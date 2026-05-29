"""Unit Tests."""

# standard
from importlib import import_module
import os
import re
import sys
from types import SimpleNamespace
import unittest
from unittest import mock
import xml.etree.ElementTree as ElementTree

# from pathlib import Path
# from inspect import cleandoc
# from typing import Any
# from json import load

try:
    prime = import_module("main")
    # works when running as
    # python -m unittest discover
except ImportError as err:
    print(err)
    # sys.exit(1)


class TestMain(unittest.TestCase):
    """Testing Main Module."""

    def test_make_title(self) -> None:
        """Test title maker."""
        self.assertRegex(
            prime.make_title("2022-01-11T23:18:19Z", "2021-12-09T10:22:06Z"),
            r"From: \d{2} \w{3,9} \d{4} - To: \d{2} \w{3,9} \d{4}",
        )

    def test_strtobool(self) -> None:
        """Test string to bool."""
        self.assertTrue(prime.strtobool("Yes"))
        self.assertFalse(prime.strtobool("nO"))
        self.assertTrue(prime.strtobool(True))
        self.assertRaises(AttributeError, prime.strtobool, None)
        self.assertRaises(ValueError, prime.strtobool, "yo!")
        self.assertRaises(AttributeError, prime.strtobool, 20.5)


class TestFetchStats(unittest.TestCase):
    """Testing WakaTime stats fetching and retry logic."""

    def setUp(self) -> None:
        """Prepare module globals and fakes used by fetch_stats."""
        prime.wk_i = SimpleNamespace(
            waka_key="dummy-key",
            time_range="last_7_days",
            api_base_url="https://wakatime.com/api",
        )
        prime.fake = mock.Mock()
        prime.fake.user_agent.return_value = "test-agent"
        prime.cryptogenic = mock.Mock()
        prime.cryptogenic.choice.side_effect = lambda sequence: sequence[0]

    @staticmethod
    def _build_response(status_code: int, payload: dict[str, object]) -> mock.Mock:
        """Build a mocked HTTP response with the given status and JSON payload."""
        response = mock.Mock()
        response.status_code = status_code
        response.reason = "OK" if status_code == 200 else "ACCEPTED"
        response.json.return_value = payload
        return response

    @mock.patch.object(prime, "sleep")
    @mock.patch.object(prime, "rq_get")
    def test_returns_data_on_first_success(
        self, mock_request: mock.Mock, mock_sleep: mock.Mock
    ) -> None:
        """Returns data and never sleeps when the first response is 200."""
        statistics = {"languages": []}
        mock_request.return_value = self._build_response(200, {"data": statistics})

        self.assertEqual(prime.fetch_stats(), statistics)
        self.assertEqual(mock_request.call_count, 1)
        mock_sleep.assert_not_called()

    @mock.patch.object(prime, "sleep")
    @mock.patch.object(prime, "rq_get")
    def test_retries_while_calculating_then_succeeds(
        self, mock_request: mock.Mock, mock_sleep: mock.Mock
    ) -> None:
        """Retries on 202 (still calculating) and returns data once ready."""
        statistics = {"languages": []}
        mock_request.side_effect = [
            self._build_response(202, {"message": "Calculating stats for this user."}),
            self._build_response(202, {"message": "Calculating stats for this user."}),
            self._build_response(200, {"data": statistics}),
        ]

        self.assertEqual(prime.fetch_stats(), statistics)
        self.assertEqual(mock_request.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @mock.patch.object(prime, "sleep")
    @mock.patch.object(prime, "rq_get")
    def test_exhausts_attempts_without_wasting_last_sleep(
        self, mock_request: mock.Mock, mock_sleep: mock.Mock
    ) -> None:
        """Stops after every attempt fails, with no idle sleep after the last try."""
        mock_request.return_value = self._build_response(
            202, {"message": "Calculating stats for this user."}
        )

        self.assertIsNone(prime.fetch_stats())
        self.assertEqual(mock_request.call_count, 6)
        self.assertEqual(mock_sleep.call_count, 5)

    @mock.patch.object(prime, "sleep")
    @mock.patch.object(prime, "rq_get")
    def test_exits_when_api_returns_error_payload(
        self, mock_request: mock.Mock, _mock_sleep: mock.Mock
    ) -> None:
        """Aborts when a 200 response carries an error payload."""
        mock_request.return_value = self._build_response(200, {"error": "Invalid API key"})

        with self.assertRaises(SystemExit) as raised:
            prime.fetch_stats()
        self.assertEqual(raised.exception.code, 1)


class TestSeigaihaGraph(unittest.TestCase):
    """Testing the seigaiha SVG graph generation."""

    @staticmethod
    def _stats(pairs: list[tuple[str, int]]) -> dict[str, list[dict[str, object]]]:
        """Build a minimal WakaTime stats payload from (name, seconds) pairs."""
        return {"languages": [{"name": name, "total_seconds": seconds} for name, seconds in pairs]}

    def test_terra_ramp_uses_palette_for_small_counts(self) -> None:
        """Counts within the palette size reuse the approved fixed colors."""
        self.assertEqual(prime._terra_ramp(5), list(prime._SEIGAIHA_PALETTE[:5]))

    def test_terra_ramp_extends_with_distinct_colors(self) -> None:
        """Counts beyond the palette size still yield distinct colors."""
        ramp = prime._terra_ramp(12)
        self.assertEqual(len(ramp), 12)
        self.assertEqual(len(set(ramp)), 12)

    def test_terra_ramp_single(self) -> None:
        """A single language uses the first palette color."""
        self.assertEqual(prime._terra_ramp(1), [prime._SEIGAIHA_PALETTE[0]])

    def test_mix_endpoints(self) -> None:
        """Mixing at the extremes returns each endpoint color."""
        self.assertEqual(prime._mix("#000000", "#ffffff", 0.0), "#000000")
        self.assertEqual(prime._mix("#000000", "#ffffff", 1.0), "#ffffff")

    def test_pattern_contains_arcs(self) -> None:
        """The seigaiha path data is a sequence of arc commands."""
        pattern = prime._seigaiha_pattern(100, 100, 20)
        self.assertTrue(pattern.startswith("M"))
        self.assertIn("A", pattern)

    def test_svg_is_wellformed_xml(self) -> None:
        """The generated SVG is well-formed XML."""
        svg = prime.generate_seigaiha_svg(self._stats([("Python", 100), ("JS", 50)]), 5)
        root = ElementTree.fromstring(svg)
        self.assertTrue(root.tag.endswith("svg"))

    def test_svg_segment_count_matches_languages(self) -> None:
        """One clipped segment is rendered per language."""
        svg = prime.generate_seigaiha_svg(self._stats([("Py", 100), ("JS", 50), ("Go", 25)]), 5)
        self.assertEqual(svg.count("clip-path"), 3)

    def test_svg_respects_language_count(self) -> None:
        """Only the top `language_count` languages are rendered."""
        stats = self._stats([("a", 5), ("b", 4), ("c", 3), ("d", 2)])
        self.assertEqual(prime.generate_seigaiha_svg(stats, 2).count("clip-path"), 2)

    def test_svg_segment_widths_are_proportional(self) -> None:
        """A larger language gets a wider segment than a smaller one."""
        svg = prime.generate_seigaiha_svg(self._stats([("big", 80), ("small", 20)]), 5)
        widths = [float(w) for w in re.findall(r'<clipPath[^>]*><rect[^>]*width="([\d.]+)"', svg)]
        self.assertGreater(widths[0], widths[1])

    def test_svg_handles_empty_stats(self) -> None:
        """Empty stats produce a valid 'No activity' placeholder SVG."""
        svg = prime.generate_seigaiha_svg({"languages": []}, 5)
        self.assertIn("No activity", svg)
        ElementTree.fromstring(svg)

    def test_svg_escapes_language_names(self) -> None:
        """Language names with XML-special characters are escaped."""
        svg = prime.generate_seigaiha_svg(self._stats([("C<>&", 100)]), 5)
        self.assertNotIn("C<>&", svg)
        self.assertIn("&lt;", svg)
        ElementTree.fromstring(svg)

    def test_prep_content_embeds_svg_image(self) -> None:
        """In seigaiha mode prep_content embeds the SVG via an <img> tag."""
        prime.wk_i = SimpleNamespace(
            show_title=False,
            show_total_time=False,
            graph_style="seigaiha",
            svg_path="assets/waka-readme.svg",
            language_count=5,
        )
        content = prime.prep_content(self._stats([("Python", 100)]))
        self.assertIn('<img src="assets/waka-readme.svg"', content)

    @staticmethod
    def _valid_config() -> object:
        """Build a WakaInput with the minimum valid fields for validation."""
        config = prime.WakaInput()
        config.gh_token = "token"
        config.waka_key = "key"
        config.api_base_url = "https://wakatime.com/api"
        config.repository = "owner/repo"
        config.commit_message = "msg"
        config.show_title = False
        config.show_total_time = False
        config._section_name = "waka"
        config.time_range = "last_7_days"
        config.language_count = 5
        return config

    def test_validate_input_falls_back_invalid_graph_style(self) -> None:
        """An invalid graph style falls back to mermaid and svg path to its default."""
        config = self._valid_config()
        config.graph_style = "nonsense"
        config.svg_path = "   "
        self.assertTrue(config.validate_input())
        self.assertEqual(config.graph_style, "mermaid")
        self.assertEqual(config.svg_path, "assets/waka-readme.svg")

    def test_validate_input_accepts_seigaiha(self) -> None:
        """A valid seigaiha style is normalized to lowercase and the svg path is kept."""
        config = self._valid_config()
        config.graph_style = "SEIGAIHA"
        config.svg_path = "custom/path.svg"
        self.assertTrue(config.validate_input())
        self.assertEqual(config.graph_style, "seigaiha")
        self.assertEqual(config.svg_path, "custom/path.svg")


if __name__ == "__main__":
    try:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        import main as prime

        # works when running as
        # python tests/test_main.py
    except ImportError as im_er:
        print(im_er)
        sys.exit(1)
    unittest.main()

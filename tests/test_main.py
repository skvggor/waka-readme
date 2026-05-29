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


class TestGraphSvg(unittest.TestCase):
    """Testing the wagara SVG graph generation, patterns and themes."""

    @staticmethod
    def _stats(pairs: list[tuple[str, int]]) -> dict[str, list[dict[str, object]]]:
        """Build a minimal WakaTime stats payload from (name, seconds) pairs."""
        return {"languages": [{"name": name, "total_seconds": seconds} for name, seconds in pairs]}

    def test_ramp_uses_anchors_for_small_counts(self) -> None:
        """Counts within the anchor list reuse the fixed colors as-is."""
        anchors = prime._THEMES["terracotta"]["ramp"]
        self.assertEqual(prime._ramp(anchors, 4), list(anchors[:4]))

    def test_ramp_extends_with_distinct_colors(self) -> None:
        """Counts beyond the anchor list still yield distinct colors."""
        anchors = prime._THEMES["sumi"]["ramp"]
        ramp = prime._ramp(anchors, len(anchors) + 5)
        self.assertEqual(len(ramp), len(anchors) + 5)
        self.assertEqual(len(set(ramp)), len(ramp))

    def test_mix_endpoints(self) -> None:
        """Mixing at the extremes returns each endpoint color."""
        self.assertEqual(prime._mix("#000000", "#ffffff", 0.0), "#000000")
        self.assertEqual(prime._mix("#000000", "#ffffff", 1.0), "#ffffff")

    def test_stroke_contrast_is_adaptive(self) -> None:
        """Outline is lighter than dark fills and darker than light fills."""
        theme = prime._THEMES["terracotta"]
        self.assertGreater(
            prime._luminance(prime._stroke_for("#101010", theme)), prime._luminance("#101010")
        )
        self.assertLess(
            prime._luminance(prime._stroke_for("#f0d0a0", theme)), prime._luminance("#f0d0a0")
        )

    def test_every_pattern_produces_wellformed_svg(self) -> None:
        """Each registered pattern renders a well-formed SVG band."""
        for pattern in prime._PATTERNS:
            svg = prime.generate_graph_svg(self._stats([("Py", 100), ("JS", 50)]), 5, pattern)
            root = ElementTree.fromstring(svg)
            self.assertTrue(root.tag.endswith("svg"))

    def test_every_theme_uses_its_background(self) -> None:
        """Each theme renders a valid SVG painted with its own background."""
        for name, theme in prime._THEMES.items():
            svg = prime.generate_graph_svg(self._stats([("Py", 100)]), 5, "seigaiha", name)
            ElementTree.fromstring(svg)
            self.assertIn(f'fill="{theme["bg"]}"', svg)

    def test_unknown_pattern_and_theme_fall_back(self) -> None:
        """Unknown pattern/theme fall back to seigaiha on terracotta."""
        svg = prime.generate_graph_svg(self._stats([("Py", 100)]), 5, "bogus", "bogus")
        ElementTree.fromstring(svg)
        self.assertIn(f'fill="{prime._THEMES["terracotta"]["bg"]}"', svg)

    def test_svg_segment_count_matches_languages(self) -> None:
        """One clipped segment is rendered per language."""
        svg = prime.generate_graph_svg(self._stats([("Py", 100), ("JS", 50), ("Go", 25)]), 5)
        self.assertEqual(svg.count("clip-path"), 3)

    def test_svg_respects_language_count(self) -> None:
        """Only the top `language_count` languages are rendered."""
        stats = self._stats([("a", 5), ("b", 4), ("c", 3), ("d", 2)])
        self.assertEqual(prime.generate_graph_svg(stats, 2).count("clip-path"), 2)

    def test_svg_segment_widths_are_proportional(self) -> None:
        """A larger language gets a wider segment than a smaller one."""
        svg = prime.generate_graph_svg(self._stats([("big", 80), ("small", 20)]), 5)
        widths = [float(w) for w in re.findall(r'<clipPath[^>]*><rect[^>]*width="([\d.]+)"', svg)]
        self.assertGreater(widths[0], widths[1])

    def test_svg_handles_empty_stats(self) -> None:
        """Empty stats produce a valid 'No activity' placeholder SVG."""
        svg = prime.generate_graph_svg({"languages": []}, 5)
        self.assertIn("No activity", svg)
        ElementTree.fromstring(svg)

    def test_svg_escapes_language_names(self) -> None:
        """Language names with XML-special characters are escaped."""
        svg = prime.generate_graph_svg(self._stats([("C<>&", 100)]), 5)
        self.assertNotIn("C<>&", svg)
        self.assertIn("&lt;", svg)
        ElementTree.fromstring(svg)

    def test_prep_content_embeds_svg_image(self) -> None:
        """In any pattern mode prep_content embeds the SVG via an <img> tag."""
        prime.wk_i = SimpleNamespace(
            show_title=False,
            show_total_time=False,
            graph_style="kikko",
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
        config.graph_style = "mermaid"
        config.theme = "terracotta"
        return config

    def test_validate_input_falls_back_invalid_graph_style(self) -> None:
        """An invalid graph style falls back to mermaid and svg path to its default."""
        config = self._valid_config()
        config.graph_style = "nonsense"
        config.svg_path = "   "
        self.assertTrue(config.validate_input())
        self.assertEqual(config.graph_style, "mermaid")
        self.assertEqual(config.svg_path, "assets/waka-readme.svg")

    def test_validate_input_accepts_pattern_and_theme(self) -> None:
        """A valid pattern and theme are normalized to lowercase and kept."""
        config = self._valid_config()
        config.graph_style = "SHIPPO"
        config.theme = "AI"
        config.svg_path = "custom/path.svg"
        self.assertTrue(config.validate_input())
        self.assertEqual(config.graph_style, "shippo")
        self.assertEqual(config.theme, "ai")
        self.assertEqual(config.svg_path, "custom/path.svg")

    def test_validate_input_falls_back_invalid_theme(self) -> None:
        """An invalid theme falls back to terracotta."""
        config = self._valid_config()
        config.graph_style = "seigaiha"
        config.theme = "bogus"
        self.assertTrue(config.validate_input())
        self.assertEqual(config.theme, "terracotta")


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

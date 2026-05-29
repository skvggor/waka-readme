"""Unit Tests."""

# standard
from dataclasses import dataclass  # , field
from importlib import import_module
from itertools import product
import os
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

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


@dataclass
class TestData:
    """Test Data."""

    # for future tests
    # waka_json: dict[str, dict[str, Any]] = field(
    #     default_factory=lambda: {}
    # )
    bar_percent: tuple[int | float, ...] | None = None
    graph_blocks: tuple[str, ...] | None = None
    waka_graphs: tuple[list[str], ...] | None = None
    dummy_readme: str = ""

    def populate(self) -> None:
        """Populate Test Data."""
        # for future tests
        # with open(
        #     file=Path(__file__).parent / "sample_data.json",
        #     encoding="utf-8",
        #     mode="rt",
        # ) as wkf:
        #     self.waka_json = load(wkf)

        self.bar_percent = (0, 100, 49.999, 50, 25, 75, 3.14, 9.901, 87.334, 87.333, 4.666, 4.667)

        self.graph_blocks = ("░▒▓█", "⚪⚫", "⓪①②③④⑤⑥⑦⑧⑨⑩")

        self.waka_graphs = (
            [
                "░░░░░░░░░░░░░░░░░░░░░░░░░",
                "█████████████████████████",
                "████████████▒░░░░░░░░░░░░",
                "████████████▓░░░░░░░░░░░░",
                "██████▒░░░░░░░░░░░░░░░░░░",
                "██████████████████▓░░░░░░",
                "▓░░░░░░░░░░░░░░░░░░░░░░░░",
                "██▒░░░░░░░░░░░░░░░░░░░░░░",
                "██████████████████████░░░",
                "█████████████████████▓░░░",
                "█░░░░░░░░░░░░░░░░░░░░░░░░",
                "█▒░░░░░░░░░░░░░░░░░░░░░░░",
            ],
            [
                "⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
                "⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫",
                "⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
                "⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
                "⚫⚫⚫⚫⚫⚫⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
                "⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚪⚪⚪⚪⚪⚪",
                "⚫⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
                "⚫⚫⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
                "⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚪⚪⚪",
                "⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚫⚪⚪⚪",
                "⚫⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
                "⚫⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪⚪",
            ],
            [
                "⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
                "⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩",
                "⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑤⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
                "⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑤⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
                "⑩⑩⑩⑩⑩⑩③⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
                "⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑧⓪⓪⓪⓪⓪⓪",
                "⑧⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
                "⑩⑩⑤⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
                "⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑧⓪⓪⓪",
                "⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑩⑧⓪⓪⓪",
                "⑩②⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
                "⑩②⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪⓪",
            ],
        )

        # self.dummy_readme = cleandoc("""
        # My Test Readme Start
        # <!--START_SECTION:waka-->
        # <!--END_SECTION:waka-->
        # My Test Readme End
        # """)


class TestMain(unittest.TestCase):
    """Testing Main Module."""

    def test_make_graph(self) -> None:
        """Test graph maker."""
        if not tds.graph_blocks or not tds.waka_graphs or not tds.bar_percent:
            raise AssertionError("Data population failed")

        for (idx, grb), (jdy, bpc) in product(
            enumerate(tds.graph_blocks), enumerate(tds.bar_percent)
        ):
            self.assertEqual(prime.make_graph(grb, bpc, 25), tds.waka_graphs[idx][jdy])

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


tds = TestData()
tds.populate()

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

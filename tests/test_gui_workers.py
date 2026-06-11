"""Tests for GUI workers (CrawlWorker)."""

from unittest.mock import MagicMock

from crawler import CrawlResult
from gui.workers import CrawlWorker
from parsers import APEntry


class TestCrawlWorker:
    def test_on_result_progress_overcount(self):
        """Test that ap_progress is emitted only once per AP, but result_ready is emitted for all."""
        session_mock = MagicMock()
        config_mock = MagicMock()

        ap_list = [APEntry("AP-TEST", "10.0.0.1", 1, False)]

        worker = CrawlWorker(
            session=session_mock,
            ap_list=ap_list,
            switch_dict={},
            config=config_mock,
            already_done=set(),
        )

        # Mock the signal emit methods to track calls without a Qt event loop
        worker.ap_progress = MagicMock()
        worker.result_ready = MagicMock()

        # Two successful results for the SAME AP (multi-neighbor)
        res1 = CrawlResult(
            "AP-TEST", "10.0.0.1", "SW-1", "10.0.1.1", "success", error="", local_intf="GE0/0/1", neighbor_intf="85"
        )
        res2 = CrawlResult(
            "AP-TEST", "10.0.0.1", "SW-2", "10.0.1.2", "success", error="", local_intf="GE0/0/2", neighbor_intf="86"
        )

        worker._on_result(res1)
        worker._on_result(res2)

        # The result_ready signal should emit for both rows to ensure CSV saving works
        assert worker.result_ready.emit.call_count == 2
        worker.result_ready.emit.assert_any_call(res1)
        worker.result_ready.emit.assert_any_call(res2)

        # The progress signal should only emit ONCE for the first result
        assert worker.ap_progress.emit.call_count == 1
        assert worker._current_count == 1

"""Unit tests for crawler.py — crawl logic with mocked SSH session."""

from unittest.mock import MagicMock, patch

import pytest

from config import Config
from crawler import CrawlResult, crawl_all_aps, crawl_single_ap, exit_ap_session
from parsers import APEntry


def make_config(**kwargs):
    defaults = dict(host="10.0.0.1", port=22, username="admin", password="secret",
                    ssh_timeout=30, ap_connect_timeout=5, command_timeout=5)
    defaults.update(kwargs)
    return Config(**defaults)


def make_ap(name="AP-TEST", ip="10.0.0.1", ap_id=0, offline=False):
    return APEntry(name=name, ip=ip, ap_id=ap_id, is_offline=offline)


# ============================================================
# crawl_all_aps tests
# ============================================================


class TestCrawlAllAps:
    def test_does_not_skip_offline_aps_but_processes_them(self):
        session = MagicMock()
        ap_list = [make_ap("AP-OFF", "--", 0, offline=True)]
        config = make_config()

        with patch("crawler.crawl_single_ap") as mock_crawl:
            mock_crawl.return_value = [CrawlResult("AP-OFF", "198.51.100.5", "SW-1", "10.0.1.1", "success")]
            results = crawl_all_aps(session, ap_list, {}, config)

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].ap_name == "AP-OFF"
        mock_crawl.assert_called_once()

    def test_skips_already_done(self):
        session = MagicMock()
        ap_list = [make_ap("AP-DONE", "10.0.0.1", 0), make_ap("AP-NEW", "10.0.0.2", 1)]
        config = make_config()
        already_done = {"AP-DONE"}

        with patch("crawler.crawl_single_ap") as mock_crawl:
            mock_crawl.return_value = [CrawlResult("AP-NEW", "10.0.0.2", "SW-1", "10.0.1.1", "success")]
            results = crawl_all_aps(session, ap_list, {}, config, already_done=already_done)

        # Only AP-NEW should be crawled
        assert len(results) == 1
        assert results[0].ap_name == "AP-NEW"
        mock_crawl.assert_called_once()

    def test_handles_exception_gracefully(self):
        session = MagicMock()
        ap_list = [make_ap("AP-ERR", "10.0.0.1", 0)]
        config = make_config()

        with patch("crawler.crawl_single_ap") as mock_crawl:
            mock_crawl.side_effect = RuntimeError("something broke")
            results = crawl_all_aps(session, ap_list, {}, config)

        assert len(results) == 1
        assert results[0].status == "failed"
        assert "something broke" in results[0].error

    def test_socket_closed_triggers_reconnect(self):
        session = MagicMock()
        ap_list = [make_ap("AP-1", "10.0.0.1", 0)]
        config = make_config()

        with patch("crawler.crawl_single_ap") as mock_crawl, \
             patch("crawler._reconnect") as mock_reconnect:
            # First call raises socket closed, retry succeeds
            mock_crawl.side_effect = [
                OSError("Socket is closed"),
                [CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success")],
            ]
            mock_reconnect.return_value = True
            results = crawl_all_aps(session, ap_list, {}, config)

        assert len(results) == 1
        assert results[0].status == "success"
        mock_reconnect.assert_called_once()


# ============================================================
# crawl_single_ap tests
# ============================================================


class TestCrawlSingleAp:
    def test_successful_crawl(self):
        session = MagicMock()
        ap = make_ap("AP-TEST", "10.0.0.1", 5)
        switch_dict = {"SW-TEST": "10.0.1.1"}
        config = make_config()

        # Mock the SSH interaction
        lldp_output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            SW-TEST                          1                         100\n"
            "<AP-TEST>\n"
        )
        session.wait_for_prompt.return_value = "<AP-TEST>"
        session.send_command.return_value = lldp_output

        with patch("crawler.exit_ap_session"), patch("crawler._drain_buffer"):
            results = crawl_single_ap(session, ap, switch_dict, config)

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].switch_name == "SW-TEST"
        assert results[0].switch_ip == "10.0.1.1"
        assert results[0].local_intf == "GE0/0/0"
        assert results[0].neighbor_intf == "1"

    def test_parses_resolved_ip_from_stelnet(self):
        session = MagicMock()
        ap = make_ap("AP-TEST", "--", 5)
        switch_dict = {"SW-TEST": "10.0.1.1"}
        config = make_config()

        output_with_ip = "Trying 198.51.100.152 ...\nPress CTRL+K to abort\nConnected to 198.51.100.152 ...\nWarning: The initial password ...\nContinue to access it? [Y/N]:\n<AP-TEST>"
        session.wait_for_prompt.return_value = output_with_ip
        session.send_command.return_value = "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\nGE0/0/0            SW-TEST                          1                         100\n<AP-TEST>\n"

        with patch("crawler.exit_ap_session"), patch("crawler._drain_buffer"):
            results = crawl_single_ap(session, ap, switch_dict, config)

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].ap_ip == "198.51.100.152"
        assert ap.ip == "198.51.100.152"

    def test_switch_not_in_dict(self):
        session = MagicMock()
        ap = make_ap("AP-TEST", "10.0.0.1", 5)
        switch_dict = {}  # empty
        config = make_config()

        lldp_output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            UNKNOWN-SW                       1                         100\n"
            "<AP-TEST>\n"
        )
        session.wait_for_prompt.return_value = "<AP-TEST>"
        session.send_command.return_value = lldp_output

        with patch("crawler.exit_ap_session"), patch("crawler._drain_buffer"):
            results = crawl_single_ap(session, ap, switch_dict, config)

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].switch_name == "UNKNOWN-SW"
        assert results[0].switch_ip == "N/A"

    def test_connection_closed_by_remote(self):
        """If AP never shows prompt (timeout), it returns failed."""
        session = MagicMock()
        ap = make_ap("AP-TEST", "10.0.0.1", 5)
        config = make_config()

        session.wait_for_prompt.side_effect = TimeoutError("timed out waiting for AP prompt")

        with patch("crawler.exit_ap_session"), patch("crawler._drain_buffer"):
            results = crawl_single_ap(session, ap, {}, config)
        assert len(results) == 1
        assert results[0].status == "failed"
        assert "Timeout" in results[0].error

    def test_timeout_returns_failed(self):
        session = MagicMock()
        ap = make_ap("AP-TEST", "10.0.0.1", 5)
        config = make_config()

        session.wait_for_prompt.side_effect = TimeoutError("timed out")

        with patch("crawler.exit_ap_session"), patch("crawler._drain_buffer"):
            results = crawl_single_ap(session, ap, {}, config)

        assert len(results) == 1
        assert results[0].status == "failed"
        assert "Timeout" in results[0].error

    def test_multiple_neighbors(self):
        session = MagicMock()
        ap = make_ap("AP-MULTI", "10.0.0.1", 5)
        switch_dict = {"SW-A": "10.0.1.1", "SW-B": "10.0.1.2"}
        config = make_config()

        lldp_output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            SW-A                             1                         100\n"
            "GE0/0/0            SW-B                             2                         100\n"
            "<AP-MULTI>\n"
        )
        session.wait_for_prompt.return_value = "<AP-MULTI>"
        session.send_command.return_value = lldp_output

        with patch("crawler.exit_ap_session"), patch("crawler._drain_buffer"):
            results = crawl_single_ap(session, ap, switch_dict, config)

        assert len(results) == 2
        assert results[0].switch_name == "SW-A"
        assert results[0].local_intf == "GE0/0/0"
        assert results[0].neighbor_intf == "1"
        assert results[1].switch_name == "SW-B"
        assert results[1].local_intf == "GE0/0/0"
        assert results[1].neighbor_intf == "2"


# ============================================================
# exit_ap_session tests
# ============================================================


class TestExitApSession:
    def test_quit_succeeds(self):
        session = MagicMock()
        session.send_command.return_value = "[WAC-CONTROLLER]"
        assert exit_ap_session(session) is True

    def test_quit_fails_return_succeeds(self):
        session = MagicMock()
        session.send_command.side_effect = [TimeoutError("quit timeout"), "[WAC-CONTROLLER]"]
        assert exit_ap_session(session) is True

    def test_both_fail(self):
        session = MagicMock()
        session.send_command.side_effect = [TimeoutError("quit"), TimeoutError("return")]
        assert exit_ap_session(session) is False

class TestUpdateApListIpSafely:
    def test_updates_missing_ip_preserves_format(self, tmp_path):
        from crawler import update_ap_list_ip_safely
        list_path = tmp_path / "list_ap.txt"

        content = (
            "# A comment\n"
            "\n"
            "AP-1\t--\t100\n"
            "AP-2\t\t200\n"
            "AP-3\t192.168.1.1\t300\n"
        )
        list_path.write_text(content, encoding="utf-8")

        # Update AP-1
        update_ap_list_ip_safely(str(list_path), "AP-1", 100, "198.51.100.100")

        new_content = list_path.read_text(encoding="utf-8")
        assert "AP-1\t198.51.100.100\t100" in new_content
        assert "# A comment" in new_content
        assert "\n\n" in new_content
        assert "AP-3\t192.168.1.1\t300" in new_content

        # Try updating AP-3 (should not overwrite existing IP)
        update_ap_list_ip_safely(str(list_path), "AP-3", 300, "10.0.0.99")
        new_content = list_path.read_text(encoding="utf-8")
        assert "AP-3\t192.168.1.1\t300" in new_content

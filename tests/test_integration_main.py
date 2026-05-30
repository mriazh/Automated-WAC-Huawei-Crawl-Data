"""Integration test for main.py with fully mocked SSH.

Tests the full flow from main() to CSV output, verifying:
- CSV file is created with correct content
- SSH disconnect is called even on exceptions

Requirements: 10.1, 10.2
"""

import csv
import os
from unittest.mock import MagicMock, patch

import pytest

from config import Config
from crawler import CrawlResult
from parsers import APEntry


@pytest.fixture
def test_config():
    """Create a test Config instance."""
    return Config(
        host="192.168.1.1",
        port=22,
        username="admin",
        password="secret",
        ssh_timeout=10,
        ap_connect_timeout=10,
        command_timeout=5,
    )


@pytest.fixture
def sample_ap_list():
    """Sample parsed AP list with online and offline APs."""
    return [
        APEntry(name="AP-BLDG-A-L1-IN01", ip="192.0.2.10", ap_id=1, is_offline=False),
        APEntry(name="AP-BLDG-B-L1-OUT01", ip="--", ap_id=2, is_offline=True),
        APEntry(name="AP-BLDG-C-L2-IN05", ip="192.0.2.20", ap_id=3, is_offline=False),
    ]


@pytest.fixture
def sample_switch_dict():
    """Sample switch dictionary."""
    return {
        "SW-BLDG-A-L2": "198.51.100.10",
        "SW-BLDG-B-L1": "198.51.100.20",
    }


@pytest.fixture
def sample_crawl_results():
    """Sample crawl results matching the AP list."""
    return [
        CrawlResult(
            ap_name="AP-BLDG-A-L1-IN01", ap_ip="192.0.2.10",
            switch_name="SW-BLDG-A-L2", switch_ip="198.51.100.10",
            status="success",
        ),
        CrawlResult(
            ap_name="AP-BLDG-B-L1-OUT01", ap_ip="--",
            switch_name="N/A", switch_ip="N/A",
            status="skipped",
        ),
        CrawlResult(
            ap_name="AP-BLDG-C-L2-IN05", ap_ip="192.0.2.20",
            switch_name="SW-BLDG-B-L1", switch_ip="198.51.100.20",
            status="success",
        ),
    ]


class TestMainIntegrationFullFlow:
    """Integration tests for main() full flow with mocked SSH."""

    def test_main_full_flow_creates_csv_with_correct_content(
        self, tmp_path, test_config, sample_ap_list, sample_switch_dict,
        sample_crawl_results
    ):
        """main() produces a CSV file with correct AP-to-Switch mapping.

        Validates Requirements 10.1, 10.2: SSH session is properly managed
        and CSV output is generated correctly through the full pipeline.
        """
        mock_session = MagicMock()

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch("main.load_config", return_value=test_config), \
                 patch("main.parse_ap_list", return_value=sample_ap_list), \
                 patch("main.parse_switch_list", return_value=sample_switch_dict), \
                 patch("main.SSHSession", return_value=mock_session), \
                 patch("main.crawl_all_aps", return_value=sample_crawl_results), \
                 patch("main.read_existing_csv", return_value=set()):

                from main import main
                main()

            # Verify CSV was created
            csv_path = tmp_path / "lldp_result.csv"
            assert csv_path.exists(), "CSV file should be created"

            # Read and verify CSV content
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            # Header row
            assert rows[0] == ["AP", "Switch"]

            # Data rows - only successful APs (AP 2 is offline/skipped)
            data_rows = rows[1:]
            assert len(data_rows) == 2

            # First successful AP
            assert data_rows[0][0] == "AP-BLDG-A-L1-IN01 (192.0.2.10)"
            assert data_rows[0][1] == "SW-BLDG-A-L2 (198.51.100.10)"

            # Second successful AP
            assert data_rows[1][0] == "AP-BLDG-C-L2-IN05 (192.0.2.20)"
            assert data_rows[1][1] == "SW-BLDG-B-L1 (198.51.100.20)"

            # Verify SSH lifecycle was called correctly
            mock_session.connect.assert_called_once()
            mock_session.enter_system_view.assert_called_once()
            mock_session.disconnect.assert_called_once()

        finally:
            os.chdir(original_cwd)

    def test_main_full_flow_with_all_failed_aps(self, tmp_path, test_config):
        """main() creates header-only CSV when all APs fail.

        Validates that CSV is still generated even with no successful results.
        """
        mock_session = MagicMock()

        ap_list = [
            APEntry(name="AP-FAIL-01", ip="192.0.2.50", ap_id=10, is_offline=False),
        ]
        results = [
            CrawlResult(
                ap_name="AP-FAIL-01", ap_ip="192.0.2.50",
                switch_name="N/A", switch_ip="N/A",
                status="failed", error="Timeout",
            ),
        ]

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch("main.load_config", return_value=test_config), \
                 patch("main.parse_ap_list", return_value=ap_list), \
                 patch("main.parse_switch_list", return_value={}), \
                 patch("main.SSHSession", return_value=mock_session), \
                 patch("main.crawl_all_aps", return_value=results), \
                 patch("main.read_existing_csv", return_value=set()):

                from main import main
                main()

            # CSV should still exist with header only
            csv_path = tmp_path / "lldp_result.csv"
            assert csv_path.exists()

            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)

            assert rows[0] == ["AP", "Switch"]
            assert len(rows) == 1  # header only, no data rows

            # Disconnect still called
            mock_session.disconnect.assert_called_once()

        finally:
            os.chdir(original_cwd)

    def test_main_disconnect_called_on_success(self, tmp_path, test_config):
        """disconnect() is called after successful crawl completion.

        Validates Requirement 10.1: SSH connection closed after processing.
        """
        mock_session = MagicMock()

        results = [
            CrawlResult(
                ap_name="AP-BLDG-A-L1-IN01", ap_ip="192.0.2.10",
                switch_name="SW-BLDG-A-L2", switch_ip="198.51.100.10",
                status="success",
            )
        ]

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch("main.load_config", return_value=test_config), \
                 patch("main.parse_ap_list", return_value=[]), \
                 patch("main.parse_switch_list", return_value={}), \
                 patch("main.SSHSession", return_value=mock_session), \
                 patch("main.crawl_all_aps", return_value=results), \
                 patch("main.write_csv", return_value="lldp_result.csv"), \
                 patch("main._display_rich_summary"), \
                 patch("main.read_existing_csv", return_value=set()):

                from main import main
                main()

            # Verify disconnect was called
            mock_session.disconnect.assert_called_once()

        finally:
            os.chdir(original_cwd)

    def test_main_disconnect_called_on_crawl_exception(
        self, tmp_path, test_config
    ):
        """disconnect() is called even when crawl_all_aps raises an exception.

        Validates Requirement 10.2: SSH connection closed on unrecoverable error.
        """
        mock_session = MagicMock()

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch("main.load_config", return_value=test_config), \
                 patch("main.parse_ap_list", return_value=[]), \
                 patch("main.parse_switch_list", return_value={}), \
                 patch("main.SSHSession", return_value=mock_session), \
                 patch("main.crawl_all_aps", side_effect=RuntimeError("SSH connection lost")), \
                 patch("main.read_existing_csv", return_value=set()):

                from main import main
                with pytest.raises(RuntimeError, match="SSH connection lost"):
                    main()

            # Verify disconnect was still called despite the exception
            mock_session.disconnect.assert_called_once()

        finally:
            os.chdir(original_cwd)

    def test_main_disconnect_called_on_enter_system_view_failure(
        self, tmp_path, test_config
    ):
        """disconnect() is called when enter_system_view() raises SSHConnectionError.

        Validates Requirement 10.2: cleanup on SSH command failure.
        """
        from ssh_client import SSHConnectionError

        mock_session = MagicMock()
        mock_session.enter_system_view.side_effect = SSHConnectionError("timeout")

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch("main.load_config", return_value=test_config), \
                 patch("main.parse_ap_list", return_value=[]), \
                 patch("main.parse_switch_list", return_value={}), \
                 patch("main.SSHSession", return_value=mock_session), \
                 patch("main.read_existing_csv", return_value=set()):

                from main import main
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

            # disconnect must be called even though enter_system_view failed
            mock_session.disconnect.assert_called_once()

        finally:
            os.chdir(original_cwd)

    def test_main_no_disconnect_when_session_not_created(self, tmp_path):
        """No disconnect attempt when session was never created.

        Validates that cleanup is only attempted when session object exists.
        """
        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch("main.load_config", side_effect=SystemExit(1)), \
                 patch("main.SSHSession") as mock_ssh_class:

                from main import main
                with pytest.raises(SystemExit):
                    main()

            # SSHSession should never have been instantiated
            mock_ssh_class.assert_not_called()

        finally:
            os.chdir(original_cwd)

    def test_main_disconnect_called_on_write_csv_exception(
        self, tmp_path, test_config
    ):
        """disconnect() is called even when write_csv raises an exception.

        Validates Requirement 10.2: cleanup on output failure.
        """
        mock_session = MagicMock()

        results = [
            CrawlResult(
                ap_name="AP-TEST", ap_ip="192.0.2.30",
                switch_name="SW-TEST", switch_ip="198.51.100.30",
                status="success",
            )
        ]

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with patch("main.load_config", return_value=test_config), \
                 patch("main.parse_ap_list", return_value=[]), \
                 patch("main.parse_switch_list", return_value={}), \
                 patch("main.SSHSession", return_value=mock_session), \
                 patch("main.crawl_all_aps", return_value=results), \
                 patch("main.write_csv", side_effect=OSError("Disk full")), \
                 patch("main.read_existing_csv", return_value=set()):

                from main import main
                with pytest.raises(OSError, match="Disk full"):
                    main()

            # disconnect must still be called
            mock_session.disconnect.assert_called_once()

        finally:
            os.chdir(original_cwd)

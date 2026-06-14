"""Tests for update checker utility."""

import json
from unittest.mock import MagicMock, patch

from gui.update_checker import (
    UpdateCheckWorker,
    is_newer_version,
    parse_version,
    show_update_dialog,
)

import app_info


class TestVersionParsing:
    def test_parse_version(self):
        assert parse_version("v1.2.3") == (1, 2, 3)
        assert parse_version("1.2.3") == (1, 2, 3)
        assert parse_version("v2.0") == (2, 0)
        assert parse_version("1.1.0-beta") == (1, 1, 0)

    def test_version_comparison(self):
        # latest > current
        assert is_newer_version("v1.1.0", "1.0.0") is True
        assert is_newer_version("1.2.10", "1.2.9") is True
        # latest == current
        assert is_newer_version("v1.0.0", "1.0.0") is False
        # latest < current
        assert is_newer_version("v1.0.0", "1.1.0") is False


class TestMapNetworkError:
    def test_map_timeout(self):
        from gui.update_checker import map_network_error
        assert "timed out" in map_network_error("urllib.error.URLError: <urlopen error timed out>")
        assert "timed out" in map_network_error("timeout")

    def test_map_unreachable(self):
        from gui.update_checker import map_network_error
        assert "Could not reach GitHub" in map_network_error("getaddrinfo failed")
        assert "Could not reach GitHub" in map_network_error("Network is unreachable")
        assert "Could not reach GitHub" in map_network_error("temporary failure in name resolution")

    def test_map_other(self):
        from gui.update_checker import map_network_error
        assert map_network_error("HTTP 404") == "HTTP 404"
        assert map_network_error("Some weird error") == "Some weird error"


class TestUpdateCheckWorker:
    @patch("urllib.request.urlopen")
    def test_worker_emits_update_available(self, mock_urlopen):
        # Prepare mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_data = {
            "tag_name": "v9.9.9",
            "html_url": "https://github.com/mriazh/Automated-WAC-Huawei-Crawl-Data/releases/tag/v9.9.9",
            "body": "Test release notes",
            "assets": [
                {
                    "name": "WAC-Crawl-Setup-v9.9.9.exe",
                    "browser_download_url": "https://example.com/WAC-Crawl-Setup-v9.9.9.exe",
                }
            ],
        }
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        worker = UpdateCheckWorker()
        worker.signals.update_available = MagicMock()
        worker.signals.up_to_date = MagicMock()
        worker.signals.error = MagicMock()

        worker.run()

        worker.signals.update_available.emit.assert_called_once_with(mock_data)
        worker.signals.up_to_date.emit.assert_not_called()
        worker.signals.error.emit.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_worker_emits_up_to_date(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_data = {
            "tag_name": app_info.APP_VERSION,
        }
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        worker = UpdateCheckWorker()
        worker.signals.update_available = MagicMock()
        worker.signals.up_to_date = MagicMock()
        worker.signals.error = MagicMock()

        worker.run()

        worker.signals.update_available.emit.assert_not_called()
        worker.signals.up_to_date.emit.assert_called_once()
        worker.signals.error.emit.assert_not_called()

    @patch("urllib.request.urlopen")
    def test_worker_emits_error_on_non_200(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 404
        mock_urlopen.return_value.__enter__.return_value = mock_response

        worker = UpdateCheckWorker()
        worker.signals.update_available = MagicMock()
        worker.signals.up_to_date = MagicMock()
        worker.signals.error = MagicMock()

        worker.run()

        worker.signals.error.emit.assert_called_once_with("HTTP 404")
        worker.signals.update_available.emit.assert_not_called()
        worker.signals.up_to_date.emit.assert_not_called()


class TestUpdateDialogLogic:
    @patch("gui.update_checker.QMessageBox")
    def test_show_update_dialog_no_installer_asset(self, mock_msgbox):
        parent_mock = MagicMock()
        release_data = {
            "tag_name": "v2.0.0",
            "body": "Notes",
            "assets": [
                {
                    "name": "source_code.zip",
                }
            ],
        }

        # Manual check should warn
        show_update_dialog(parent_mock, release_data, is_manual=True)
        mock_msgbox.warning.assert_called_once()

    @patch("gui.update_checker.QMessageBox")
    @patch("gui.update_checker._start_download")
    def test_show_update_dialog_with_installer_asset(self, mock_start_download, mock_msgbox):
        parent_mock = MagicMock()
        release_data = {
            "tag_name": "v2.0.0",
            "body": "Notes",
            "assets": [
                {
                    "name": "WAC-Crawl-Setup.exe",
                    "browser_download_url": "https://example.com/installer.exe",
                }
            ],
        }

        # Setup mock message box
        msg_instance = mock_msgbox.return_value
        
        # We need to simulate the user clicking "Update Now"
        # We mock addButton to return a dummy button, and clickedButton to return it
        update_btn_mock = MagicMock()
        view_btn_mock = MagicMock()
        later_btn_mock = MagicMock()
        
        # Make the first call to addButton return update_btn_mock
        msg_instance.addButton.side_effect = [update_btn_mock, view_btn_mock, later_btn_mock]
        msg_instance.clickedButton.return_value = update_btn_mock

        show_update_dialog(parent_mock, release_data, is_manual=True)
        
        # Verify it passed the right URL and asset name to download
        mock_start_download.assert_called_once_with(
            parent_mock, "https://example.com/installer.exe", "WAC-Crawl-Setup.exe"
        )

    @patch("gui.update_checker.QMessageBox")
    @patch("gui.update_checker._start_download")
    def test_show_update_dialog_invalid_download_url(self, mock_start_download, mock_msgbox):
        parent_mock = MagicMock()
        release_data = {
            "tag_name": "v2.0.0",
            "body": "Notes",
            "assets": [
                {
                    "name": "WAC-Crawl-Setup.exe",
                    "browser_download_url": "http://example.com/installer.exe",
                }
            ],
        }

        # Setup mock message box
        msg_instance = mock_msgbox.return_value

        # We need to simulate the user clicking "Update Now"
        update_btn_mock = MagicMock()
        view_btn_mock = MagicMock()
        later_btn_mock = MagicMock()

        msg_instance.addButton.side_effect = [update_btn_mock, view_btn_mock, later_btn_mock]
        msg_instance.clickedButton.return_value = update_btn_mock

        show_update_dialog(parent_mock, release_data, is_manual=True)
        # Assert warning was shown and download was not started
        mock_msgbox.warning.assert_called_once_with(parent_mock, "Update Error", "Invalid installer download URL.")
        mock_start_download.assert_not_called()

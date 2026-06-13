"""Background worker and dialog for update checking and downloading."""

import json
import logging
import os
import subprocess
import tempfile
import urllib.request
import webbrowser

from PySide6.QtCore import QObject, QRunnable, Signal, QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

import app_info

logger = logging.getLogger(__name__)


def parse_version(version_str: str) -> tuple:
    """Parse a version string like 'v1.1.0' or '1.0.0' into a numeric tuple."""
    if version_str.startswith("v"):
        version_str = version_str[1:]
    # Strip pre-release suffix if present
    version_str = version_str.split("-")[0]
    parts = []
    for p in version_str.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break  # Stop at non-numeric parts like '-beta'
    return tuple(parts)


def is_newer_version(latest_str: str, current_str: str) -> bool:
    """Check if the latest version is greater than the current version."""
    return parse_version(latest_str) > parse_version(current_str)


class UpdateCheckSignals(QObject):
    """Signals for update checking."""

    update_available = Signal(dict)  # release_data
    up_to_date = Signal()
    error = Signal(str)


class UpdateCheckWorker(QRunnable):
    """Worker to check for updates without blocking UI."""

    def __init__(self):
        super().__init__()
        self.signals = UpdateCheckSignals()

    def run(self):
        """Fetch latest release info from GitHub API."""
        try:
            req = urllib.request.Request(
                app_info.LATEST_RELEASE_API,
                headers={"User-Agent": "WAC-Huawei-Crawl-Updater"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status != 200:
                    self.signals.error.emit(f"HTTP {response.status}")
                    return
                data = json.loads(response.read().decode("utf-8"))

            latest_version = data.get("tag_name", "")
            if latest_version and is_newer_version(latest_version, app_info.APP_VERSION):
                self.signals.update_available.emit(data)
            else:
                self.signals.up_to_date.emit()

        except Exception as e:
            logger.error("Update check failed: %s", e)
            self.signals.error.emit(str(e))


class DownloadUpdateSignals(QObject):
    """Signals for downloading updates."""

    download_complete = Signal(str)  # filepath
    error = Signal(str)


class DownloadUpdateWorker(QRunnable):
    """Worker to download the installer asset without blocking UI."""

    def __init__(self, download_url: str, asset_name: str):
        super().__init__()
        self.download_url = download_url
        self.asset_name = asset_name
        self.signals = DownloadUpdateSignals()
        self.is_cancelled = False

    def run(self):
        """Download the file to a temp directory."""
        try:
            temp_dir = os.path.join(tempfile.gettempdir(), "WAC-Crawl-Update")
            os.makedirs(temp_dir, exist_ok=True)
            filepath = os.path.join(temp_dir, self.asset_name)

            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "WAC-Huawei-Crawl-Updater"},
            )
            with urllib.request.urlopen(req, timeout=30) as response, open(filepath, "wb") as out_file:
                while True:
                    if self.is_cancelled:
                        break
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    out_file.write(chunk)

            if not self.is_cancelled:
                self.signals.download_complete.emit(filepath)
        except Exception as e:
            logger.error("Download failed: %s", e)
            self.signals.error.emit(str(e))


def show_update_dialog(parent, release_data: dict, is_manual: bool):
    """Show the update dialog when an update is available."""
    tag_name = release_data.get("tag_name", "")
    body = release_data.get("body", "")
    html_url = release_data.get("html_url", app_info.RELEASES_URL)
    assets = release_data.get("assets", [])

    # Find installer asset
    installer_asset = None
    for asset in assets:
        name = asset.get("name", "")
        if name.startswith(app_info.INSTALLER_ASSET_PREFIX) and name.endswith(app_info.INSTALLER_ASSET_SUFFIX):
            installer_asset = asset
            break

    if not installer_asset:
        if is_manual:
            QMessageBox.warning(
                parent, "Update Error", "No Windows installer asset found in the latest release."
            )
        return

    # Truncate release notes
    if len(body) > 1500:
        body = body[:1500] + "...\n(Read more on GitHub)"

    msg = QMessageBox(parent)
    msg.setWindowTitle("Update Available")
    msg.setText(f"A new version of {app_info.APP_NAME} is available!")
    msg.setInformativeText(
        f"Current version: {app_info.APP_VERSION}\n"
        f"Latest version: {tag_name}\n\n"
        f"Release Notes:\n{body}"
    )

    update_btn = msg.addButton("Update Now", QMessageBox.ButtonRole.AcceptRole)
    view_btn = msg.addButton("View Release", QMessageBox.ButtonRole.ActionRole)
    msg.addButton("Later", QMessageBox.ButtonRole.RejectRole)

    msg.exec()

    if msg.clickedButton() == view_btn:
        webbrowser.open(html_url)
    elif msg.clickedButton() == update_btn:
        download_url = installer_asset.get("browser_download_url", "")
        asset_name = installer_asset.get("name", "")
        if not download_url.startswith("https://"):
            QMessageBox.warning(parent, "Update Error", "Invalid installer download URL.")
            return
        if not (asset_name.startswith(app_info.INSTALLER_ASSET_PREFIX) and asset_name.endswith(app_info.INSTALLER_ASSET_SUFFIX)):
            QMessageBox.warning(parent, "Update Error", "Invalid installer asset name.")
            return
        _start_download(parent, download_url, asset_name)


def _start_download(parent, download_url: str, asset_name: str):
    """Start downloading the installer."""
    progress_dialog = QProgressDialog("Downloading update...", "Cancel", 0, 0, parent)
    progress_dialog.setWindowTitle("Downloading")
    progress_dialog.setModal(True)
    progress_dialog.show()

    worker = DownloadUpdateWorker(download_url, asset_name)

    def on_complete(filepath):
        progress_dialog.accept()
        reply = QMessageBox.question(
            parent,
            "Download Complete",
            "Update downloaded. WAC-Crawl will close and the installer will start.\n\nInstall now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Launch the installer
            subprocess.Popen([filepath])
            # Exit the app
            QApplication.quit()

    def on_error(err_msg):
        progress_dialog.accept()
        QMessageBox.warning(parent, "Download Error", f"Could not download update:\n{err_msg}")

    def on_cancel():
        worker.is_cancelled = True

    worker.signals.download_complete.connect(on_complete)
    worker.signals.error.connect(on_error)
    progress_dialog.canceled.connect(on_cancel)

    QThreadPool.globalInstance().start(worker)


class UpdateManager(QObject):
    """Manager to handle update checks for the main window."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent

    def check_for_updates(self, is_manual: bool = False):
        """Check for updates in a background thread."""
        worker = UpdateCheckWorker()

        def on_update_available(data):
            show_update_dialog(self.parent_window, data, is_manual)

        def on_up_to_date():
            if is_manual:
                QMessageBox.information(
                    self.parent_window,
                    "Up to Date",
                    f"You are using the latest version ({app_info.APP_VERSION}).",
                )

        def on_error(err_msg):
            if is_manual:
                QMessageBox.warning(
                    self.parent_window, "Update Error", f"Could not check for updates:\n{err_msg}"
                )

        worker.signals.update_available.connect(on_update_available)
        worker.signals.up_to_date.connect(on_up_to_date)
        worker.signals.error.connect(on_error)

        QThreadPool.globalInstance().start(worker)

"""About dialog."""

from PySide6.QtWidgets import QMessageBox
import app_info

def show_about_dialog(parent=None):
    """Show the About dialog."""
    QMessageBox.about(
        parent,
        "About",
        f"<b>{app_info.APP_NAME}</b><br><br>"
        f"Version: {app_info.APP_VERSION}<br><br>"
        f"Automated LLDP neighbor crawler for Huawei WAC-managed APs.<br><br>"
        f"Author: M Riyadh Azhar<br>"
        f"GitHub: <a href='{app_info.RELEASES_URL}'>{app_info.GITHUB_REPO}</a><br>"
        f"License: MIT"
    )

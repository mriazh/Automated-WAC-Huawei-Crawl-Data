"""About dialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

import app_info


class AboutDialog(QDialog):
    """Custom frameless About dialog styled with a dark theme."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(360, 420)
        self.resize(380, 440)
        is_light = False
        if parent is not None and hasattr(parent, '_theme_toggle'):
            if parent._theme_toggle.current_theme == "light":
                is_light = True

        if is_light:
            bg_color = "#ffffff"
            text_color = "#1e1e2e"
            self._accent_color = "#1e66f5"
            close_text_color = "#1e1e2e"
            close_bg_color = "#e0e0e0"
            border_color = "#dcdcdc"
        else:
            bg_color = "#1e1e2e"
            text_color = "#cdd6f4"
            self._accent_color = "#89b4fa"
            close_text_color = "#cdd6f4"
            close_bg_color = "#313244"
            border_color = "#45475a"

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 1px solid {border_color};
            }}
            QLabel {{
                color: {text_color};
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10pt;
            }}
            QLabel#titleLabel {{
                font-size: 12pt;
                font-weight: bold;
                color: {text_color};
            }}
            QLabel#appNameLabel {{
                font-size: 11pt;
                color: {text_color};
            }}
            QLabel#dependencyLabel {{
                color: {self._accent_color};
            }}
            QPushButton#closeBtn {{
                background: {close_bg_color};
                color: {close_text_color};
                font-size: 14pt;
                border: none;
                border-radius: 4px;
                padding: 0px;
                font-weight: bold;
            }}
            QPushButton#closeBtn:hover {{
                color: #ffffff;
                background: #e81123;
            }}
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 20)
        layout.setSpacing(8)

        # Top row: Title and Close button
        top_layout = QHBoxLayout()
        title_label = QLabel("About")
        title_label.setObjectName("titleLabel")
        top_layout.addWidget(title_label)

        top_layout.addStretch()

        close_btn = QPushButton("X")
        close_btn.setObjectName("closeBtn")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close_btn.clicked.connect(self.accept)
        top_layout.addWidget(close_btn)

        layout.addLayout(top_layout)
        layout.addSpacing(5)

        # App Info
        app_name = QLabel(app_info.APP_NAME)
        app_name.setObjectName("appNameLabel")
        layout.addWidget(app_name)

        version_label = QLabel(f"Version: {app_info.APP_VERSION}")
        layout.addWidget(version_label)

        date_label = QLabel(f"Build: {getattr(app_info, 'APP_BUILD_DATE', '')}")
        layout.addWidget(date_label)

        license_label = QLabel("License: MIT")
        layout.addWidget(license_label)
        layout.addSpacing(10)

        # Description
        desc_label = QLabel("Automated LLDP neighbor crawler for Huawei WAC-managed APs.")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        layout.addSpacing(10)

        # Tech/dependency info list
        deps = [
            "Python",
            "PySide6",
            "Paramiko",
            "Cryptography",
            "PyInstaller"
        ]

        for dep in deps:
            dep_label = QLabel(dep)
            dep_label.setObjectName("dependencyLabel")
            layout.addWidget(dep_label)

        layout.addStretch()

        # Links and Copyright
        links_text = (
            f"&copy; M Riyadh Azhar | "
            f"<a href='https://github.com/{app_info.GITHUB_REPO}' style='color: {self._accent_color}; text-decoration: none;'>GitHub</a> | "
            f"<a href='{app_info.RELEASES_URL}' style='color: {self._accent_color}; text-decoration: none;'>Releases</a>"
        )
        links_label = QLabel(links_text)
        links_label.setOpenExternalLinks(True)
        links_label.setWordWrap(True)
        layout.addWidget(links_label)

        # Enable dragging the frameless window
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


def show_about_dialog(parent=None):
    """Show the About dialog."""
    dialog = AboutDialog(parent)
    dialog.exec()

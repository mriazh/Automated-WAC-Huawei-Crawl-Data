"""Dark and light QSS stylesheets and theme toggle widget.

Provides DARK_STYLESHEET and LIGHT_STYLESHEET as QSS strings,
a ThemeToggle button widget, and an apply_theme helper function.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QPushButton


DARK_STYLESHEET = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {
    border: 1px solid #89b4fa;
}

QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #b4d0fb;
}

QPushButton:pressed {
    background-color: #74a8fc;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

QLabel {
    background-color: transparent;
    color: #cdd6f4;
}

QCheckBox {
    color: #cdd6f4;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #45475a;
    border-radius: 3px;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QProgressBar {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}

QListWidget {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
}

QListWidget::item {
    padding: 4px;
}

QListWidget::item:selected {
    background-color: #45475a;
}

QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QMainWindow {
    background-color: #1e1e2e;
}

QFormLayout {
    background-color: transparent;
}
"""

LIGHT_STYLESHEET = """
QWidget {
    background-color: #ffffff;
    color: #1e1e2e;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox {
    background-color: #f5f5f5;
    color: #1e1e2e;
    border: 1px solid #dcdcdc;
    border-radius: 4px;
    padding: 6px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {
    border: 1px solid #1e66f5;
}

QPushButton {
    background-color: #1e66f5;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #4580f7;
}

QPushButton:pressed {
    background-color: #1854d1;
}

QPushButton:disabled {
    background-color: #dcdcdc;
    color: #9ca0b0;
}

QLabel {
    background-color: transparent;
    color: #1e1e2e;
}

QCheckBox {
    color: #1e1e2e;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #dcdcdc;
    border-radius: 3px;
    background-color: #f5f5f5;
}

QCheckBox::indicator:checked {
    background-color: #1e66f5;
    border-color: #1e66f5;
}

QProgressBar {
    background-color: #f5f5f5;
    border: 1px solid #dcdcdc;
    border-radius: 4px;
    text-align: center;
    color: #1e1e2e;
}

QProgressBar::chunk {
    background-color: #1e66f5;
    border-radius: 3px;
}

QListWidget {
    background-color: #f5f5f5;
    color: #1e1e2e;
    border: 1px solid #dcdcdc;
    border-radius: 4px;
}

QListWidget::item {
    padding: 4px;
}

QListWidget::item:selected {
    background-color: #e0e0e0;
}

QScrollBar:vertical {
    background-color: #ffffff;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #dcdcdc;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #c0c0c0;
}

QMainWindow {
    background-color: #ffffff;
}

QFormLayout {
    background-color: transparent;
}
"""


class ThemeToggle(QPushButton):
    """Toggle button that switches between dark and light themes.

    Emits theme_changed(str) signal with "dark" or "light" when toggled.
    Displays a moon icon (dark mode active) or sun icon (light mode active).
    """

    theme_changed = Signal(str)

    def __init__(self, initial_theme: str = "dark", parent=None):
        """Initialize the theme toggle button.

        Args:
            initial_theme: Starting theme, either "dark" or "light".
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._current_theme = initial_theme if initial_theme in ("dark", "light") else "dark"
        self._update_display()
        self.clicked.connect(self._toggle)
        self.setFixedSize(40, 40)
        self.setToolTip("Toggle theme")

    @property
    def current_theme(self) -> str:
        """Return the currently active theme name."""
        return self._current_theme

    def _toggle(self) -> None:
        """Switch to the opposite theme and emit signal."""
        self._current_theme = "light" if self._current_theme == "dark" else "dark"
        self._update_display()
        self.theme_changed.emit(self._current_theme)

    def _update_display(self) -> None:
        """Update button text to reflect current theme state."""
        if self._current_theme == "dark":
            self.setText("\U0001f319")  # 🌙 moon - indicates dark mode is active
        else:
            self.setText("\u2600\ufe0f")  # ☀️ sun - indicates light mode is active


def apply_theme(app: QApplication, theme_name: str) -> None:
    """Apply a theme stylesheet to the application.

    Args:
        app: The QApplication instance to style.
        theme_name: Either "dark" or "light". Defaults to dark if invalid.
    """
    if theme_name == "light":
        app.setStyleSheet(LIGHT_STYLESHEET)
    else:
        app.setStyleSheet(DARK_STYLESHEET)

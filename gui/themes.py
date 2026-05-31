"""Dark and light QSS stylesheets and theme toggle widget.

Provides DARK_STYLESHEET and LIGHT_STYLESHEET as QSS strings,
a ThemeToggle button widget, and an apply_theme helper function.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QPushButton, QWidget


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
    padding-left: 2px;
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
    padding: 0px;
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
    padding-left: 2px;
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
    padding: 0px;
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


class ThemeToggle(QWidget):
    """Animated toggle switch for dark/light theme.

    Pill-shaped slider with sun/moon icon that slides between positions.
    Emits theme_changed(str) signal with "dark" or "light" when toggled.
    """

    theme_changed = Signal(str)

    def __init__(self, initial_theme: str = "dark", parent=None):
        super().__init__(parent)
        self._current_theme = initial_theme if initial_theme in ("dark", "light") else "dark"
        self.setFixedSize(56, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Toggle dark/light theme")

    @property
    def current_theme(self) -> str:
        """Return the currently active theme name."""
        return self._current_theme

    def mousePressEvent(self, event) -> None:
        """Toggle theme on click."""
        self._current_theme = "light" if self._current_theme == "dark" else "dark"
        self.update()
        self.theme_changed.emit(self._current_theme)

    def paintEvent(self, event) -> None:
        """Draw the toggle switch with pill shape and sliding circle."""
        from PySide6.QtGui import QPainter, QColor, QPen, QBrush

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h // 2
        circle_margin = 3
        circle_size = h - (circle_margin * 2)

        if self._current_theme == "dark":
            # Dark mode: match dark theme accent (#89b4fa)
            track_color = QColor("#313244")
            circle_color = QColor("#89b4fa")
            circle_x = w - circle_size - circle_margin  # Right side
        else:
            # Light mode: match light theme accent (#1e66f5)
            track_color = QColor("#dcdcdc")
            circle_color = QColor("#1e66f5")
            circle_x = circle_margin  # Left side

        # Draw track (pill shape)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(0, 0, w, h, radius, radius)

        # Draw circle
        painter.setBrush(QBrush(circle_color))
        painter.drawEllipse(int(circle_x), circle_margin, circle_size, circle_size)

        # Draw icon inside circle
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        cx = int(circle_x) + circle_size // 2
        cy = circle_margin + circle_size // 2
        icon_r = circle_size // 4

        if self._current_theme == "dark":
            # Moon crescent
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - icon_r, cy - icon_r, icon_r * 2, icon_r * 2)
            painter.setBrush(QBrush(circle_color))
            painter.drawEllipse(cx - icon_r + 3, cy - icon_r - 2, icon_r * 2, icon_r * 2)
        else:
            # Sun rays
            import math
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.setBrush(QBrush(QColor("#ffffff")))
            painter.drawEllipse(cx - 3, cy - 3, 6, 6)
            for i in range(8):
                angle = i * math.pi / 4
                x1 = cx + int(5 * math.cos(angle))
                y1 = cy + int(5 * math.sin(angle))
                x2 = cx + int(7 * math.cos(angle))
                y2 = cy + int(7 * math.sin(angle))
                painter.drawLine(x1, y1, x2, y2)

        painter.end()


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
    # Process events immediately to reduce visual flash
    app.processEvents()

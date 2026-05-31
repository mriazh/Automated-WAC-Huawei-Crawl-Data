"""Login page widget for SSH credential entry and connection verification.

Provides a form-based login interface with host, port, username, and password
fields, remember-me persistence, and async connection verification via
ConnectVerifier running on QThreadPool.
"""

import logging

from PySide6.QtCore import Qt, QThreadPool, Signal
from PySide6.QtGui import QBrush, QColor, QIntValidator, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.config_store import ConfigStore
from gui.encryption import DecryptionError, EncryptionService
from gui.validators import validate_login_fields
from gui.workers import ConnectVerifier

logger = logging.getLogger(__name__)


class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal when pressed."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()
        super().mousePressEvent(event)


class StyledCheckBox(QWidget):
    """Custom checkbox that renders its own box + checkmark.

    Works reliably across dark/light themes without QSS indicator issues.
    """

    toggled = Signal(bool)

    # Theme accent colors (same as Connect button)
    DARK_ACCENT = "#89b4fa"
    LIGHT_ACCENT = "#1e66f5"

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._checked = False
        self._text = text
        self._accent_color = QColor(self.DARK_ACCENT)
        self.setFixedHeight(24)
        self.setFixedWidth(140)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        self._checked = checked
        self.update()

    def set_theme(self, theme: str) -> None:
        """Update accent color based on current theme."""
        if theme == "light":
            self._accent_color = QColor(self.LIGHT_ACCENT)
        else:
            self._accent_color = QColor(self.DARK_ACCENT)
        self.update()

    def mousePressEvent(self, event) -> None:
        self._checked = not self._checked
        self.update()
        self.toggled.emit(self._checked)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        text_color = self.palette().text().color()
        box_size = 16
        margin_y = (self.height() - box_size) // 2

        # Draw box
        if self._checked:
            painter.setPen(QPen(self._accent_color, 2))
            painter.setBrush(QBrush(self._accent_color))
        else:
            painter.setPen(QPen(text_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(2, margin_y, box_size, box_size, 3, 3)

        # Draw checkmark if checked
        if self._checked:
            painter.setPen(QPen(QColor("#ffffff"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(6, margin_y + 8, 9, margin_y + 12)
            painter.drawLine(9, margin_y + 12, 14, margin_y + 5)

        # Draw text
        painter.setPen(QPen(text_color))
        painter.drawText(box_size + 10, 0, self.width() - box_size - 10, self.height(),
                         Qt.AlignmentFlag.AlignVCenter, self._text)

        painter.end()


class LoginPage(QWidget):
    """Login form with SSH connection verification and remember-me logic.

    Emits login_success(object) signal with the SSHSession on successful
    connection. Stores host/port/username as properties for display on
    the crawl page.
    """

    login_success = Signal(object)  # Emits SSHSession on successful connection

    def __init__(
        self,
        config_store: ConfigStore,
        encryption_service: EncryptionService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config_store = config_store
        self._encryption_service = encryption_service

        self._connected_host: str = ""
        self._connected_port: str = ""
        self._connected_username: str = ""
        self._password_visible = False

        self._setup_ui()
        self._load_saved_credentials()

        # Set initial checkbox theme from config
        config = self._config_store.load()
        self._remember_checkbox.set_theme(config.theme)

    @property
    def connected_host(self) -> str:
        return self._connected_host

    @property
    def connected_port(self) -> str:
        return self._connected_port

    @property
    def connected_username(self) -> str:
        return self._connected_username

    def _setup_ui(self) -> None:
        """Build the login form UI layout — compact, centered."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # Center the form vertically
        outer_layout.addStretch(2)

        # Container widget for the form (fixed max width)
        form_container = QWidget()
        form_container.setMaximumWidth(400)
        form_layout = QVBoxLayout(form_container)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(30, 20, 30, 20)

        # Title
        title = QLabel("SSH Connection")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 8px;")
        form_layout.addWidget(title)

        # Form fields
        fields_layout = QFormLayout()
        fields_layout.setSpacing(10)

        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("e.g. 192.168.1.1")
        fields_layout.addRow("Host:", self._host_input)

        self._port_input = QLineEdit()
        self._port_input.setPlaceholderText("e.g. 22")
        self._port_input.setValidator(QIntValidator(1, 65535))
        fields_layout.addRow("Port:", self._port_input)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("SSH username")
        fields_layout.addRow("Username:", self._username_input)

        # Password with reveal toggle
        password_layout = QHBoxLayout()
        password_layout.setSpacing(4)
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("SSH password")
        password_layout.addWidget(self._password_input)

        self._reveal_btn = QPushButton()
        self._reveal_btn.setFixedSize(32, 32)
        self._reveal_btn.setToolTip("Show/hide password")
        self._reveal_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; }"
            "QPushButton:hover { background-color: rgba(128,128,128,0.15); border-radius: 4px; }"
        )
        self._reveal_btn.clicked.connect(self._toggle_password_visibility)
        self._update_reveal_icon()
        password_layout.addWidget(self._reveal_btn)

        fields_layout.addRow("Password:", password_layout)
        form_layout.addLayout(fields_layout)

        # Remember me checkbox
        self._remember_checkbox = StyledCheckBox("Remember me")
        self._remember_checkbox.setChecked(False)
        form_layout.addWidget(self._remember_checkbox)

        # Connect button
        self._connect_button = QPushButton("Connect")
        self._connect_button.setFixedHeight(36)
        self._connect_button.clicked.connect(self._on_connect_clicked)
        form_layout.addWidget(self._connect_button)

        # Enter key in any input field triggers Connect
        self._host_input.returnPressed.connect(self._on_connect_clicked)
        self._port_input.returnPressed.connect(self._on_connect_clicked)
        self._username_input.returnPressed.connect(self._on_connect_clicked)
        self._password_input.returnPressed.connect(self._on_connect_clicked)

        # Error label (hidden by default) — click to copy
        self._error_label = ClickableLabel("")
        self._error_label.setStyleSheet("color: #f38ba8; font-size: 12px;")
        self._error_label.setWordWrap(True)
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._error_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._error_label.hide()
        self._error_label.clicked.connect(self._on_error_clicked)
        form_layout.addWidget(self._error_label)

        # Center the form horizontally
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(form_container)
        h_layout.addStretch()
        outer_layout.addLayout(h_layout)

        outer_layout.addStretch(3)

    def _toggle_password_visibility(self) -> None:
        """Toggle password field between hidden and visible."""
        self._password_visible = not self._password_visible
        if self._password_visible:
            self._password_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._update_reveal_icon()

    def _update_reveal_icon(self) -> None:
        """Update the reveal button icon based on current visibility state."""
        from gui.icons import icon_eye_closed, icon_eye_open

        if self._password_visible:
            self._reveal_btn.setIcon(icon_eye_closed())
        else:
            self._reveal_btn.setIcon(icon_eye_open())

    def _load_saved_credentials(self) -> None:
        """Load and pre-fill credentials from ConfigStore if remember-me was enabled."""
        config = self._config_store.load()

        if not config.remember_me:
            return

        self._host_input.setText(config.host)
        self._port_input.setText(config.port)
        self._username_input.setText(config.username)

        if config.encrypted_password:
            try:
                password = self._encryption_service.decrypt(config.encrypted_password)
                self._password_input.setText(password)
            except DecryptionError:
                logger.warning("Failed to decrypt stored password. Clearing credentials.")
                self._config_store.clear_credentials()
                self._host_input.clear()
                self._port_input.clear()
                self._username_input.clear()
                self._password_input.clear()
                self._remember_checkbox.setChecked(False)
                return

        self._remember_checkbox.setChecked(True)

    def _on_connect_clicked(self) -> None:
        """Handle Connect button click: validate fields then start verification."""
        self._error_label.hide()

        host = self._host_input.text()
        port = self._port_input.text()
        username = self._username_input.text()
        password = self._password_input.text()

        errors = validate_login_fields(host, port, username, password)
        if errors:
            error_messages = "; ".join(errors.values())
            self._show_error(error_messages)
            return

        self._set_loading(True)

        port_int = int(port.strip())
        verifier = ConnectVerifier(
            host=host.strip(),
            port=port_int,
            username=username.strip(),
            password=password,
            ssh_timeout=15,
        )
        verifier.signals.connected.connect(self._on_connect_success)
        verifier.signals.failed.connect(self._on_connect_failed)

        self._current_verifier = verifier
        QThreadPool.globalInstance().start(verifier)

    def _on_connect_success(self, session: object) -> None:
        """Handle successful SSH connection."""
        self._set_loading(False)

        self._connected_host = self._host_input.text().strip()
        self._connected_port = self._port_input.text().strip()
        self._connected_username = self._username_input.text().strip()

        if self._remember_checkbox.isChecked():
            self._save_credentials()
        else:
            self._clear_credentials()

        self.login_success.emit(session)

    def _on_connect_failed(self, error_message: str) -> None:
        """Handle failed SSH connection — map error to user-facing message."""
        self._set_loading(False)
        # Log raw error for debugging
        logger.info("Raw SSH error: %s", error_message)
        user_message = self._map_error_message(error_message)
        self._show_error(user_message)

    def _set_loading(self, loading: bool) -> None:
        """Toggle loading state."""
        if loading:
            self._connect_button.setEnabled(False)
            self._connect_button.setText("Connecting...")
            # Keep focus on the page itself to prevent jumping to host input
            self.setFocus()
        else:
            self._connect_button.setEnabled(True)
            self._connect_button.setText("Connect")

    def _show_error(self, message: str) -> None:
        """Display error message and copy to clipboard on click."""
        self._error_label.setText(message)
        self._error_label.show()

    def _on_error_clicked(self) -> None:
        """Copy error text to clipboard when error label is clicked."""
        if self._error_label.text():
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self._error_label.text())
            # Brief visual feedback
            original = self._error_label.text()
            self._error_label.setText("✓ Copied to clipboard!")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self._error_label.setText(original))

    def _save_credentials(self) -> None:
        """Save current credentials to ConfigStore with encrypted password."""
        config = self._config_store.load()
        config.host = self._host_input.text().strip()
        config.port = self._port_input.text().strip()
        config.username = self._username_input.text().strip()
        config.encrypted_password = self._encryption_service.encrypt(
            self._password_input.text()
        )
        config.remember_me = True
        self._config_store.save(config)

    def _clear_credentials(self) -> None:
        """Clear stored credentials from ConfigStore."""
        self._config_store.clear_credentials()

    @staticmethod
    def _map_error_message(error: str) -> str:
        """Map error codes from ConnectVerifier to user-facing messages.

        Error codes:
          - host_port_timeout: TCP/SSH timed out (host unreachable or port closed)
          - host_port_refused: TCP connection refused
          - host_port_error:*: Other socket errors
          - auth_failed: Username or password wrong (host+port confirmed OK)
          - ssh_protocol_error: Port open but not SSH service
          - not_wac:*: SSH OK but not a WAC device
          - unexpected:*: Unexpected errors
        """
        if error == "host_port_timeout":
            return (
                "Connection failed: Host/port not reachable\n"
                "(Connection timed out — check host, port, or VPN)"
            )
        if error == "host_port_refused":
            return (
                "Connection failed: Port not open\n"
                "(Host exists but SSH is not running on this port)"
            )
        if error.startswith("host_port_error:"):
            detail = error.split(":", 1)[1]
            return (
                f"Connection failed: Cannot reach host\n"
                f"({detail})"
            )
        if error == "auth_failed":
            return (
                "Connection failed: Invalid username or password\n"
                "(Host and port are correct, check your credentials)"
            )
        if error == "ssh_protocol_error":
            return (
                "Connection failed: Not an SSH server\n"
                "(Port is open but not running SSH — check host or port)"
            )
        if error.startswith("not_wac:"):
            detail = error.split(":", 1)[1]
            return (
                "Connection failed: Not a WAC device\n"
                f"(SSH login OK but device did not respond as WAC: {detail})"
            )
        if error.startswith("unexpected:"):
            detail = error.split(":", 1)[1]
            return f"Connection failed: {detail}"

        return f"Connection failed: {error}"

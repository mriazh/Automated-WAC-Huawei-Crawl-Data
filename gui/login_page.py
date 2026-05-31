"""Login page widget for SSH credential entry and connection verification.

Provides a form-based login interface with host, port, username, and password
fields, remember-me persistence, and async connection verification via
ConnectVerifier running on QThreadPool.
"""

import logging

from PySide6.QtCore import QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
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
        """Initialize LoginPage with config store and encryption service.

        Args:
            config_store: ConfigStore instance for credential persistence.
            encryption_service: EncryptionService for password encrypt/decrypt.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._config_store = config_store
        self._encryption_service = encryption_service

        # Connection info properties (set on successful login)
        self._connected_host: str = ""
        self._connected_port: str = ""
        self._connected_username: str = ""

        self._setup_ui()
        self._load_saved_credentials()

    @property
    def connected_host(self) -> str:
        """Return the host used for the last successful connection."""
        return self._connected_host

    @property
    def connected_port(self) -> str:
        """Return the port used for the last successful connection."""
        return self._connected_port

    @property
    def connected_username(self) -> str:
        """Return the username used for the last successful connection."""
        return self._connected_username

    def _setup_ui(self) -> None:
        """Build the login form UI layout."""
        layout = QVBoxLayout(self)

        # Form layout for credential fields
        form_layout = QFormLayout()

        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("e.g. 192.168.1.1")
        self._host_input.setObjectName("host_input")
        form_layout.addRow("Host:", self._host_input)

        self._port_input = QLineEdit()
        self._port_input.setPlaceholderText("e.g. 22")
        self._port_input.setObjectName("port_input")
        form_layout.addRow("Port:", self._port_input)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("SSH username")
        self._username_input.setObjectName("username_input")
        form_layout.addRow("Username:", self._username_input)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("SSH password")
        self._password_input.setObjectName("password_input")
        form_layout.addRow("Password:", self._password_input)

        layout.addLayout(form_layout)

        # Remember me checkbox
        self._remember_checkbox = QCheckBox("Remember me")
        self._remember_checkbox.setChecked(False)
        self._remember_checkbox.setObjectName("remember_checkbox")
        layout.addWidget(self._remember_checkbox)

        # Connect button
        self._connect_button = QPushButton("Connect")
        self._connect_button.setObjectName("connect_button")
        self._connect_button.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self._connect_button)

        # Error label (hidden by default, red text)
        self._error_label = QLabel("")
        self._error_label.setObjectName("error_label")
        self._error_label.setStyleSheet("color: red;")
        self._error_label.setWordWrap(True)
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Add stretch to push content to top
        layout.addStretch()

    def _load_saved_credentials(self) -> None:
        """Load and pre-fill credentials from ConfigStore if remember-me was enabled."""
        config = self._config_store.load()

        if not config.remember_me:
            return

        self._host_input.setText(config.host)
        self._port_input.setText(config.port)
        self._username_input.setText(config.username)

        # Decrypt stored password
        if config.encrypted_password:
            try:
                password = self._encryption_service.decrypt(config.encrypted_password)
                self._password_input.setText(password)
            except DecryptionError:
                logger.warning(
                    "Failed to decrypt stored password. Clearing credentials."
                )
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
        # Hide previous error
        self._error_label.hide()

        host = self._host_input.text()
        port = self._port_input.text()
        username = self._username_input.text()
        password = self._password_input.text()

        # Validate fields
        errors = validate_login_fields(host, port, username, password)
        if errors:
            error_messages = "; ".join(errors.values())
            self._show_error(error_messages)
            return

        # Enter loading state
        self._set_loading(True)

        # Launch ConnectVerifier on thread pool
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

        # Keep reference to prevent garbage collection
        self._current_verifier = verifier
        QThreadPool.globalInstance().start(verifier)

    def _on_connect_success(self, session: object) -> None:
        """Handle successful SSH connection.

        Args:
            session: The SSHSession object from ConnectVerifier.
        """
        self._set_loading(False)

        # Store connection info for crawl page display
        self._connected_host = self._host_input.text().strip()
        self._connected_port = self._port_input.text().strip()
        self._connected_username = self._username_input.text().strip()

        # Handle remember-me persistence
        if self._remember_checkbox.isChecked():
            self._save_credentials()
        else:
            self._clear_credentials()

        # Emit success signal with the session
        self.login_success.emit(session)

    def _on_connect_failed(self, error_message: str) -> None:
        """Handle failed SSH connection — map error to user-facing message.

        Args:
            error_message: Raw error string from ConnectVerifier.
        """
        self._set_loading(False)

        user_message = self._map_error_message(error_message)
        self._show_error(user_message)

    def _set_loading(self, loading: bool) -> None:
        """Toggle loading state: disable button and change text during connection.

        Args:
            loading: True to enter loading state, False to exit.
        """
        if loading:
            self._connect_button.setEnabled(False)
            self._connect_button.setText("Connecting...")
        else:
            self._connect_button.setEnabled(True)
            self._connect_button.setText("Connect")

    def _show_error(self, message: str) -> None:
        """Display error message in the error label.

        Args:
            message: Error text to display.
        """
        self._error_label.setText(message)
        self._error_label.show()

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
        """Map SSH error strings to user-facing messages.

        Args:
            error: Raw error string from the SSH connection attempt.

        Returns:
            User-friendly error message.
        """
        error_lower = error.lower()

        if "authentication failed" in error_lower:
            return "Connection failed: Authentication failed"
        if "unable to connect" in error_lower:
            return "Connection failed: Host unreachable"
        if "timed out" in error_lower:
            return "Connection failed: Connection timed out"

        # For unrecognized errors, show the raw message
        return error

"""Main application window for WAC Huawei LLDP Crawl Data GUI.

Provides the top-level QMainWindow with a QStackedWidget for page navigation
between LoginPage and CrawlPage, a ThemeToggle in the toolbar area, and
graceful close handling during active crawl operations.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from gui.config_store import ConfigStore
from gui.crawl_page import CrawlPage
from gui.encryption import EncryptionService
from gui.login_page import LoginPage
from gui.themes import ThemeToggle, apply_theme

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with stacked page navigation and theme toggle.

    Manages the lifecycle of LoginPage and CrawlPage, handles theme
    persistence, and provides graceful shutdown during active crawls.
    """

    def __init__(
        self,
        config_store: ConfigStore,
        encryption_service: EncryptionService,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize MainWindow with config store and encryption service.

        Args:
            config_store: ConfigStore instance for persisting preferences.
            encryption_service: EncryptionService for credential handling.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._config_store = config_store
        self._encryption_service = encryption_service
        self._session = None
        self._crawl_page: CrawlPage | None = None

        self._setup_window()
        self._setup_toolbar()
        self._setup_pages()
        self._apply_stored_theme()

    def _setup_window(self) -> None:
        """Configure window title, size, and icon."""
        self.setWindowTitle("WAC Huawei LLDP Crawl Data")
        self.setMinimumSize(500, 400)
        self.resize(550, 450)

        # Set window icon from assets/huawei.svg
        import os
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "huawei.svg")
        if os.path.exists(icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))

    def _setup_toolbar(self) -> None:
        """Create toolbar with ThemeToggle positioned at the top-right."""
        toolbar = QToolBar("Theme")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)

        # Load stored theme to initialize toggle state
        config = self._config_store.load()
        initial_theme = config.theme if config.theme in ("dark", "light") else "dark"

        # Add spacer to push toggle to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        # Add theme toggle
        self._theme_toggle = ThemeToggle(initial_theme=initial_theme)
        self._theme_toggle.theme_changed.connect(self._on_theme_changed)
        toolbar.addWidget(self._theme_toggle)

        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _setup_pages(self) -> None:
        """Create QStackedWidget and add the LoginPage."""
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Create login page (always present)
        self._login_page = LoginPage(
            config_store=self._config_store,
            encryption_service=self._encryption_service,
        )
        self._login_page.login_success.connect(self._on_login_success)
        self._stack.addWidget(self._login_page)

    def _apply_stored_theme(self) -> None:
        """Apply the theme stored in ConfigStore before showing the window."""
        config = self._config_store.load()
        theme = config.theme if config.theme in ("dark", "light") else "dark"
        app = self._get_application()
        if app:
            apply_theme(app, theme)

    def _on_theme_changed(self, theme_name: str) -> None:
        """Handle theme toggle: apply theme and persist preference."""
        app = self._get_application()
        if app:
            apply_theme(app, theme_name)

        # Update login page checkbox theme
        if hasattr(self._login_page, '_remember_checkbox'):
            self._login_page._remember_checkbox.set_theme(theme_name)

        # Persist theme preference
        config = self._config_store.load()
        config.theme = theme_name
        self._config_store.save(config)

        # Update crawl page theme if it exists
        if self._crawl_page is not None:
            self._crawl_page.set_theme(theme_name)

    def _on_login_success(self, session: object) -> None:
        """Handle successful login: create CrawlPage and switch to it.

        Args:
            session: The SSHSession object from ConnectVerifier.
        """
        self._session = session

        # Build connection info from login page properties
        connection_info = {
            "host": self._login_page.connected_host,
            "port": self._login_page.connected_port,
            "username": self._login_page.connected_username,
        }

        # Create CrawlPage dynamically with the active session
        self._crawl_page = CrawlPage(
            session=session,
            config_store=self._config_store,
            connection_info=connection_info,
        )
        self._crawl_page.logout_requested.connect(self._on_logout_requested)

        # Apply current theme to crawl page
        self._crawl_page.set_theme(self._theme_toggle.current_theme)

        # Add to stack and switch
        self._stack.addWidget(self._crawl_page)
        self._stack.setCurrentWidget(self._crawl_page)

    def _on_logout_requested(self) -> None:
        """Handle logout: close SSH session, destroy CrawlPage, show LoginPage."""
        # Close SSH session
        self._disconnect_session()

        # Remove and destroy CrawlPage
        if self._crawl_page is not None:
            self._stack.removeWidget(self._crawl_page)
            self._crawl_page.deleteLater()
            self._crawl_page = None

        # Switch back to LoginPage
        self._stack.setCurrentWidget(self._login_page)

    def _disconnect_session(self) -> None:
        """Safely close the SSH session, ignoring errors."""
        if self._session is not None:
            try:
                self._session.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting SSH session: %s", e)
            finally:
                self._session = None

    def closeEvent(self, event) -> None:
        """Handle window close: confirm if crawl running, else close gracefully.

        If a crawl is in progress, shows a confirmation dialog. On confirm,
        stops the worker, saves partial results, closes SSH, and exits.
        On cancel, the close is ignored and the crawl continues.

        Args:
            event: The QCloseEvent.
        """
        # Check if a crawl is running
        if self._crawl_page is not None and self._crawl_page._is_crawling:
            reply = QMessageBox.question(
                self,
                "Confirm Close",
                "Are you sure? Crawl in progress.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

            # User confirmed: stop worker, save partial results, close SSH
            self._graceful_shutdown()

        else:
            # No crawl running: just close SSH and exit
            self._disconnect_session()

        event.accept()

    def _graceful_shutdown(self) -> None:
        """Stop crawl worker, save partial results, and close SSH session."""
        if self._crawl_page is not None and self._crawl_page._worker is not None:
            worker = self._crawl_page._worker
            worker.request_stop()

            # Wait up to 10 seconds for worker to finish
            if not worker.wait(10000):
                worker.terminate()
                worker.wait(2000)

            # Save partial results
            self._crawl_page._save_partial_results()

        # Close SSH session
        self._disconnect_session()

    @staticmethod
    def _get_application():
        """Return the current QApplication instance, or None."""
        from PySide6.QtWidgets import QApplication

        return QApplication.instance()

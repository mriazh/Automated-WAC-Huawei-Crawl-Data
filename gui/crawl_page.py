"""Crawl page widget for WAC Huawei LLDP Crawl Data GUI.

Provides file input selection, crawl execution control, progress monitoring,
and live result logging with color-coded entries.
"""

import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import Config
from gui.config_store import ConfigStore
from gui.validators import validate_paths
from gui.workers import CrawlWorker
from output import read_existing_csv, write_csv
from parsers import parse_ap_list, parse_switch_list
from ssh_client import SSHSession

logger = logging.getLogger(__name__)

# Log entry colors for dark theme
_DARK_GREEN = QColor("#a6e3a1")
_DARK_RED = QColor("#f38ba8")
_DARK_YELLOW = QColor("#f9e2af")

# Log entry colors for light theme
_LIGHT_GREEN = QColor("#40a02b")
_LIGHT_RED = QColor("#d20f39")
_LIGHT_YELLOW = QColor("#df8e1d")


class CrawlPage(QWidget):
    """Main crawl page with file inputs, progress, and live log.

    Provides controls for selecting input files, starting/stopping crawl,
    monitoring progress, and viewing color-coded live results.
    """

    logout_requested = Signal()

    def __init__(
        self,
        session: SSHSession,
        config_store: ConfigStore,
        connection_info: dict,
        parent=None,
    ):
        """Initialize CrawlPage.

        Args:
            session: Active SSH session to the WAC controller.
            config_store: ConfigStore instance for persisting preferences.
            connection_info: Dict with 'host', 'port', 'username' keys.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._session = session
        self._config_store = config_store
        self._connection_info = connection_info
        self._worker: CrawlWorker | None = None
        self._is_crawling = False
        self._success_count = 0
        self._failed_count = 0
        self._skipped_count = 0
        self._results: list = []
        self._use_dark_theme = True  # Default to dark theme colors

        self._setup_ui()
        self._prefill_paths()

    def _setup_ui(self) -> None:
        """Build the crawl page UI layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- Connection status and logout ---
        status_layout = QHBoxLayout()
        username = self._connection_info.get("username", "")
        host = self._connection_info.get("host", "")
        port = self._connection_info.get("port", "")
        self._status_label = QLabel(f"Connected: {username}@{host}:{port}")
        self._status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        self._logout_btn = QPushButton("Logout")
        self._logout_btn.setFixedWidth(80)
        self._logout_btn.clicked.connect(self._on_logout)
        status_layout.addWidget(self._logout_btn)
        layout.addLayout(status_layout)

        # --- File input section ---
        file_section_label = QLabel("File Inputs")
        file_section_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(file_section_label)

        # AP List
        ap_layout = QHBoxLayout()
        ap_layout.addWidget(QLabel("AP List:"))
        self._ap_list_input = QLineEdit()
        self._ap_list_input.setReadOnly(True)
        self._ap_list_input.setPlaceholderText("Select AP list file (.txt)")
        ap_layout.addWidget(self._ap_list_input)
        self._ap_browse_btn = QPushButton("Browse")
        self._ap_browse_btn.setFixedWidth(80)
        self._ap_browse_btn.clicked.connect(self._browse_ap_list)
        ap_layout.addWidget(self._ap_browse_btn)
        layout.addLayout(ap_layout)

        # Switch List
        sw_layout = QHBoxLayout()
        sw_layout.addWidget(QLabel("Switch List:"))
        self._switch_list_input = QLineEdit()
        self._switch_list_input.setReadOnly(True)
        self._switch_list_input.setPlaceholderText("Select switch list file (.txt)")
        sw_layout.addWidget(self._switch_list_input)
        self._switch_browse_btn = QPushButton("Browse")
        self._switch_browse_btn.setFixedWidth(80)
        self._switch_browse_btn.clicked.connect(self._browse_switch_list)
        sw_layout.addWidget(self._switch_browse_btn)
        layout.addLayout(sw_layout)

        # Output Directory
        out_layout = QHBoxLayout()
        out_layout.addWidget(QLabel("Output Dir:"))
        self._output_dir_input = QLineEdit()
        self._output_dir_input.setReadOnly(True)
        self._output_dir_input.setPlaceholderText("Select output directory")
        out_layout.addWidget(self._output_dir_input)
        self._output_browse_btn = QPushButton("Browse")
        self._output_browse_btn.setFixedWidth(80)
        self._output_browse_btn.clicked.connect(self._browse_output_dir)
        out_layout.addWidget(self._output_browse_btn)
        layout.addLayout(out_layout)

        # Error label for path validation
        self._path_error_label = QLabel("")
        self._path_error_label.setStyleSheet("color: #f38ba8;")
        self._path_error_label.setWordWrap(True)
        self._path_error_label.hide()
        layout.addWidget(self._path_error_label)

        # --- Start/Stop button ---
        self._start_stop_btn = QPushButton("Start")
        self._start_stop_btn.setFixedHeight(40)
        self._apply_start_style()
        self._start_stop_btn.clicked.connect(self._on_start_stop)
        layout.addWidget(self._start_stop_btn)

        # --- Progress bar ---
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        # --- Counts ---
        counts_layout = QHBoxLayout()
        self._success_label = QLabel("Success: 0")
        self._success_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        counts_layout.addWidget(self._success_label)

        self._failed_label = QLabel("Failed: 0")
        self._failed_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        counts_layout.addWidget(self._failed_label)

        self._skipped_label = QLabel("Skipped: 0")
        self._skipped_label.setStyleSheet("color: #f9e2af; font-weight: bold;")
        counts_layout.addWidget(self._skipped_label)

        counts_layout.addStretch()
        layout.addLayout(counts_layout)

        # --- Live log ---
        log_label = QLabel("Live Log")
        log_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(log_label)

        self._log_list = QListWidget()
        self._log_list.setMinimumHeight(200)
        layout.addWidget(self._log_list)

    def _apply_start_style(self) -> None:
        """Apply green 'Start' button style."""
        self._start_stop_btn.setText("Start")
        self._start_stop_btn.setStyleSheet(
            "QPushButton { background-color: #a6e3a1; color: #1e1e2e; "
            "font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #b8ebc2; }"
            "QPushButton:disabled { background-color: #45475a; color: #6c7086; }"
        )

    def _apply_stop_style(self) -> None:
        """Apply red 'Stop' button style."""
        self._start_stop_btn.setText("Stop")
        self._start_stop_btn.setStyleSheet(
            "QPushButton { background-color: #f38ba8; color: #1e1e2e; "
            "font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #f5a0b8; }"
            "QPushButton:disabled { background-color: #45475a; color: #6c7086; }"
        )

    def _prefill_paths(self) -> None:
        """Pre-fill file paths from ConfigStore on page load."""
        config = self._config_store.load()
        if config.ap_list_path:
            self._ap_list_input.setText(config.ap_list_path)
        if config.switch_list_path:
            self._switch_list_input.setText(config.switch_list_path)
        if config.output_dir:
            self._output_dir_input.setText(config.output_dir)

    def _save_paths(self) -> None:
        """Save current file paths to ConfigStore."""
        config = self._config_store.load()
        config.ap_list_path = self._ap_list_input.text()
        config.switch_list_path = self._switch_list_input.text()
        config.output_dir = self._output_dir_input.text()
        self._config_store.save(config)

    # --- Browse dialogs ---

    def _browse_ap_list(self) -> None:
        """Open file dialog for AP list selection."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select AP List File", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self._ap_list_input.setText(path)

    def _browse_switch_list(self) -> None:
        """Open file dialog for switch list selection."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Switch List File", "", "Text Files (*.txt);;All Files (*)"
        )
        if path:
            self._switch_list_input.setText(path)

    def _browse_output_dir(self) -> None:
        """Open directory dialog for output directory selection."""
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self._output_dir_input.setText(path)

    # --- Start/Stop logic ---

    def _on_start_stop(self) -> None:
        """Handle Start/Stop button click."""
        if self._is_crawling:
            self._stop_crawl()
        else:
            self._start_crawl()

    def _start_crawl(self) -> None:
        """Validate paths, launch CrawlWorker, toggle to Stop state."""
        ap_path = self._ap_list_input.text()
        switch_path = self._switch_list_input.text()
        output_dir = self._output_dir_input.text()

        # Validate paths
        errors = validate_paths(ap_path, switch_path, output_dir)
        if errors:
            error_lines = [f"• {field}: {msg}" for field, msg in errors.items()]
            self._path_error_label.setText("\n".join(error_lines))
            self._path_error_label.show()
            return

        self._path_error_label.hide()

        # Disable start button during initialization
        self._start_stop_btn.setEnabled(False)

        try:
            # Parse input files
            ap_list = parse_ap_list(ap_path)
            switch_dict = parse_switch_list(switch_path)

            # Read existing CSV for resume mode
            already_done = read_existing_csv(output_dir)

            # Build config from session
            config = Config(
                host=self._connection_info.get("host", ""),
                port=int(self._connection_info.get("port", 22)),
                username=self._connection_info.get("username", ""),
                password=self._connection_info.get("password", ""),
            )

            # Save paths to config store on successful start
            self._save_paths()

            # Reset UI state for new crawl
            self._reset_crawl_state()

            # Create and start worker
            self._worker = CrawlWorker(
                session=self._session,
                ap_list=ap_list,
                switch_dict=switch_dict,
                config=config,
                already_done=already_done,
            )
            self._worker.ap_progress.connect(self._on_ap_progress)
            self._worker.crawl_finished.connect(self._on_crawl_finished)
            self._worker.crawl_error.connect(self._on_crawl_error)
            self._worker.start()

            # Toggle to crawling state
            self._is_crawling = True
            self._apply_stop_style()
            self._start_stop_btn.setEnabled(True)
            self._logout_btn.setEnabled(False)

        except SystemExit:
            # parse_ap_list / parse_switch_list call sys.exit on errors
            self._path_error_label.setText("Error: Failed to parse input files.")
            self._path_error_label.show()
            self._start_stop_btn.setEnabled(True)
        except Exception as e:
            logger.error("Failed to start crawl: %s", e)
            self._path_error_label.setText(f"Error: {e}")
            self._path_error_label.show()
            self._start_stop_btn.setEnabled(True)

    def _stop_crawl(self) -> None:
        """Request stop, save partial results."""
        if self._worker is None:
            return

        self._start_stop_btn.setEnabled(False)
        self._worker.request_stop()

        # Wait up to 10 seconds for worker to finish
        if not self._worker.wait(10000):
            # Force terminate if not stopped in time
            self._worker.terminate()
            self._worker.wait(2000)

        # Save partial results
        self._save_partial_results()

    def _reset_crawl_state(self) -> None:
        """Reset progress bar, counts, and log for a new crawl."""
        self._success_count = 0
        self._failed_count = 0
        self._skipped_count = 0
        self._results = []
        self._progress_bar.setValue(0)
        self._success_label.setText("Success: 0")
        self._failed_label.setText("Failed: 0")
        self._skipped_label.setText("Skipped: 0")
        self._log_list.clear()

    def _save_partial_results(self) -> None:
        """Save collected results to CSV."""
        if self._results:
            output_dir = self._output_dir_input.text()
            try:
                write_csv(self._results, output_dir, append_to_existing=True)
                logger.info("Saved %d partial results to CSV", len(self._results))
            except Exception as e:
                logger.error("Failed to save partial results: %s", e)

    # --- Worker signal handlers ---

    def _on_ap_progress(self, ap_name: str, status: str, current: int, total: int) -> None:
        """Handle progress signal from CrawlWorker."""
        # Update progress bar
        if total > 0:
            percentage = int((current / total) * 100)
            self._progress_bar.setValue(percentage)

        # Update counts
        if status == "success":
            self._success_count += 1
            self._success_label.setText(f"Success: {self._success_count}")
        elif status == "failed":
            self._failed_count += 1
            self._failed_label.setText(f"Failed: {self._failed_count}")
        elif status == "skipped":
            self._skipped_count += 1
            self._skipped_label.setText(f"Skipped: {self._skipped_count}")

        # Add log entry with color
        self._add_log_entry(ap_name, status)

        # Store result for partial save
        from crawler import CrawlResult

        self._results.append(
            CrawlResult(
                ap_name=ap_name,
                ap_ip="",
                switch_name="",
                switch_ip="",
                status=status,
            )
        )

    def _on_crawl_finished(self, reason: str) -> None:
        """Handle crawl completion signal."""
        self._is_crawling = False
        self._apply_start_style()
        self._start_stop_btn.setEnabled(True)
        self._logout_btn.setEnabled(True)

        # Add completion message to log
        if reason == "completed":
            self._add_log_entry("Crawl completed successfully", "info")
        elif reason == "stopped":
            self._add_log_entry("Crawl stopped by user", "info")
        elif reason == "connection_lost":
            self._add_log_entry("Connection lost during crawl", "failed")

        self._worker = None

    def _on_crawl_error(self, error: str) -> None:
        """Handle crawl error signal."""
        self._is_crawling = False
        self._apply_start_style()
        self._start_stop_btn.setEnabled(True)
        self._logout_btn.setEnabled(True)

        self._add_log_entry(f"Error: {error}", "failed")
        self._save_partial_results()
        self._worker = None

    # --- Log entry management ---

    def _add_log_entry(self, text: str, status: str) -> None:
        """Add a color-coded entry to the live log.

        Auto-scrolls to bottom unless user has scrolled away.
        """
        # Check if scrollbar is at the bottom before adding
        scrollbar = self._log_list.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum()

        item = QListWidgetItem(text)

        # Apply color based on status
        if status == "success":
            color = _DARK_GREEN if self._use_dark_theme else _LIGHT_GREEN
        elif status == "failed":
            color = _DARK_RED if self._use_dark_theme else _LIGHT_RED
        elif status == "skipped":
            color = _DARK_YELLOW if self._use_dark_theme else _LIGHT_YELLOW
        else:
            color = None

        if color:
            item.setForeground(color)

        self._log_list.addItem(item)

        # Auto-scroll to bottom if user was at the bottom
        if at_bottom:
            self._log_list.scrollToBottom()

    # --- Logout ---

    def _on_logout(self) -> None:
        """Handle logout button click."""
        self.logout_requested.emit()

    # --- Theme support ---

    def set_theme(self, theme: str) -> None:
        """Update theme for log entry colors.

        Args:
            theme: Either "dark" or "light".
        """
        self._use_dark_theme = theme == "dark"

"""PySide6 GUI entry point for WAC Huawei LLDP Crawl Data tool.

Replaces the previous CLI entry point. Creates the QApplication,
initializes services (encryption, config store), applies the stored
theme, and launches the MainWindow.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import QApplication

from gui.encryption import EncryptionService
from gui.config_store import ConfigStore
from gui.main_window import MainWindow
from gui.themes import apply_theme

# --- Logging setup ---
# Rotating log file: 5 MB max, 3 backups
log_handler = RotatingFileHandler(
    "crawl.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
log_handler.setLevel(logging.DEBUG)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)

logging.basicConfig(level=logging.DEBUG, handlers=[log_handler])
logger = logging.getLogger(__name__)


def main() -> None:
    """Application entry point."""
    from datetime import datetime

    logger.info("")
    logger.info("")
    logger.info("=" * 50)
    logger.info("APP START — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 50)
    logger.info("")

    app = QApplication(sys.argv)

    # Initialize services
    encryption_service = EncryptionService()
    config_store = ConfigStore(encryption_service)

    # Load config and apply stored theme before showing window
    config = config_store.load()
    apply_theme(app, config.theme)

    # Create and show main window
    window = MainWindow(config_store, encryption_service)
    window.show()

    logger.info("Main window displayed")
    exit_code = app.exec()

    logger.info("")
    logger.info("=" * 50)
    logger.info("APP END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 50)
    logger.info("")
    logger.info("")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

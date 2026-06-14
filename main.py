"""PySide6 GUI entry point for WAC Huawei LLDP Crawl Data tool.

Replaces the previous CLI entry point. Creates the QApplication,
initializes services (encryption, config store), applies the stored
theme, and launches the MainWindow.
"""

import logging
import signal
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import QApplication

from gui.encryption import EncryptionService
from gui.config_store import ConfigStore
from gui.main_window import MainWindow
from gui.themes import apply_theme
from app_info import get_log_dir

# --- Logging setup ---
# Rotating log file: 5 MB max, 3 backups
log_dir = get_log_dir()
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "crawl.log"

log_handler = RotatingFileHandler(
    log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
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
    import app_info

    start_time = datetime.now()
    exit_code = 1

    logger.info("=" * 50)
    logger.info("APPLICATION SESSION START")
    logger.info("Time    : %s", start_time.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("App     : %s", app_info.APP_NAME)
    logger.info("Version : %s", app_info.APP_VERSION)
    logger.info("Log file: %s", log_file)
    logger.info("=" * 50)

    try:
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

        # Handle CTRL+C gracefully — close SSH session and exit
        def sigint_handler(*args):
            logger.info("CTRL+C received, shutting down...")
            window.close()

        signal.signal(signal.SIGINT, sigint_handler)

        # Allow Python to process signals (CTRL+C) while Qt event loop runs
        from PySide6.QtCore import QTimer
        timer = QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(500)

        logger.info("Main window displayed")
        exit_code = app.exec()

    except Exception:
        logger.exception("Unhandled application error")
        raise
    finally:
        end_time = datetime.now()
        runtime = end_time - start_time

        # Format runtime nicely (e.g., 00:06:16)
        runtime_secs = int(runtime.total_seconds())
        hours = runtime_secs // 3600
        minutes = (runtime_secs % 3600) // 60
        seconds = runtime_secs % 60
        runtime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        logger.info("=" * 50)
        logger.info("APPLICATION SESSION END")
        logger.info("Time     : %s", end_time.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("Exit code: %s", exit_code)
        logger.info("Runtime  : %s", runtime_str)
        logger.info("=" * 50)
        logger.info("")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

"""Main entry point for WAC Huawei LLDP Crawl Data tool.

Wires all components together: config loading, file parsing,
SSH connection, AP crawling, CSV output, and summary display.
"""

import logging
import sys
from datetime import datetime

from config import load_config
from crawler import crawl_all_aps
from output import print_summary, write_csv
from parsers import parse_ap_list, parse_switch_list
from ssh_client import SSHSession

# Log file: single file, append mode with session separators
log_filename = "crawl.log"
file_handler = logging.FileHandler(log_filename, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

# Console: clean, minimal output (only errors)
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

# Write session start marker
_logger = logging.getLogger(__name__)
_logger.info("=" * 60)
_logger.info("SESSION START — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
_logger.info("=" * 60)


def main() -> None:
    """Main entry point.

    Flow:
    1. load_config()
    2. parse_ap_list()
    3. parse_switch_list()
    4. session.connect() + enter_system_view()
    5. crawl_all_aps()
    6. write_csv()
    7. print_summary()
    8. session.disconnect()

    Wrapped in try/finally for guaranteed SSH cleanup.
    """
    session = None
    results = []
    try:
        config = load_config()
        ap_list = parse_ap_list()
        switch_dict = parse_switch_list()

        session = SSHSession(config)
        session.connect()
        session.enter_system_view()

        results = crawl_all_aps(session, ap_list, switch_dict, config)
        filepath = write_csv(results)
        print_summary(results, filepath)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C). Saving partial results...")
        if results:
            filepath = write_csv(results)
            print_summary(results, filepath)
        else:
            print("No results to save.")
    finally:
        if session:
            session.disconnect()
        _logger.info("SESSION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        _logger.info("-" * 60)


if __name__ == "__main__":
    main()

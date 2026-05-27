"""Main entry point for WAC Huawei LLDP Crawl Data tool.

Wires all components together: config loading, file parsing,
SSH connection, AP crawling, CSV output, and summary display.
"""

import logging

from config import load_config
from crawler import crawl_all_aps
from output import print_summary, write_csv
from parsers import parse_ap_list, parse_switch_list
from ssh_client import SSHSession

# Configure logging to show warnings on stderr
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


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
    finally:
        if session:
            session.disconnect()


if __name__ == "__main__":
    main()

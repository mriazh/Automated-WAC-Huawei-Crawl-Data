"""Main entry point for WAC Huawei LLDP Crawl Data tool.

Wires all components together: config loading, file parsing,
SSH connection, AP crawling, CSV output, and summary display.

Supports resume mode: if lldp_result.csv exists, skips already-crawled APs.
Supports auto-reconnect: if SSH drops mid-crawl, reconnects and continues.
"""

import logging
import sys
from datetime import datetime

from config import load_config
from crawler import crawl_all_aps
from output import print_summary, read_existing_csv, write_csv
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

    Supports resume: reads existing lldp_result.csv and skips completed APs.
    Supports auto-reconnect: if SSH drops, reconnects and continues.
    """
    session = None
    results = []
    try:
        config = load_config()
        ap_list = parse_ap_list()
        switch_dict = parse_switch_list()

        # Check for existing CSV to resume from
        already_done = read_existing_csv()
        resumed_count = len(already_done)

        remaining = len(ap_list) - resumed_count
        print("")
        if resumed_count > 0:
            print(f"  Mode     : RESUME (continuing previous crawl)")
            print(f"  Done     : {resumed_count} APs already in lldp_result.csv")
            print(f"  Remaining: {remaining} APs to crawl")
            _logger.info("=== RESUME MODE === %d done, %d remaining out of %d total", resumed_count, remaining, len(ap_list))
        else:
            print(f"  Mode     : FRESH START (no previous results found)")
            print(f"  Total APs: {len(ap_list)}")
            _logger.info("=== FRESH START === %d APs to crawl", len(ap_list))
        print("")

        session = SSHSession(config)
        session.connect()
        session.enter_system_view()

        print("Connected to WAC. Starting crawl...\n")
        _logger.info("SSH connected, entering crawl loop")

        results = crawl_all_aps(session, ap_list, switch_dict, config, already_done=already_done)

        # Write results (append if resuming, overwrite if fresh)
        if resumed_count > 0:
            filepath = write_csv(results, append_to_existing=True)
        else:
            filepath = write_csv(results)

        print_summary(results, filepath, resumed_count=resumed_count)

    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C). Saving partial results...")
        if results:
            if resumed_count > 0:
                filepath = write_csv(results, append_to_existing=True)
            else:
                filepath = write_csv(results)
            print_summary(results, filepath, resumed_count=resumed_count)
        else:
            print("No results to save.")
    finally:
        if session:
            session.disconnect()
        _logger.info("SESSION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        _logger.info("-" * 60)


if __name__ == "__main__":
    main()

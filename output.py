"""CSV output writer and summary display for WAC Huawei LLDP Crawl Data tool.

Generates timestamped CSV files mapping AP-to-Switch connectivity
and displays crawl execution statistics.
"""

import csv
import os
from datetime import datetime

from crawler import CrawlResult


def write_csv(results: list[CrawlResult], output_dir: str = ".") -> str:
    """Write results to CSV file with timestamp filename.

    Filename: lldp_result_YYYYMMDD_HHMMSS.csv
    Header: AP,Switch
    Row format: "AP_Name (AP_IP)","Switch_Name (Switch_IP)"

    Only includes results with status 'success'.
    Generates header-only file if no successful results.
    Returns the output filepath.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"lldp_result_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    try:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["AP", "Switch"])

            for result in results:
                if result.status == "success":
                    ap_col = f"{result.ap_name} ({result.ap_ip})"
                    switch_col = f"{result.switch_name} ({result.switch_ip})"
                    writer.writerow([ap_col, switch_col])
    except OSError as e:
        print(f"Error: Failed to write output file '{filepath}': {e}")
        raise

    return filepath


def print_summary(results: list[CrawlResult], filepath: str) -> None:
    """Print crawl summary statistics to stdout.

    Shows: total, skipped, successful, failed counts.
    Shows output file path.
    """
    total = len(results)
    skipped = sum(1 for r in results if r.status == "skipped")
    successful = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")

    print("\n--- Crawl Summary ---")
    print(f"Total APs: {total}")
    print(f"Skipped (offline): {skipped}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Output file: {filepath}")

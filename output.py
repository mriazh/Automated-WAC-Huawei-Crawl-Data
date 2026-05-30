"""CSV output writer and summary display for WAC Huawei LLDP Crawl Data tool.

Generates a single CSV file mapping AP-to-Switch connectivity
and displays crawl execution statistics.
"""

import csv
import logging
import os
import re

from crawler import CrawlResult

logger = logging.getLogger(__name__)

CSV_FILENAME = "lldp_result.csv"


def read_existing_csv(output_dir: str = ".") -> set[str]:
    """Read existing CSV and return set of AP names already crawled.

    Used for resume mode — skip APs that already have results.
    Returns empty set if file doesn't exist or is empty.
    Logs warning on read errors instead of silently ignoring.
    """
    filepath = os.path.join(output_dir, CSV_FILENAME)
    done = set()

    if not os.path.exists(filepath):
        return done

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if row:
                    # Extract AP name from "AP_Name (AP_IP)" format
                    match = re.match(r"^(.+?)\s*\(", row[0])
                    if match:
                        done.add(match.group(1))
    except OSError as e:
        logger.warning("Could not read existing CSV '%s': %s", filepath, e)
    except csv.Error as e:
        logger.warning("Existing CSV '%s' is malformed: %s", filepath, e)

    return done


def write_csv(results: list[CrawlResult], output_dir: str = ".",
              append_to_existing: bool = False) -> str:
    """Write results to CSV file.

    If append_to_existing=True, appends new successful results to existing file.
    Otherwise overwrites the file.

    Filename: lldp_result.csv
    Header: AP,Switch
    Row format: "AP_Name (AP_IP)","Switch_Name (Switch_IP)"

    Only includes results with status 'success'.
    Returns the output filepath.
    """
    filepath = os.path.join(output_dir, CSV_FILENAME)

    if append_to_existing and os.path.exists(filepath):
        # Append mode: add new results to existing file
        try:
            with open(filepath, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_ALL)
                for result in results:
                    if result.status == "success":
                        ap_col = f"{result.ap_name} ({result.ap_ip})"
                        switch_col = f"{result.switch_name} ({result.switch_ip})"
                        writer.writerow([ap_col, switch_col])
        except OSError as e:
            print(f"Error: Failed to append to output file '{filepath}': {e}")
            raise
    else:
        # Overwrite mode: write fresh file
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


def print_summary(results: list[CrawlResult], filepath: str,
                  resumed_count: int = 0) -> None:
    """Fallback plain-text summary used by tests and non-Rich environments.

    Shows: total, skipped, successful, failed counts.
    Shows output file path.
    """
    total = len(results)
    skipped = sum(1 for r in results if r.status == "skipped")
    successful = sum(1 for r in results if r.status == "success")
    failed = sum(1 for r in results if r.status == "failed")

    print("\n--- Crawl Summary ---")
    if resumed_count > 0:
        print(f"Previously completed: {resumed_count}")
    print(f"Total APs processed this run: {total}")
    print(f"Skipped (offline): {skipped}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    if resumed_count > 0:
        print(f"Total in CSV: {resumed_count + successful}")
    print(f"Output file: {filepath}")

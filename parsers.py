"""File and LLDP parsers for WAC Huawei LLDP Crawl Data tool.

Parses input files (list_ap.txt, list_switch.txt) and LLDP command output.
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class APEntry:
    """Represents a single AP entry from list_ap.txt."""

    name: str
    ip: str
    ap_id: int
    is_offline: bool  # True when ip == "--"


@dataclass
class LLDPNeighbor:
    """Represents an LLDP neighbor entry."""
    
    local_intf: str
    neighbor_dev: str
    neighbor_intf: str


def parse_ap_list(filepath: str = "list_ap.txt") -> list[APEntry]:
    """Parse tab-separated AP list file.

    Format per line: AP_Name<TAB>IP<TAB>ID
    Skips blank lines silently. Logs warning for malformed lines.
    Raises SystemExit on missing file or no valid entries.
    """
    path = Path(filepath)

    if not path.exists():
        print(f"Error: AP list file not found at '{filepath}'")
        sys.exit(1)

    entries: list[APEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            parts = stripped.split("\t")
            if len(parts) != 3:
                logger.warning(
                    "Skipping malformed line %d in '%s': %s",
                    line_num,
                    filepath,
                    stripped,
                )
                continue

            ap_name = parts[0].strip()
            ip = parts[1].strip()
            try:
                ap_id = int(parts[2].strip())
            except ValueError:
                logger.warning(
                    "Skipping malformed line %d in '%s': invalid ID '%s'",
                    line_num,
                    filepath,
                    parts[2].strip(),
                )
                continue

            is_offline = ip == "--"
            entries.append(APEntry(name=ap_name, ip=ip, ap_id=ap_id, is_offline=is_offline))

    if not entries:
        print(f"Error: No valid AP entries found in '{filepath}'")
        sys.exit(1)

    return entries


def parse_switch_list(filepath: str = "list_switch.txt") -> dict[str, str]:
    """Parse tab-separated switch list file.

    Format per line: Switch_Name<TAB>IP
    Trims whitespace from both fields.
    Returns dict mapping switch_name -> ip.
    Raises SystemExit on missing file.
    """
    path = Path(filepath)

    if not path.exists():
        print(f"Error: Switch list file not found at '{filepath}'")
        sys.exit(1)

    switch_dict: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            parts = stripped.split("\t")
            if len(parts) != 2:
                logger.warning(
                    "Skipping malformed line %d in '%s': %s",
                    line_num,
                    filepath,
                    stripped,
                )
                continue

            switch_name = parts[0].strip()
            ip = parts[1].strip()
            switch_dict[switch_name] = ip

    return switch_dict


def parse_lldp_output(output: str, ap_name: str = "") -> list[LLDPNeighbor]:
    """Extract ALL Neighbor Dev values from LLDP command output.

    Algorithm:
    1. Find header line containing "Neighbor Dev"
    2. Determine column boundaries from header character positions
    3. Extract values from ALL data rows below header

    Returns list of LLDPNeighbor objects. Empty list if no valid data found.
    Logs warning if header format is unrecognizable.
    """
    if not output or not output.strip():
        return []

    lines = output.splitlines()

    # Find the header line containing "Neighbor Dev"
    header_idx = None
    for i, line in enumerate(lines):
        if "Neighbor Dev" in line:
            header_idx = i
            break

    if header_idx is None:
        logger.warning(
            "LLDP output for AP '%s' does not contain expected header columns",
            ap_name,
        )
        return []

    header_line = lines[header_idx]

    # Verify header contains expected column names
    # Verify header contains expected column names
    if "Neighbor Intf" not in header_line or "Local Intf" not in header_line or "Exptime" not in header_line:
        logger.warning(
            "LLDP output for AP '%s' has unrecognizable header format",
            ap_name,
        )
        return []

    # Determine column boundaries from header character positions
    local_start = header_line.index("Local Intf")
    dev_start = header_line.index("Neighbor Dev")
    intf_start = header_line.index("Neighbor Intf")
    exptime_start = header_line.index("Exptime")

    # Extract ALL data rows after header
    neighbors: list[LLDPNeighbor] = []
    data_lines = lines[header_idx + 1:]
    for data_line in data_lines:
        stripped = data_line.strip()
        if not stripped:
            continue
        # Skip lines that look like prompts (e.g., <AP-TEST-01>)
        if stripped.startswith("<") and stripped.endswith(">"):
            continue

        # Extract values using column boundaries
        local_intf = data_line[local_start:dev_start].strip() if len(data_line) > local_start else ""
        neighbor_dev = data_line[dev_start:intf_start].strip() if len(data_line) > dev_start else ""
        neighbor_intf = data_line[intf_start:exptime_start].strip() if len(data_line) > intf_start else ""

        if neighbor_dev:
            neighbors.append(
                LLDPNeighbor(
                    local_intf=local_intf or "N/A",
                    neighbor_dev=neighbor_dev,
                    neighbor_intf=neighbor_intf or "N/A",
                )
            )

    return neighbors


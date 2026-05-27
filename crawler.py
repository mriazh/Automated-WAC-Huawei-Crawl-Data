"""Crawl engine for WAC Huawei LLDP Crawl Data tool.

Orchestrates AP iteration, executes crawl sequence per AP,
maps results to switch IPs via the switch dictionary.
"""

import logging
import re
import time
from dataclasses import dataclass

from config import Config
from parsers import APEntry, parse_lldp_output
from ssh_client import SSHSession, WAC_SYSTEM_PROMPT, AP_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Result of crawling a single AP for LLDP data."""

    ap_name: str
    ap_ip: str
    switch_name: str  # "N/A" if not found
    switch_ip: str  # "N/A" if not in switch list
    status: str  # "success", "skipped", "failed"
    error: str = ""  # error message if failed


def crawl_all_aps(
    session: SSHSession,
    ap_list: list[APEntry],
    switch_dict: dict[str, str],
    config: Config,
) -> list[CrawlResult]:
    """Iterate through all APs, crawl LLDP data, return results.

    Prints clean progress to stdout. Logs details to file.
    Skips offline APs. Handles connection failures gracefully.
    Returns partial results on KeyboardInterrupt.
    """
    results: list[CrawlResult] = []
    total = len(ap_list)

    try:
        for n, ap in enumerate(ap_list, start=1):
            # Clean console: single line progress
            print(f"[{n}/{total}] {ap.name}", end="")
            logger.info("Processing AP %d/%d: %s (ID: %d, IP: %s)", n, total, ap.name, ap.ap_id, ap.ip)

            # Skip offline APs
            if ap.is_offline:
                print(" - SKIP (offline)")
                logger.info("Skipped AP '%s' — no IP assigned", ap.name)
                results.append(
                    CrawlResult(
                        ap_name=ap.name,
                        ap_ip=ap.ip,
                        switch_name="N/A",
                        switch_ip="N/A",
                        status="skipped",
                    )
                )
                continue

            # Crawl online AP
            try:
                result = crawl_single_ap(session, ap, switch_dict, config)
                if result.status == "success":
                    print(f" -> {result.switch_name}")
                    logger.info("Success: %s -> %s (%s)", ap.name, result.switch_name, result.switch_ip)
                else:
                    print(f" - FAILED: {result.error}")
                    logger.warning("Failed: %s — %s", ap.name, result.error)
                results.append(result)
            except KeyboardInterrupt:
                print(" - INTERRUPTED")
                raise
            except Exception as e:
                error_msg = str(e)
                print(f" - FAILED: {error_msg}")
                logger.error("Exception crawling AP '%s' (ID: %d): %s", ap.name, ap.ap_id, error_msg)
                results.append(
                    CrawlResult(
                        ap_name=ap.name,
                        ap_ip=ap.ip,
                        switch_name="N/A",
                        switch_ip="N/A",
                        status="failed",
                        error=error_msg,
                    )
            )
    except KeyboardInterrupt:
        print(" - INTERRUPTED")
        logger.info("Crawl interrupted by user at AP %d/%d", len(results) + 1, total)

    return results

    return results


def crawl_single_ap(
    session: SSHSession,
    ap: APEntry,
    switch_dict: dict[str, str],
    config: Config,
) -> CrawlResult:
    """Connect to single AP via stelnet, get LLDP data, map to switch.

    Sequence:
    1. Send 'stelnet ap ap-id {ID}'
    2. Handle Y/N prompts (auto-respond Y then N)
    3. Wait for AP prompt
    4. Send 'display lldp neighbor brief'
    5. Parse output for Neighbor Dev
    6. Lookup switch IP in switch_dict
    7. Exit AP session
    """
    try:
        # Step 1-3: Send stelnet command and handle Y/N prompts, wait for AP prompt
        # The stelnet sequence may have 1 or 2 Y/N prompts:
        #   1. "Continue to access it? [Y/N]:" → respond "Y" (always)
        #   2. "Save the server's public key? [Y/N]:" → respond "N" (only first time)
        # After prompts, wait for AP prompt <AP-NAME>
        #
        # We use auto_respond to handle both cases gracefully:
        # - If both prompts appear, auto_respond handles them automatically
        # - If only the first prompt appears, we still reach the AP prompt
        session.channel.send(f"stelnet ap ap-id {ap.ap_id}\n")

        # Use auto_respond to handle Y/N prompts dynamically.
        # Handles all known prompt variations:
        # - "Continue to access it?" → Y (always)
        # - "Save the server's public key?" → Y (first time, key not cached)
        # - "Update the server's public key now?" → Y (key changed)
        # Answering Y to save/update prevents "connection closed by remote"
        auto_respond_map = {
            r"Continue to access it\?": "Y",
            r"Save the server's public key\?": "Y",
            r"Update the server's public key": "Y",
        }

        # Also detect if connection was closed by remote (AP unreachable)
        output = session.wait_for_prompt(
            patterns=[AP_PROMPT, r"connection was closed"],
            timeout=config.ap_connect_timeout,
            auto_respond=auto_respond_map,
        )

        # Check if connection was closed instead of getting AP prompt
        if re.search(r"connection was closed", output, re.IGNORECASE):
            logger.warning("AP '%s' (ID: %d): connection closed by remote host", ap.name, ap.ap_id)
            # Drain any remaining output and wait for WAC prompt to recover
            try:
                session.wait_for_prompt(
                    patterns=[WAC_SYSTEM_PROMPT],
                    timeout=5,
                )
            except TimeoutError:
                pass
            return CrawlResult(
                ap_name=ap.name,
                ap_ip=ap.ip,
                switch_name="N/A",
                switch_ip="N/A",
                status="failed",
                error="Connection closed by remote host",
            )

        # Step 4: Send LLDP command and wait for output
        lldp_output = session.send_command(
            "display lldp neighbor brief",
            timeout=config.command_timeout,
            expect_patterns=[AP_PROMPT],
        )

        # Step 5: Parse LLDP output for neighbor device name
        neighbor_name = parse_lldp_output(lldp_output, ap_name=ap.name)

        # Step 6: Lookup switch name in switch_dict
        if neighbor_name:
            switch_name = neighbor_name
            switch_ip = switch_dict.get(neighbor_name, "N/A")
        else:
            switch_name = "N/A"
            switch_ip = "N/A"

        # Step 7: Exit AP session
        exit_ap_session(session)

        return CrawlResult(
            ap_name=ap.name,
            ap_ip=ap.ip,
            switch_name=switch_name,
            switch_ip=switch_ip,
            status="success",
        )

    except TimeoutError as e:
        # Attempt to exit AP session on failure
        try:
            exit_ap_session(session)
        except Exception:
            pass

        # Drain any leftover data in the buffer to prevent state corruption
        _drain_buffer(session)

        error_msg = f"Timeout: {e}"
        logger.warning("AP '%s' (ID: %d) crawl failed: %s", ap.name, ap.ap_id, error_msg)

        return CrawlResult(
            ap_name=ap.name,
            ap_ip=ap.ip,
            switch_name="N/A",
            switch_ip="N/A",
            status="failed",
            error=error_msg,
        )


def _drain_buffer(session: SSHSession) -> None:
    """Drain any leftover data from the SSH channel buffer."""
    time.sleep(0.5)
    try:
        while session.channel and session.channel.recv_ready():
            session.channel.recv(65535)
    except Exception:
        pass


def exit_ap_session(session: SSHSession) -> bool:
    """Exit AP session back to WAC context.

    Primary: send 'quit', wait 5s for WAC prompt.
    Fallback: send 'return', wait 5s for WAC prompt.
    Returns True if successful, False if both fail.
    """
    # Primary: try quit
    try:
        session.send_command(
            "quit",
            timeout=5,
            expect_patterns=[WAC_SYSTEM_PROMPT],
        )
        return True
    except TimeoutError:
        pass

    # Fallback: try return
    try:
        session.send_command(
            "return",
            timeout=5,
            expect_patterns=[WAC_SYSTEM_PROMPT],
        )
        return True
    except TimeoutError:
        logger.warning("Failed to exit AP session: both 'quit' and 'return' timed out")
        return False

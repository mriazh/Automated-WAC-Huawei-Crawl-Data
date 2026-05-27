"""Crawl engine for WAC Huawei LLDP Crawl Data tool.

Orchestrates AP iteration, executes crawl sequence per AP,
maps results to switch IPs via the switch dictionary.
"""

import logging
import time
from dataclasses import dataclass

from config import Config
from parsers import APEntry, parse_lldp_output
from ssh_client import SSHSession, WAC_SYSTEM_PROMPT, AP_PROMPT

logger = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 3


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
    already_done: set[str] | None = None,
) -> list[CrawlResult]:
    """Iterate through all APs, crawl LLDP data, return results.

    Prints clean progress to stdout. Logs details to file.
    Skips offline APs and already-completed APs (resume mode).
    Auto-reconnects SSH if connection drops.
    Returns partial results on KeyboardInterrupt.
    """
    results: list[CrawlResult] = []
    total = len(ap_list)
    if already_done is None:
        already_done = set()

    try:
        for n, ap in enumerate(ap_list, start=1):
            # Skip already-completed APs (resume mode)
            if ap.name in already_done:
                logger.info("Skipped AP '%s' — already in CSV (resume mode)", ap.name)
                continue

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
                ap_results = crawl_single_ap(session, ap, switch_dict, config)
                success_names = [r.switch_name for r in ap_results if r.status == "success"]
                failed_results = [r for r in ap_results if r.status == "failed"]

                if success_names:
                    print(f" -> {', '.join(success_names)}")
                    for r in ap_results:
                        if r.status == "success":
                            logger.info("Success: %s -> %s (%s)", ap.name, r.switch_name, r.switch_ip)
                elif failed_results:
                    print(f" - FAILED: {failed_results[0].error}")
                    for r in failed_results:
                        logger.warning("Failed: %s — %s", ap.name, r.error)

                results.extend(ap_results)
            except KeyboardInterrupt:
                print(" - INTERRUPTED")
                raise
            except Exception as e:
                error_msg = str(e)

                # Detect socket closed → attempt reconnect
                if "socket is closed" in error_msg.lower() or "socket exception" in error_msg.lower():
                    print(f" - CONNECTION LOST")
                    logger.error("SSH connection lost at AP '%s' (ID: %d): %s", ap.name, ap.ap_id, error_msg)

                    # Attempt reconnect
                    reconnected = _reconnect(session, config)
                    if reconnected:
                        # Retry this AP after reconnect
                        print(f"[{n}/{total}] {ap.name} (retry)", end="")
                        try:
                            ap_results = crawl_single_ap(session, ap, switch_dict, config)
                            success_names = [r.switch_name for r in ap_results if r.status == "success"]
                            if success_names:
                                print(f" -> {', '.join(success_names)}")
                                for r in ap_results:
                                    if r.status == "success":
                                        logger.info("Success (after reconnect): %s -> %s (%s)", ap.name, r.switch_name, r.switch_ip)
                            else:
                                print(f" - FAILED")
                            results.extend(ap_results)
                        except Exception as retry_e:
                            print(f" - FAILED: {retry_e}")
                            logger.error("Retry failed for AP '%s': %s", ap.name, retry_e)
                            results.append(
                                CrawlResult(
                                    ap_name=ap.name, ap_ip=ap.ip,
                                    switch_name="N/A", switch_ip="N/A",
                                    status="failed", error=str(retry_e),
                                )
                            )
                    else:
                        # Reconnect failed — stop crawling
                        print("\nFailed to reconnect SSH. Stopping crawl.")
                        logger.error("SSH reconnect failed. Stopping crawl at AP %d/%d", n, total)
                        results.append(
                            CrawlResult(
                                ap_name=ap.name, ap_ip=ap.ip,
                                switch_name="N/A", switch_ip="N/A",
                                status="failed", error="SSH reconnect failed",
                            )
                        )
                        break
                else:
                    print(f" - FAILED: {error_msg}")
                    logger.error("Exception crawling AP '%s' (ID: %d): %s", ap.name, ap.ap_id, error_msg)
                    results.append(
                        CrawlResult(
                            ap_name=ap.name, ap_ip=ap.ip,
                            switch_name="N/A", switch_ip="N/A",
                            status="failed", error=error_msg,
                        )
                    )
    except KeyboardInterrupt:
        print(" - INTERRUPTED")
        logger.info("Crawl interrupted by user at AP %d/%d", len(results) + 1, total)

    return results


def _reconnect(session: SSHSession, config: Config) -> bool:
    """Attempt to reconnect SSH session to WAC.

    Returns True if reconnect successful, False otherwise.
    """
    for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
        print(f"\n  Reconnecting SSH (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS})...", end="")
        logger.info("SSH reconnect attempt %d/%d", attempt, MAX_RECONNECT_ATTEMPTS)

        try:
            # Close old connection
            try:
                session.disconnect()
            except Exception:
                pass

            # Wait before reconnect
            time.sleep(2)

            # Reconnect
            session.connect()
            session.enter_system_view()
            print(" OK")
            logger.info("SSH reconnect successful")
            return True
        except Exception as e:
            print(f" FAILED ({e})")
            logger.error("SSH reconnect attempt %d failed: %s", attempt, e)
            time.sleep(5)

    return False


def crawl_single_ap(
    session: SSHSession,
    ap: APEntry,
    switch_dict: dict[str, str],
    config: Config,
) -> list[CrawlResult]:
    """Connect to single AP via stelnet, get LLDP data, map to switch.

    Sequence:
    1. Send 'stelnet ap ap-id {ID}'
    2. Handle Y/N prompts (auto-respond Y)
    3. Wait for AP prompt
    4. Send 'display lldp neighbor brief'
    5. Parse output for Neighbor Dev
    6. Lookup switch IP in switch_dict
    7. Exit AP session
    """
    try:
        # Drain any leftover buffer from previous AP session
        _drain_buffer(session)

        session.channel.send(f"stelnet ap ap-id {ap.ap_id}\n")

        # Use auto_respond to handle Y/N prompts dynamically.
        auto_respond_map = {
            r"Continue to access it\?": "Y",
            r"Save the server's public key\?": "Y",
            r"Update the server's public key": "Y",
        }

        # Wait for AP prompt only. Don't match "connection was closed" as it
        # can be leftover from the previous AP's quit sequence.
        # If connection truly fails, it will timeout.
        output = session.wait_for_prompt(
            patterns=[AP_PROMPT],
            timeout=config.ap_connect_timeout,
            auto_respond=auto_respond_map,
        )

        # Step 4: Send LLDP command and wait for output
        lldp_output = session.send_command(
            "display lldp neighbor brief",
            timeout=config.command_timeout,
            expect_patterns=[AP_PROMPT],
        )

        # Step 5: Parse LLDP output for ALL neighbor device names
        neighbors = parse_lldp_output(lldp_output, ap_name=ap.name)

        # Step 6: Build results for each neighbor
        results = []
        if neighbors:
            for neighbor_name in neighbors:
                switch_ip = switch_dict.get(neighbor_name, "N/A")
                results.append(CrawlResult(
                    ap_name=ap.name, ap_ip=ap.ip,
                    switch_name=neighbor_name, switch_ip=switch_ip,
                    status="success",
                ))
        else:
            results.append(CrawlResult(
                ap_name=ap.name, ap_ip=ap.ip,
                switch_name="N/A", switch_ip="N/A",
                status="success",
            ))

        # Step 7: Exit AP session and drain leftover buffer
        exit_ap_session(session)
        _drain_buffer(session)

        return results

    except TimeoutError as e:
        try:
            exit_ap_session(session)
        except Exception:
            pass
        _drain_buffer(session)

        error_msg = f"Timeout: {e}"
        logger.warning("AP '%s' (ID: %d) crawl failed: %s", ap.name, ap.ap_id, error_msg)
        return [CrawlResult(
            ap_name=ap.name, ap_ip=ap.ip,
            switch_name="N/A", switch_ip="N/A",
            status="failed", error=error_msg,
        )]


def _drain_buffer(session: SSHSession) -> None:
    """Drain any leftover data from the SSH channel buffer."""
    time.sleep(1)
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
    try:
        session.send_command("quit", timeout=5, expect_patterns=[WAC_SYSTEM_PROMPT])
        return True
    except TimeoutError:
        pass

    try:
        session.send_command("return", timeout=5, expect_patterns=[WAC_SYSTEM_PROMPT])
        return True
    except TimeoutError:
        logger.warning("Failed to exit AP session: both 'quit' and 'return' timed out")
        return False

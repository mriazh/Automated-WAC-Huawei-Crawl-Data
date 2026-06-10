"""Crawl engine for WAC Huawei LLDP Crawl Data tool.

Orchestrates AP iteration, executes crawl sequence per AP,
maps results to switch IPs via the switch dictionary.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from config import Config
from parsers import APEntry, parse_lldp_output
from ssh_client import SSHSession, WAC_SYSTEM_PROMPT, AP_PROMPT

logger = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 3

# ANSI codes for tqdm.write
ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_CYAN = "\033[96m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"


@dataclass
class CrawlResult:
    """Result of crawling a single AP for LLDP data."""

    ap_name: str
    ap_ip: str
    switch_name: str  # "N/A" if not found
    switch_ip: str  # "N/A" if not in switch list
    status: str  # "success", "skipped", "failed"
    error: str = ""  # error message if failed
    local_intf: str = "N/A"
    neighbor_intf: str = "N/A"


def crawl_all_aps(
    session: SSHSession,
    ap_list: list[APEntry],
    switch_dict: dict[str, str],
    config: Config,
    already_done: set[str] | None = None,
    progress_callback: Callable[[CrawlResult], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
    use_tqdm: bool = True,
) -> list[CrawlResult]:
    """Iterate through all APs, crawl LLDP data, return results.

    Uses tqdm progress bar (if available and use_tqdm=True) with colorful status output.
    Skips offline APs and already-completed APs (resume mode).
    Auto-reconnects SSH if connection drops.
    Returns partial results on KeyboardInterrupt or when stop_check returns True.

    Args:
        progress_callback: If provided, called after each AP result with the CrawlResult.
        stop_check: If provided and returns True, breaks the loop early (controlled stop).
        use_tqdm: If False, suppresses all console output (for GUI mode).
    """
    results: list[CrawlResult] = []
    total = len(ap_list)
    if already_done is None:
        already_done = set()

    # Count APs to actually process (exclude already done)
    to_process = [ap for ap in ap_list if ap.name not in already_done]
    success_count = 0
    fail_count = 0

    pbar = None
    if tqdm is not None and use_tqdm:
        pbar = tqdm(
            total=len(to_process),
            bar_format="{desc} {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            ncols=90,
        )
        pbar.set_description(f"Crawling: {ANSI_GREEN}✅ 0{ANSI_RESET} | {ANSI_RED}❌ 0{ANSI_RESET}")

    try:
        for n, ap in enumerate(ap_list, start=1):
            # Check if stop has been requested
            if stop_check is not None and stop_check():
                logger.info("Crawl stopped by stop_check at AP %d/%d", n, total)
                break

            # Skip already-completed APs (resume mode)
            if ap.name in already_done:
                logger.info("Skipped AP '%s' — already in CSV (resume mode)", ap.name)
                continue

            logger.info("Processing AP %d/%d: %s (ID: %d, IP: %s)", n, total, ap.name, ap.ap_id, ap.ip)

            # Skip offline APs
            if ap.is_offline:
                if pbar is not None:
                    pbar.write(f"  {ANSI_YELLOW}⏭️{ANSI_RESET}  [{n}/{total}] {ap.name} {ANSI_DIM}— offline, skipped{ANSI_RESET}")
                logger.info("Skipped AP '%s' — no IP assigned", ap.name)
                result = CrawlResult(
                    ap_name=ap.name,
                    ap_ip=ap.ip,
                    switch_name="N/A",
                    switch_ip="N/A",
                    status="skipped",
                )
                results.append(result)
                if progress_callback is not None:
                    progress_callback(result)
                if pbar is not None:
                    pbar.update(1)
                continue

            # Crawl online AP
            try:
                ap_results = crawl_single_ap(session, ap, switch_dict, config)
                success_names = [r.switch_name for r in ap_results if r.status == "success"]
                failed_results_ap = [r for r in ap_results if r.status == "failed"]

                if success_names:
                    neighbors_str = ", ".join(success_names)
                    if pbar is not None:
                        pbar.write(f"  {ANSI_GREEN}✅{ANSI_RESET} [{n}/{total}] {ap.name} → {ANSI_CYAN}{neighbors_str}{ANSI_RESET}")
                    for r in ap_results:
                        if r.status == "success":
                            logger.info("Success: %s -> %s (%s)", ap.name, r.switch_name, r.switch_ip)
                    success_count += 1
                elif failed_results_ap:
                    err_short = failed_results_ap[0].error[:50]
                    if pbar is not None:
                        pbar.write(f"  {ANSI_RED}❌{ANSI_RESET} [{n}/{total}] {ap.name} {ANSI_DIM}— {err_short}{ANSI_RESET}")
                    for r in failed_results_ap:
                        logger.warning("Failed: %s — %s", ap.name, r.error)
                    fail_count += 1

                results.extend(ap_results)
                if progress_callback is not None:
                    for r in ap_results:
                        progress_callback(r)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                error_msg = str(e)

                # Detect socket closed → attempt reconnect
                if "socket is closed" in error_msg.lower() or "socket exception" in error_msg.lower():
                    if pbar is not None:
                        pbar.write(f"  {ANSI_YELLOW}⚡{ANSI_RESET} [{n}/{total}] {ap.name} {ANSI_YELLOW}— CONNECTION LOST{ANSI_RESET}")
                    logger.error("SSH connection lost at AP '%s' (ID: %d): %s", ap.name, ap.ap_id, error_msg)

                    # Attempt reconnect
                    reconnected = _reconnect(session, config, pbar)
                    if reconnected:
                        # Retry this AP after reconnect
                        try:
                            ap_results = crawl_single_ap(session, ap, switch_dict, config)
                            success_names = [r.switch_name for r in ap_results if r.status == "success"]
                            if success_names:
                                neighbors_str = ", ".join(success_names)
                                if pbar is not None:
                                    pbar.write(f"  {ANSI_GREEN}✅{ANSI_RESET} [{n}/{total}] {ap.name} (retry) → {ANSI_CYAN}{neighbors_str}{ANSI_RESET}")
                                for r in ap_results:
                                    if r.status == "success":
                                        logger.info("Success (after reconnect): %s -> %s (%s)", ap.name, r.switch_name, r.switch_ip)
                                success_count += 1
                            else:
                                if pbar is not None:
                                    pbar.write(f"  {ANSI_RED}❌{ANSI_RESET} [{n}/{total}] {ap.name} (retry) {ANSI_DIM}— failed{ANSI_RESET}")
                                fail_count += 1
                            results.extend(ap_results)
                            if progress_callback is not None:
                                for r in ap_results:
                                    progress_callback(r)
                        except Exception as retry_e:
                            if pbar is not None:
                                pbar.write(f"  {ANSI_RED}❌{ANSI_RESET} [{n}/{total}] {ap.name} (retry) {ANSI_DIM}— {retry_e}{ANSI_RESET}")
                            logger.error("Retry failed for AP '%s': %s", ap.name, retry_e)
                            fail_count += 1
                            result = CrawlResult(
                                ap_name=ap.name, ap_ip=ap.ip,
                                switch_name="N/A", switch_ip="N/A",
                                status="failed", error=str(retry_e),
                            )
                            results.append(result)
                            if progress_callback is not None:
                                progress_callback(result)
                    else:
                        # Reconnect failed — stop crawling
                        if pbar is not None:
                            pbar.write(f"\n  {ANSI_RED}💀 Failed to reconnect SSH. Stopping crawl.{ANSI_RESET}")
                        logger.error("SSH reconnect failed. Stopping crawl at AP %d/%d", n, total)
                        fail_count += 1
                        result = CrawlResult(
                            ap_name=ap.name, ap_ip=ap.ip,
                            switch_name="N/A", switch_ip="N/A",
                            status="failed", error="SSH reconnect failed",
                        )
                        results.append(result)
                        if progress_callback is not None:
                            progress_callback(result)
                        break
                else:
                    err_short = error_msg[:50]
                    if pbar is not None:
                        pbar.write(f"  {ANSI_RED}❌{ANSI_RESET} [{n}/{total}] {ap.name} {ANSI_DIM}— {err_short}{ANSI_RESET}")
                    logger.error("Exception crawling AP '%s' (ID: %d): %s", ap.name, ap.ap_id, error_msg)
                    fail_count += 1
                    result = CrawlResult(
                        ap_name=ap.name, ap_ip=ap.ip,
                        switch_name="N/A", switch_ip="N/A",
                        status="failed", error=error_msg,
                    )
                    results.append(result)
                    if progress_callback is not None:
                        progress_callback(result)

            # Update progress bar description with live counts
            if pbar is not None:
                pbar.set_description(f"Crawling: {ANSI_GREEN}✅ {success_count}{ANSI_RESET} | {ANSI_RED}❌ {fail_count}{ANSI_RESET}")
                pbar.update(1)

    except KeyboardInterrupt:
        if pbar is not None:
            pbar.write(f"\n  {ANSI_YELLOW}⚠️  Crawl interrupted by user (Ctrl+C){ANSI_RESET}")
        logger.info("Crawl interrupted by user at AP %d/%d", len(results) + 1, total)
    finally:
        if pbar is not None:
            pbar.close()

    return results


def _reconnect(session: SSHSession, config: Config, pbar=None) -> bool:
    """Attempt to reconnect SSH session to WAC.

    Returns True if reconnect successful, False otherwise.
    """
    for attempt in range(1, MAX_RECONNECT_ATTEMPTS + 1):
        msg = f"  {ANSI_YELLOW}🔄 Reconnecting SSH (attempt {attempt}/{MAX_RECONNECT_ATTEMPTS})...{ANSI_RESET}"
        if pbar:
            pbar.write(msg)
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
            if pbar:
                pbar.write(f"  {ANSI_GREEN}✅ Reconnected successfully{ANSI_RESET}")
            logger.info("SSH reconnect successful")
            return True
        except Exception as e:
            if pbar:
                pbar.write(f"  {ANSI_RED}❌ Attempt {attempt} failed: {e}{ANSI_RESET}")
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

        # Wait for AP prompt. Also detect WAC error messages so we fail fast
        # instead of waiting the full timeout.
        # Error patterns return to WAC system prompt [WAC-xxx] with error text.
        output = session.wait_for_prompt(
            patterns=[AP_PROMPT, WAC_SYSTEM_PROMPT],
            timeout=config.ap_connect_timeout,
            auto_respond=auto_respond_map,
        )

        # Check if we got a WAC system prompt instead of AP prompt
        # This means stelnet failed (e.g., "Login failed", "Error:")
        import re as _re
        if _re.search(WAC_SYSTEM_PROMPT, output) and not _re.search(AP_PROMPT, output):
            # Extract the error message from WAC output
            error_detail = "AP unreachable via stelnet"
            if "Login failed" in output:
                error_detail = "Login failed (WAC cannot obtain AP info)"
            elif "Error:" in output:
                # Extract the Error: line
                for line in output.splitlines():
                    if "Error:" in line:
                        error_detail = line.strip()
                        break
            elif "timed out" in output.lower() or "timeout" in output.lower():
                error_detail = "Connection to AP timed out"

            logger.warning("AP '%s' (ID: %d) stelnet rejected: %s", ap.name, ap.ap_id, error_detail)
            return [CrawlResult(
                ap_name=ap.name, ap_ip=ap.ip,
                switch_name="N/A", switch_ip="N/A",
                status="failed", error=error_detail,
            )]

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
            for neighbor in neighbors:
                switch_ip = switch_dict.get(neighbor.neighbor_dev, "N/A")
                results.append(CrawlResult(
                    ap_name=ap.name, ap_ip=ap.ip,
                    switch_name=neighbor.neighbor_dev, switch_ip=switch_ip,
                    status="success",
                    local_intf=neighbor.local_intf,
                    neighbor_intf=neighbor.neighbor_intf,
                ))
        else:
            results.append(CrawlResult(
                ap_name=ap.name, ap_ip=ap.ip,
                switch_name="N/A", switch_ip="N/A",
                status="success",
            ))

        # Step 7: Exit AP session and drain leftover buffer
        if not exit_ap_session(session):
            logger.warning(
                "AP '%s' did not return to WAC prompt after LLDP crawl; draining buffer before continuing",
                ap.name,
            )
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

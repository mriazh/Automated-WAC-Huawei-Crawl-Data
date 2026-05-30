"""Main entry point for WAC Huawei LLDP Crawl Data tool.

Wires all components together: config loading, file parsing,
SSH connection, AP crawling, CSV output, and summary display.

Supports resume mode: if lldp_result.csv exists, skips already-crawled APs.
Supports auto-reconnect: if SSH drops mid-crawl, reconnects and continues.
"""

import logging
import sys
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import load_config
from crawler import crawl_all_aps
from output import read_existing_csv, write_csv
from parsers import parse_ap_list, parse_switch_list
from ssh_client import SSHConnectionError, SSHSession

# Rich console for colorful output
console = Console()

# ANSI codes for tqdm.write (tqdm doesn't support rich markup)
ANSI_GREEN = "\033[92m"
ANSI_RED = "\033[91m"
ANSI_YELLOW = "\033[93m"
ANSI_CYAN = "\033[96m"
ANSI_DIM = "\033[2m"
ANSI_RESET = "\033[0m"

# Log file: single file, append mode with session separators
log_filename = "crawl.log"
file_handler = logging.FileHandler(log_filename, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
))

# Console: suppress log output (we use rich/tqdm for display)
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.CRITICAL)
console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

# Write session start marker
_logger = logging.getLogger(__name__)
_logger.info("")
_logger.info("=" * 60)
_logger.info("SESSION START — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
_logger.info("=" * 60)
_logger.info("")


def _log_session_summary(results: list, resumed_count: int = 0) -> None:
    """Write a detailed summary to the log file at end of session."""
    _logger.info("")
    _logger.info("=" * 60)
    _logger.info("SESSION SUMMARY")
    _logger.info("=" * 60)
    _logger.info("")

    if not results:
        _logger.info("No APs were processed this session.")
        return

    # Categorize results
    success_results = [r for r in results if r.status == "success"]
    failed_results = [r for r in results if r.status == "failed"]
    skipped_results = [r for r in results if r.status == "skipped"]

    # Group success results by AP name to find multi-neighbor APs
    ap_neighbors: dict[str, list] = {}
    for r in success_results:
        if r.ap_name not in ap_neighbors:
            ap_neighbors[r.ap_name] = []
        ap_neighbors[r.ap_name].append(r)

    single_neighbor_aps = {k: v for k, v in ap_neighbors.items() if len(v) == 1}
    multi_neighbor_aps = {k: v for k, v in ap_neighbors.items() if len(v) > 1}

    total_processed = len(set(r.ap_name for r in results))

    _logger.info("TOTALS:")
    _logger.info("  APs processed this run : %d", total_processed)
    if resumed_count > 0:
        _logger.info("  Previously completed   : %d (resume mode)", resumed_count)
    _logger.info("  Successful (single)    : %d APs", len(single_neighbor_aps))
    _logger.info("  Successful (multi)     : %d APs", len(multi_neighbor_aps))
    _logger.info("  Failed                 : %d APs", len(set(r.ap_name for r in failed_results)))
    _logger.info("  Skipped (offline)      : %d APs", len(skipped_results))
    _logger.info("")

    # --- Multi-neighbor APs (detailed) ---
    if multi_neighbor_aps:
        _logger.info("-" * 60)
        _logger.info("MULTI-NEIGHBOR APs (%d APs, multiple LLDP neighbors detected):", len(multi_neighbor_aps))
        _logger.info("-" * 60)
        for ap_name, neighbors in sorted(multi_neighbor_aps.items()):
            ap_ip = neighbors[0].ap_ip
            _logger.info("  %s (%s) — %d neighbors:", ap_name, ap_ip, len(neighbors))
            for i, r in enumerate(neighbors, 1):
                _logger.info("    %d. %s (%s)", i, r.switch_name, r.switch_ip)
        _logger.info("")

    # --- Failed APs (detailed) ---
    if failed_results:
        _logger.info("-" * 60)
        _logger.info("FAILED APs (%d):", len(set(r.ap_name for r in failed_results)))
        _logger.info("-" * 60)
        seen_failed = set()
        for r in failed_results:
            if r.ap_name not in seen_failed:
                seen_failed.add(r.ap_name)
                _logger.info("  %s (%s) — Reason: %s", r.ap_name, r.ap_ip, r.error)
        _logger.info("")

    # --- Skipped APs (offline) ---
    if skipped_results:
        _logger.info("-" * 60)
        _logger.info("SKIPPED APs — offline (%d):", len(skipped_results))
        _logger.info("-" * 60)
        for r in skipped_results:
            _logger.info("  %s (IP: %s)", r.ap_name, r.ap_ip)
        _logger.info("")

    # --- Success APs (single neighbor, compact list) ---
    if single_neighbor_aps:
        _logger.info("-" * 60)
        _logger.info("SUCCESSFUL APs — single neighbor (%d):", len(single_neighbor_aps))
        _logger.info("-" * 60)
        for ap_name, neighbors in sorted(single_neighbor_aps.items()):
            r = neighbors[0]
            _logger.info("  %s (%s) -> %s (%s)", r.ap_name, r.ap_ip, r.switch_name, r.switch_ip)
        _logger.info("")

    _logger.info("=" * 60)
    _logger.info("END OF SUMMARY")
    _logger.info("=" * 60)


def _display_rich_summary(results: list, filepath: str, resumed_count: int = 0) -> None:
    """Display a colorful summary table using rich."""
    success_count = sum(1 for r in results if r.status == "success")
    failed_count = len(set(r.ap_name for r in results if r.status == "failed"))
    skipped_count = sum(1 for r in results if r.status == "skipped")
    total_processed = len(set(r.ap_name for r in results))

    # Count unique APs with multiple neighbors
    ap_neighbors: dict[str, int] = {}
    for r in results:
        if r.status == "success":
            ap_neighbors[r.ap_name] = ap_neighbors.get(r.ap_name, 0) + 1
    multi_count = sum(1 for v in ap_neighbors.values() if v > 1)

    console.print()
    table = Table(title="📊 CRAWL SUMMARY", border_style="cyan", show_header=True)
    table.add_column("Metric", style="bold white")
    table.add_column("Value", justify="right")
    table.add_row("APs processed this run", str(total_processed))
    if resumed_count > 0:
        table.add_row("Previously completed", f"[dim]{resumed_count}[/dim]")
        table.add_row("Total in CSV", f"[bold cyan]{resumed_count + success_count}[/bold cyan]")
    table.add_row("[green]Successful[/green] (single neighbor)", f"[bold green]{len(ap_neighbors) - multi_count}[/bold green]")
    table.add_row("[green]Successful[/green] (multi-neighbor)", f"[bold green]{multi_count}[/bold green]")
    table.add_row("[red]Failed[/red]", f"[bold red]{failed_count}[/bold red]")
    table.add_row("[yellow]Skipped[/yellow] (offline)", f"[bold yellow]{skipped_count}[/bold yellow]")
    table.add_row("Output file", f"[dim]{filepath}[/dim]")
    console.print(table)
    console.print()


def main() -> None:
    """Main entry point.

    Supports resume: reads existing lldp_result.csv and skips completed APs.
    Supports auto-reconnect: if SSH drops, reconnects and continues.
    """
    session = None
    results = []
    resumed_count = 0
    try:
        console.print()
        console.print(Panel.fit(
            "[bold cyan]WAC HUAWEI LLDP CRAWL DATA[/bold cyan]",
            border_style="cyan",
            subtitle="[dim]Automated AP neighbor discovery[/dim]",
        ))

        config = load_config()
        ap_list = parse_ap_list()
        switch_dict = parse_switch_list()

        # Check for existing CSV to resume from
        already_done = read_existing_csv()
        # Only count APs that are still in the current list
        current_ap_names = {ap.name for ap in ap_list}
        already_done = already_done & current_ap_names
        resumed_count = len(already_done)

        remaining = len(ap_list) - resumed_count
        console.print()
        if resumed_count > 0:
            console.print(f"  [bold yellow]Mode[/bold yellow]     : RESUME (continuing previous crawl)")
            console.print(f"  [bold yellow]Done[/bold yellow]     : {resumed_count} APs already in lldp_result.csv")
            console.print(f"  [bold yellow]Remaining[/bold yellow]: {remaining} APs to crawl")
            _logger.info("=== RESUME MODE === %d done, %d remaining out of %d total", resumed_count, remaining, len(ap_list))
        else:
            console.print(f"  [bold cyan]Mode[/bold cyan]     : FRESH START (no previous results found)")
            console.print(f"  [bold cyan]Total APs[/bold cyan]: {len(ap_list)}")
            _logger.info("=== FRESH START === %d APs to crawl", len(ap_list))
        console.print()

        session = SSHSession(config)
        session.connect()
        session.enter_system_view()

        console.print("[green]Connected to WAC.[/green] Starting crawl...\n")
        _logger.info("SSH connected, entering crawl loop")

        results = crawl_all_aps(session, ap_list, switch_dict, config, already_done=already_done)

        # Write results (append if resuming, overwrite if fresh)
        if resumed_count > 0:
            filepath = write_csv(results, append_to_existing=True)
        else:
            filepath = write_csv(results)

        _display_rich_summary(results, filepath, resumed_count=resumed_count)

    except SSHConnectionError as e:
        console.print(f"\n[bold red]❌ {e}[/bold red]")
        _logger.error("SSH connection error: %s", e)
        sys.exit(1)
    except KeyboardInterrupt:
        console.print(f"\n\n[bold yellow]⚠️  Interrupted by user (Ctrl+C). Saving partial results...[/bold yellow]")
        if results:
            if resumed_count > 0:
                filepath = write_csv(results, append_to_existing=True)
            else:
                filepath = write_csv(results)
            _display_rich_summary(results, filepath, resumed_count=resumed_count)
        else:
            console.print("[dim]No results to save.[/dim]")
    finally:
        if session:
            session.disconnect()
        _log_session_summary(results, resumed_count)
        _logger.info("")
        _logger.info("=" * 60)
        _logger.info("SESSION END — %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        _logger.info("=" * 60)
        _logger.info("")


if __name__ == "__main__":
    main()

"""Property-based test for Order Preservation (Property 5).

**Validates: Requirements 5.1, 8.1**

Property 5: Order Preservation — CSV output maintains the same AP order as
the input list. Results are appended sequentially.

This test generates ordered AP lists, runs write_csv, and verifies that
CSV row order matches the input order.
"""

import csv
import os
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from crawler import CrawlResult
from output import write_csv


# --- Strategies ---

# Generate valid AP names: alphanumeric with hyphens
ap_name_strategy = st.text(
    alphabet=st.sampled_from(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"
    ),
    min_size=1,
    max_size=20,
)

# Generate valid IP addresses
ip_strategy = st.tuples(
    st.integers(min_value=1, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=1, max_value=254),
).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}")

# Generate switch names
switch_name_strategy = st.text(
    alphabet=st.sampled_from(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    ),
    min_size=1,
    max_size=20,
)

# Generate a single successful CrawlResult
crawl_result_success_strategy = st.builds(
    CrawlResult,
    ap_name=ap_name_strategy,
    ap_ip=ip_strategy,
    switch_name=switch_name_strategy,
    switch_ip=ip_strategy,
    status=st.just("success"),
    error=st.just(""),
)

# Generate a list of successful CrawlResults (1-30 items)
success_results_list_strategy = st.lists(
    crawl_result_success_strategy,
    min_size=1,
    max_size=30,
)


@given(results=success_results_list_strategy)
@settings(max_examples=100)
def test_csv_row_order_matches_input_order(results: list[CrawlResult]):
    """Property 5: The order of rows in the CSV output matches the order
    of results in the input list. The i-th successful result corresponds
    to the i-th data row in the CSV.

    **Validates: Requirements 5.1, 8.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = write_csv(results, output_dir=tmpdir)

        # Read back the CSV
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        # Verify header
        assert header == ["AP", "Switch"], f"Unexpected header: {header}"

        # Verify row count matches successful results
        successful = [r for r in results if r.status == "success"]
        assert len(rows) == len(successful), (
            f"Expected {len(successful)} data rows, got {len(rows)}"
        )

        # Verify order: each row matches the corresponding result
        for i, (row, result) in enumerate(zip(rows, successful)):
            expected_ap = f"{result.ap_name} ({result.ap_ip})"
            expected_switch = f"{result.switch_name} ({result.switch_ip})"
            assert row[0] == expected_ap, (
                f"Row {i}: expected AP '{expected_ap}', got '{row[0]}'"
            )
            assert row[1] == expected_switch, (
                f"Row {i}: expected Switch '{expected_switch}', got '{row[1]}'"
            )


# Generate a mixed list with success, skipped, and failed results
mixed_status_strategy = st.one_of(
    st.just("success"),
    st.just("skipped"),
    st.just("failed"),
)

crawl_result_mixed_strategy = st.builds(
    CrawlResult,
    ap_name=ap_name_strategy,
    ap_ip=ip_strategy,
    switch_name=switch_name_strategy,
    switch_ip=ip_strategy,
    status=mixed_status_strategy,
    error=st.just(""),
)

mixed_results_list_strategy = st.lists(
    crawl_result_mixed_strategy,
    min_size=1,
    max_size=30,
)


@given(results=mixed_results_list_strategy)
@settings(max_examples=100)
def test_csv_preserves_order_among_successful_results(results: list[CrawlResult]):
    """Property 5: When the input contains a mix of success, skipped, and failed
    results, the CSV rows preserve the relative order of successful results only.
    Non-successful results are filtered out but the order of successful ones is
    maintained.

    **Validates: Requirements 5.1, 8.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = write_csv(results, output_dir=tmpdir)

        # Read back the CSV
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            rows = list(reader)

        # Extract only successful results in their original order
        successful = [r for r in results if r.status == "success"]

        assert len(rows) == len(successful), (
            f"Expected {len(successful)} data rows, got {len(rows)}"
        )

        # Verify order is preserved for successful results
        for i, (row, result) in enumerate(zip(rows, successful)):
            expected_ap = f"{result.ap_name} ({result.ap_ip})"
            expected_switch = f"{result.switch_name} ({result.switch_ip})"
            assert row[0] == expected_ap, (
                f"Row {i}: expected AP '{expected_ap}', got '{row[0]}'"
            )
            assert row[1] == expected_switch, (
                f"Row {i}: expected Switch '{expected_switch}', got '{row[1]}'"
            )


@given(results=success_results_list_strategy)
@settings(max_examples=100)
def test_csv_sequential_append_preserves_order(results: list[CrawlResult]):
    """Property 5: When results are written in append mode (simulating
    sequential processing), the final CSV maintains the overall order.

    **Validates: Requirements 5.1, 8.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write first half, then append second half
        midpoint = len(results) // 2
        first_half = results[:midpoint] if midpoint > 0 else results[:1]
        second_half = results[midpoint:] if midpoint > 0 else results[1:]

        # Write first batch (creates file with header)
        write_csv(first_half, output_dir=tmpdir)

        # Append second batch
        if second_half:
            write_csv(second_half, output_dir=tmpdir, append_to_existing=True)

        # Read back the CSV
        filepath = os.path.join(tmpdir, "lldp_result.csv")
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)

        assert header == ["AP", "Switch"]

        # All results are successful, so total rows = first_half + second_half
        all_successful = first_half + second_half
        assert len(rows) == len(all_successful), (
            f"Expected {len(all_successful)} data rows, got {len(rows)}"
        )

        # Verify order matches the sequential append order
        for i, (row, result) in enumerate(zip(rows, all_successful)):
            expected_ap = f"{result.ap_name} ({result.ap_ip})"
            expected_switch = f"{result.switch_name} ({result.switch_ip})"
            assert row[0] == expected_ap, (
                f"Row {i}: expected AP '{expected_ap}', got '{row[0]}'"
            )
            assert row[1] == expected_switch, (
                f"Row {i}: expected Switch '{expected_switch}', got '{row[1]}'"
            )

"""Property-based test for No Data Loss (Property 2).

**Validates: Requirements 8.1, 8.2**

Property 2: No Data Loss — All successful LLDP results are written to the CSV file.
The number of data rows in the CSV equals the number of CrawlResults with status "success".

This test generates random lists of CrawlResult with mixed statuses and verifies
that the CSV row count matches the count of results with status "success".
"""

import csv
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from crawler import CrawlResult
from output import write_csv


# --- Strategies ---

# Generate valid AP names
ap_name_strategy = st.text(
    alphabet=st.sampled_from(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    ),
    min_size=1,
    max_size=30,
)

# Generate valid IP addresses
ip_strategy = st.tuples(
    st.integers(min_value=1, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=0, max_value=255),
    st.integers(min_value=1, max_value=254),
).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}")

# Generate switch names (can be "N/A" for failed/skipped)
switch_name_strategy = st.one_of(
    ap_name_strategy,
    st.just("N/A"),
)

# Generate a CrawlResult with status "success"
success_result_strategy = st.builds(
    CrawlResult,
    ap_name=ap_name_strategy,
    ap_ip=ip_strategy,
    switch_name=switch_name_strategy,
    switch_ip=st.one_of(ip_strategy, st.just("N/A")),
    status=st.just("success"),
    error=st.just(""),
)

# Generate a CrawlResult with status "skipped"
skipped_result_strategy = st.builds(
    CrawlResult,
    ap_name=ap_name_strategy,
    ap_ip=st.one_of(ip_strategy, st.just("--")),
    switch_name=st.just("N/A"),
    switch_ip=st.just("N/A"),
    status=st.just("skipped"),
    error=st.just(""),
)

# Generate a CrawlResult with status "failed"
failed_result_strategy = st.builds(
    CrawlResult,
    ap_name=ap_name_strategy,
    ap_ip=ip_strategy,
    switch_name=st.just("N/A"),
    switch_ip=st.just("N/A"),
    status=st.just("failed"),
    error=st.text(min_size=1, max_size=50),
)

# Generate a mixed list of CrawlResults with various statuses
mixed_results_strategy = st.lists(
    st.one_of(success_result_strategy, skipped_result_strategy, failed_result_strategy),
    min_size=0,
    max_size=50,
)


@given(results=mixed_results_strategy)
@settings(max_examples=100)
def test_csv_row_count_equals_success_count(results: list[CrawlResult]):
    """Property 2: No Data Loss — The number of data rows in the CSV file
    equals the number of CrawlResults with status "success".

    **Validates: Requirements 8.1, 8.2**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Write CSV using the function under test
        filepath = write_csv(results, output_dir=tmp_dir)

        # Count expected successful results
        expected_success_count = sum(1 for r in results if r.status == "success")

        # Read the CSV and count data rows (excluding header)
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # First row is always the header
        assert rows[0] == ["AP", "Local Intf", "Switch", "Neighbor Intf"], (
            f"Expected new header but got {rows[0]}"
        )

        # Data rows are everything after the header
        data_rows = rows[1:]

        # Property: data row count equals success count
        assert len(data_rows) == expected_success_count, (
            f"Expected {expected_success_count} data rows but got {len(data_rows)}. "
            f"Results had {len(results)} total: "
            f"{sum(1 for r in results if r.status == 'success')} success, "
            f"{sum(1 for r in results if r.status == 'skipped')} skipped, "
            f"{sum(1 for r in results if r.status == 'failed')} failed."
        )


@given(results=st.lists(success_result_strategy, min_size=1, max_size=30))
@settings(max_examples=100)
def test_all_success_results_appear_in_csv(results: list[CrawlResult]):
    """Property 2 extension: When all results are successful, every result
    appears as a data row in the CSV. No successful result is dropped.

    **Validates: Requirements 8.1, 8.2**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        filepath = write_csv(results, output_dir=tmp_dir)

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        data_rows = rows[1:]  # skip header

        # Property: every successful result has a corresponding row
        assert len(data_rows) == len(results), (
            f"Expected {len(results)} data rows for all-success input, got {len(data_rows)}"
        )

        # Verify each row contains the expected AP and Switch info
        for i, result in enumerate(results):
            expected_ap = f"{result.ap_name} ({result.ap_ip})"
            expected_switch = f"{result.switch_name} ({result.switch_ip})"
            assert data_rows[i][0] == expected_ap, (
                f"Row {i} AP mismatch: expected '{expected_ap}', got '{data_rows[i][0]}'"
            )
            assert data_rows[i][1] == result.local_intf, (
                f"Row {i} Local Intf mismatch: expected '{result.local_intf}', got '{data_rows[i][1]}'"
            )
            assert data_rows[i][2] == expected_switch, (
                f"Row {i} Switch mismatch: expected '{expected_switch}', got '{data_rows[i][2]}'"
            )
            assert data_rows[i][3] == result.neighbor_intf, (
                f"Row {i} Neighbor Intf mismatch: expected '{result.neighbor_intf}', got '{data_rows[i][3]}'"
            )

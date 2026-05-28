"""Property-based test for Completeness (Property 1).

**Validates: Requirements 5.1, 9.3**

Property 1: Completeness — Every AP in list_ap.txt produces exactly one CrawlResult.
Total results count equals total valid AP entries parsed.

This test generates random AP lists and verifies parse_ap_list returns the correct
count of APEntry objects — one per valid line in the input.
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from parsers import APEntry, parse_ap_list


# --- Strategies ---

# Generate valid AP names: alphanumeric with hyphens, non-empty
ap_name_strategy = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"),
    min_size=1,
    max_size=30,
)

# Generate valid IP addresses or "--" for offline APs
ip_strategy = st.one_of(
    st.tuples(
        st.integers(min_value=1, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=0, max_value=255),
        st.integers(min_value=1, max_value=254),
    ).map(lambda t: f"{t[0]}.{t[1]}.{t[2]}.{t[3]}"),
    st.just("--"),
)

# Generate valid AP IDs (non-negative integers)
ap_id_strategy = st.integers(min_value=0, max_value=9999)

# A single valid AP line (tab-separated: name, ip, id)
valid_ap_line_strategy = st.tuples(ap_name_strategy, ip_strategy, ap_id_strategy).map(
    lambda t: f"{t[0]}\t{t[1]}\t{t[2]}"
)

# Generate a non-empty list of valid AP lines
valid_ap_list_strategy = st.lists(valid_ap_line_strategy, min_size=1, max_size=50)


@given(ap_lines=valid_ap_list_strategy)
@settings(max_examples=100)
def test_parse_ap_list_returns_one_entry_per_valid_line(ap_lines: list[str]):
    """Property 1: Completeness — parse_ap_list returns exactly one APEntry
    per valid line in the input file. The count of returned entries equals
    the count of valid input lines.

    **Validates: Requirements 5.1, 9.3**
    """
    # Write the generated AP lines to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        content = "\n".join(ap_lines) + "\n"
        f.write(content)
        tmp_path = f.name

    try:
        result = parse_ap_list(tmp_path)

        # Property: the number of APEntry objects equals the number of valid input lines
        assert len(result) == len(ap_lines), (
            f"Expected {len(ap_lines)} entries but got {len(result)}"
        )

        # Each result is an APEntry instance
        for entry in result:
            assert isinstance(entry, APEntry)

        # Each entry has a non-empty name
        for entry in result:
            assert entry.name != ""

        # Offline status is correctly determined
        for i, entry in enumerate(result):
            line_parts = ap_lines[i].split("\t")
            expected_offline = line_parts[1].strip() == "--"
            assert entry.is_offline == expected_offline, (
                f"Entry {i} offline status mismatch: expected {expected_offline}, got {entry.is_offline}"
            )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@given(
    valid_lines=st.lists(valid_ap_line_strategy, min_size=1, max_size=20),
    blank_lines_count=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100)
def test_blank_lines_do_not_affect_entry_count(valid_lines: list[str], blank_lines_count: int):
    """Property 1 extension: Blank lines are skipped and do not produce entries.
    The count of APEntry objects equals only the count of valid (non-blank) lines.

    **Validates: Requirements 5.1, 9.3**
    """
    # Interleave blank lines with valid lines
    all_lines = []
    for line in valid_lines:
        # Add some blank lines before each valid line
        all_lines.extend([""] * (blank_lines_count // max(len(valid_lines), 1)))
        all_lines.append(line)
    # Add trailing blank lines
    all_lines.extend([""] * blank_lines_count)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        content = "\n".join(all_lines) + "\n"
        f.write(content)
        tmp_path = f.name

    try:
        result = parse_ap_list(tmp_path)

        # Property: count equals only valid lines, blank lines are ignored
        assert len(result) == len(valid_lines), (
            f"Expected {len(valid_lines)} entries but got {len(result)} "
            f"(blank lines should not produce entries)"
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

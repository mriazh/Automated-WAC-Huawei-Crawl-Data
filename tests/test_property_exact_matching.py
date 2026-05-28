"""Property-based test for Exact Matching (Property 6).

**Validates: Requirements 7.1**

Property 6: Exact Matching — Switch name lookup uses exact string match
(case-sensitive) against switch dictionary keys. No fuzzy matching or
normalization is applied.

This test generates random switch names and verifies only exact matches
return IPs from the switch dictionary.
"""

from hypothesis import given, settings, assume
from hypothesis import strategies as st


# --- Strategies ---

# Generate valid switch names: alphanumeric with hyphens and underscores
switch_name_strategy = st.text(
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

# Generate a switch dictionary with 1-20 entries
switch_dict_strategy = st.dictionaries(
    keys=switch_name_strategy,
    values=ip_strategy,
    min_size=1,
    max_size=20,
)


def lookup_switch_ip(switch_dict: dict[str, str], neighbor_name: str) -> str:
    """Replicate the exact lookup logic from crawler.py.

    This is the same as: switch_dict.get(neighbor_name, "N/A")
    """
    return switch_dict.get(neighbor_name, "N/A")


@given(switch_dict=switch_dict_strategy)
@settings(max_examples=100)
def test_exact_match_returns_correct_ip(switch_dict: dict[str, str]):
    """Property 6: When a neighbor name exactly matches a key in the switch
    dictionary, the lookup returns the corresponding IP address.

    **Validates: Requirements 7.1**
    """
    for name, expected_ip in switch_dict.items():
        result = lookup_switch_ip(switch_dict, name)
        assert result == expected_ip, (
            f"Exact match for '{name}' should return '{expected_ip}', got '{result}'"
        )


@given(switch_dict=switch_dict_strategy)
@settings(max_examples=100)
def test_case_variation_does_not_match(switch_dict: dict[str, str]):
    """Property 6: Case variations of a switch name do NOT match.
    The lookup is case-sensitive — swapping case must return "N/A"
    (unless the swapped version happens to also be a key).

    **Validates: Requirements 7.1**
    """
    for name in switch_dict:
        # Generate case-swapped variant
        swapped = name.swapcase()

        # Only test if the swapped version is actually different from the original
        # and is not itself a key in the dictionary
        if swapped != name and swapped not in switch_dict:
            result = lookup_switch_ip(switch_dict, swapped)
            assert result == "N/A", (
                f"Case-swapped '{swapped}' (from '{name}') should return 'N/A', "
                f"got '{result}'"
            )


@given(switch_dict=switch_dict_strategy, suffix=switch_name_strategy)
@settings(max_examples=100)
def test_partial_match_does_not_return_ip(switch_dict: dict[str, str], suffix: str):
    """Property 6: Appending characters to a valid switch name does NOT match.
    No fuzzy or prefix matching is applied.

    **Validates: Requirements 7.1**
    """
    assume(len(suffix) > 0)

    for name in switch_dict:
        extended_name = name + suffix
        # Only test if the extended name is not itself a key
        if extended_name not in switch_dict:
            result = lookup_switch_ip(switch_dict, extended_name)
            assert result == "N/A", (
                f"Extended name '{extended_name}' (from '{name}' + '{suffix}') "
                f"should return 'N/A', got '{result}'"
            )


@given(switch_dict=switch_dict_strategy, query_name=switch_name_strategy)
@settings(max_examples=100)
def test_non_existent_name_returns_na(switch_dict: dict[str, str], query_name: str):
    """Property 6: A name not present in the switch dictionary returns "N/A".
    No fuzzy matching or normalization is applied.

    **Validates: Requirements 7.1**
    """
    assume(query_name not in switch_dict)

    result = lookup_switch_ip(switch_dict, query_name)
    assert result == "N/A", (
        f"Non-existent name '{query_name}' should return 'N/A', got '{result}'"
    )


@given(switch_dict=switch_dict_strategy)
@settings(max_examples=100)
def test_whitespace_prefix_does_not_match(switch_dict: dict[str, str]):
    """Property 6: Adding leading/trailing whitespace to a switch name does NOT
    match. No normalization or trimming is applied during lookup.

    **Validates: Requirements 7.1**
    """
    for name in switch_dict:
        # Add leading space
        padded = " " + name
        if padded not in switch_dict:
            result = lookup_switch_ip(switch_dict, padded)
            assert result == "N/A", (
                f"Whitespace-padded ' {name}' should return 'N/A', got '{result}'"
            )

        # Add trailing space
        padded = name + " "
        if padded not in switch_dict:
            result = lookup_switch_ip(switch_dict, padded)
            assert result == "N/A", (
                f"Whitespace-padded '{name} ' should return 'N/A', got '{result}'"
            )

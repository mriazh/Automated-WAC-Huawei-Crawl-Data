"""Unit tests for parsers.py — AP list, switch list, and LLDP output parsing."""

import os
import sys
import tempfile

import pytest

from parsers import APEntry, parse_ap_list, parse_lldp_output, parse_switch_list


# ============================================================
# parse_ap_list tests
# ============================================================


class TestParseApList:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "list_ap.txt"
        f.write_text("AP-TEST-01\t172.16.1.1\t0\nAP-TEST-02\t172.16.1.2\t1\n")
        result = parse_ap_list(str(f))
        assert len(result) == 2
        assert result[0].name == "AP-TEST-01"
        assert result[0].ip == "172.16.1.1"
        assert result[0].ap_id == 0
        assert result[0].is_offline is False

    def test_offline_ap(self, tmp_path):
        f = tmp_path / "list_ap.txt"
        f.write_text("AP-OFFLINE\t--\t5\n")
        result = parse_ap_list(str(f))
        assert result[0].is_offline is True
        assert result[0].ip == "--"

    def test_skip_blank_lines(self, tmp_path):
        f = tmp_path / "list_ap.txt"
        f.write_text("\nAP-TEST\t10.0.0.1\t0\n\n\n")
        result = parse_ap_list(str(f))
        assert len(result) == 1

    def test_skip_malformed_lines(self, tmp_path):
        f = tmp_path / "list_ap.txt"
        f.write_text("AP-GOOD\t10.0.0.1\t0\nBAD LINE NO TABS\nAP-GOOD2\t10.0.0.2\t1\n")
        result = parse_ap_list(str(f))
        assert len(result) == 2

    def test_missing_file_exits(self):
        with pytest.raises(SystemExit):
            parse_ap_list("/nonexistent/path/list_ap.txt")

    def test_empty_file_exits(self, tmp_path):
        f = tmp_path / "list_ap.txt"
        f.write_text("\n\n\n")
        with pytest.raises(SystemExit):
            parse_ap_list(str(f))

    def test_invalid_id_skipped(self, tmp_path):
        f = tmp_path / "list_ap.txt"
        f.write_text("AP-BAD\t10.0.0.1\tABC\nAP-GOOD\t10.0.0.2\t1\n")
        result = parse_ap_list(str(f))
        assert len(result) == 1
        assert result[0].name == "AP-GOOD"

    def test_all_offline_entries(self, tmp_path):
        """All APs are offline (ip == '--') — still valid entries."""
        f = tmp_path / "list_ap.txt"
        f.write_text("AP-OFF-01\t--\t10\nAP-OFF-02\t--\t11\nAP-OFF-03\t--\t12\n")
        result = parse_ap_list(str(f))
        assert len(result) == 3
        assert all(entry.is_offline for entry in result)
        assert all(entry.ip == "--" for entry in result)
        assert result[0].name == "AP-OFF-01"
        assert result[1].ap_id == 11
        assert result[2].name == "AP-OFF-03"


# ============================================================
# parse_switch_list tests
# ============================================================


class TestParseSwitchList:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "list_switch.txt"
        f.write_text("ASW01-HG4-1A\t172.16.13.201\nSW-MD-L1-2530\t172.16.12.163\n")
        result = parse_switch_list(str(f))
        assert result["ASW01-HG4-1A"] == "172.16.13.201"
        assert result["SW-MD-L1-2530"] == "172.16.12.163"

    def test_whitespace_trimming(self, tmp_path):
        f = tmp_path / "list_switch.txt"
        f.write_text("CORE DISTRI HG4 \t 172.16.13.1 \n")
        result = parse_switch_list(str(f))
        assert result["CORE DISTRI HG4"] == "172.16.13.1"

    def test_duplicate_uses_last(self, tmp_path):
        f = tmp_path / "list_switch.txt"
        f.write_text("SW-DUP\t10.0.0.1\nSW-DUP\t10.0.0.2\n")
        result = parse_switch_list(str(f))
        assert result["SW-DUP"] == "10.0.0.2"

    def test_skip_malformed(self, tmp_path):
        f = tmp_path / "list_switch.txt"
        f.write_text("GOOD\t10.0.0.1\nBAD LINE\nGOOD2\t10.0.0.2\n")
        result = parse_switch_list(str(f))
        assert len(result) == 2

    def test_missing_file_exits(self):
        with pytest.raises(SystemExit):
            parse_switch_list("/nonexistent/path/list_switch.txt")


# ============================================================
# parse_lldp_output tests
# ============================================================


class TestParseLldpOutput:
    def test_valid_output(self):
        output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            ASW02-HG3-L2RW                   85                        102\n"
        )
        assert parse_lldp_output(output) == ["ASW02-HG3-L2RW"]

    def test_switch_name_with_spaces(self):
        output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            CORE DISTRI HG4                  85                        102\n"
        )
        assert parse_lldp_output(output) == ["CORE DISTRI HG4"]

    def test_empty_output(self):
        assert parse_lldp_output("") == []
        assert parse_lldp_output("   ") == []

    def test_no_header(self):
        output = "Some random text\nNo LLDP data here\n"
        assert parse_lldp_output(output, ap_name="TEST") == []

    def test_header_only_no_data(self):
        output = "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
        assert parse_lldp_output(output) == []

    def test_skip_prompt_lines(self):
        output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "<AP-H3-L1-IN11>\n"
        )
        assert parse_lldp_output(output) == []

    def test_multiple_rows_returns_all(self):
        output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            SWITCH-A                         1                         100\n"
            "GE0/0/1            SWITCH-B                         2                         100\n"
        )
        result = parse_lldp_output(output)
        assert result == ["SWITCH-A", "SWITCH-B"]

    def test_with_ap_prompt_before_data(self):
        output = (
            "<AP-TEST>display lldp neighbor brief\n"
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            SW-TEST-L1                       5                         120\n"
            "<AP-TEST>\n"
        )
        assert parse_lldp_output(output, ap_name="AP-TEST") == ["SW-TEST-L1"]

    def test_three_neighbors(self):
        output = (
            "Local Intf         Neighbor Dev                     Neighbor Intf             Exptime\n"
            "GE0/0/0            AP-MD-L1-IN07                    GE0/0/0                   116\n"
            "GE0/0/0            AP-MD-L1-IN14                    GE0/0/0                   117\n"
            "GE0/0/0            ASW01-MD-L1                      178                       119\n"
        )
        result = parse_lldp_output(output)
        assert result == ["AP-MD-L1-IN07", "AP-MD-L1-IN14", "ASW01-MD-L1"]

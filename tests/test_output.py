"""Unit tests for output.py — CSV writing, reading, and resume logic."""

import csv
import os

import pytest

from crawler import CrawlResult
from output import CSV_FILENAME, print_summary, read_existing_csv, write_csv


# ============================================================
# write_csv tests
# ============================================================


class TestWriteCsv:
    def test_writes_successful_results(self, tmp_path):
        results = [
            CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
            CrawlResult("AP-2", "10.0.0.2", "SW-2", "10.0.1.2", "success"),
        ]
        filepath = write_csv(results, output_dir=str(tmp_path))
        assert os.path.exists(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == ["AP", "Switch"]
        assert rows[1] == ["AP-1 (10.0.0.1)", "SW-1 (10.0.1.1)"]
        assert rows[2] == ["AP-2 (10.0.0.2)", "SW-2 (10.0.1.2)"]

    def test_mixed_results_only_writes_success(self, tmp_path):
        """write_csv with mixed results: only success rows appear in CSV."""
        results = [
            CrawlResult("AP-OK", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
            CrawlResult("AP-SKIP", "--", "N/A", "N/A", "skipped"),
            CrawlResult("AP-FAIL", "10.0.0.3", "N/A", "N/A", "failed", "timeout"),
            CrawlResult("AP-OK2", "10.0.0.4", "SW-2", "10.0.1.2", "success"),
        ]
        filepath = write_csv(results, output_dir=str(tmp_path))

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # Header + 2 success rows only
        assert len(rows) == 3
        assert rows[0] == ["AP", "Switch"]
        assert rows[1] == ["AP-OK (10.0.0.1)", "SW-1 (10.0.1.1)"]
        assert rows[2] == ["AP-OK2 (10.0.0.4)", "SW-2 (10.0.1.2)"]

    def test_skips_failed_and_skipped(self, tmp_path):
        results = [
            CrawlResult("AP-OK", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
            CrawlResult("AP-FAIL", "10.0.0.2", "N/A", "N/A", "failed", "timeout"),
            CrawlResult("AP-SKIP", "--", "N/A", "N/A", "skipped"),
        ]
        filepath = write_csv(results, output_dir=str(tmp_path))

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 2  # header + 1 success

    def test_zero_successful_results_header_only(self, tmp_path):
        """write_csv with zero successful results generates header-only CSV."""
        results = [
            CrawlResult("AP-FAIL", "10.0.0.1", "N/A", "N/A", "failed", "timeout"),
            CrawlResult("AP-SKIP", "--", "N/A", "N/A", "skipped"),
        ]
        filepath = write_csv(results, output_dir=str(tmp_path))

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0] == ["AP", "Switch"]

    def test_empty_results_header_only(self, tmp_path):
        """write_csv with empty list generates header-only CSV."""
        results = []
        filepath = write_csv(results, output_dir=str(tmp_path))

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0] == ["AP", "Switch"]

    def test_csv_filename_matches_expected_pattern(self, tmp_path):
        """CSV filename is lldp_result.csv (static name, overwrite mode)."""
        results = [CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success")]
        filepath = write_csv(results, output_dir=str(tmp_path))
        assert os.path.basename(filepath) == "lldp_result.csv"
        assert filepath == os.path.join(str(tmp_path), CSV_FILENAME)

    def test_append_mode(self, tmp_path):
        # Write initial results
        results1 = [CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success")]
        write_csv(results1, output_dir=str(tmp_path))

        # Append more results
        results2 = [CrawlResult("AP-2", "10.0.0.2", "SW-2", "10.0.1.2", "success")]
        filepath = write_csv(results2, output_dir=str(tmp_path), append_to_existing=True)

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 3  # header + 2 data rows
        assert "AP-1" in rows[1][0]
        assert "AP-2" in rows[2][0]

    def test_filename_is_static(self, tmp_path):
        results = [CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success")]
        filepath = write_csv(results, output_dir=str(tmp_path))
        assert os.path.basename(filepath) == CSV_FILENAME


# ============================================================
# read_existing_csv tests
# ============================================================


class TestReadExistingCsv:
    def test_reads_ap_names(self, tmp_path):
        csv_file = tmp_path / CSV_FILENAME
        csv_file.write_text('"AP","Switch"\n"AP-TEST-01 (10.0.0.1)","SW-1 (10.0.1.1)"\n"AP-TEST-02 (10.0.0.2)","SW-2 (10.0.1.2)"\n')
        result = read_existing_csv(str(tmp_path))
        assert "AP-TEST-01" in result
        assert "AP-TEST-02" in result
        assert len(result) == 2

    def test_empty_file_returns_empty_set(self, tmp_path):
        csv_file = tmp_path / CSV_FILENAME
        csv_file.write_text('"AP","Switch"\n')
        result = read_existing_csv(str(tmp_path))
        assert len(result) == 0

    def test_no_file_returns_empty_set(self, tmp_path):
        result = read_existing_csv(str(tmp_path))
        assert len(result) == 0

    def test_handles_ap_name_with_spaces(self, tmp_path):
        csv_file = tmp_path / CSV_FILENAME
        csv_file.write_text('"AP","Switch"\n"AP-BLDG-A-L1 55 (192.0.2.50)","SW-BLDG-A-1D (198.51.100.40)"\n')
        result = read_existing_csv(str(tmp_path))
        assert "AP-BLDG-A-L1 55" in result


# ============================================================
# print_summary tests
# ============================================================


class TestPrintSummary:
    def test_basic_summary(self, capsys):
        results = [
            CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
            CrawlResult("AP-2", "--", "N/A", "N/A", "skipped"),
            CrawlResult("AP-3", "10.0.0.3", "N/A", "N/A", "failed", "timeout"),
        ]
        print_summary(results, "lldp_result.csv")
        output = capsys.readouterr().out
        assert "Total APs processed this run: 3" in output
        assert "Successful: 1" in output
        assert "Skipped (offline): 1" in output
        assert "Failed: 1" in output

    def test_summary_shows_output_filepath(self, capsys):
        """print_summary displays the output file path."""
        results = [
            CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
        ]
        filepath = "/some/path/lldp_result.csv"
        print_summary(results, filepath)
        output = capsys.readouterr().out
        assert f"Output file: {filepath}" in output

    def test_summary_with_all_statuses(self, capsys):
        """print_summary correctly counts mixed statuses."""
        results = [
            CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
            CrawlResult("AP-2", "10.0.0.2", "SW-2", "10.0.1.2", "success"),
            CrawlResult("AP-3", "--", "N/A", "N/A", "skipped"),
            CrawlResult("AP-4", "--", "N/A", "N/A", "skipped"),
            CrawlResult("AP-5", "--", "N/A", "N/A", "skipped"),
            CrawlResult("AP-6", "10.0.0.6", "N/A", "N/A", "failed", "timeout"),
        ]
        print_summary(results, "lldp_result.csv")
        output = capsys.readouterr().out
        assert "Total APs processed this run: 6" in output
        assert "Successful: 2" in output
        assert "Skipped (offline): 3" in output
        assert "Failed: 1" in output

    def test_resume_summary(self, capsys):
        results = [
            CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
        ]
        print_summary(results, "lldp_result.csv", resumed_count=149)
        output = capsys.readouterr().out
        assert "Previously completed: 149" in output
        assert "Total in CSV: 150" in output

    def test_summary_header_present(self, capsys):
        """print_summary includes the summary header line."""
        results = []
        print_summary(results, "lldp_result.csv")
        output = capsys.readouterr().out
        assert "--- Crawl Summary ---" in output

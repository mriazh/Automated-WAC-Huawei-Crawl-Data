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

    def test_empty_results_header_only(self, tmp_path):
        results = []
        filepath = write_csv(results, output_dir=str(tmp_path))

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0] == ["AP", "Switch"]

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
        csv_file.write_text('"AP","Switch"\n"AP-H4-L1-OUT 55 (172.16.24.150)","ASW01-HG4-1D (172.16.13.204)"\n')
        result = read_existing_csv(str(tmp_path))
        assert "AP-H4-L1-OUT 55" in result


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

    def test_resume_summary(self, capsys):
        results = [
            CrawlResult("AP-1", "10.0.0.1", "SW-1", "10.0.1.1", "success"),
        ]
        print_summary(results, "lldp_result.csv", resumed_count=149)
        output = capsys.readouterr().out
        assert "Previously completed: 149" in output
        assert "Total in CSV: 150" in output

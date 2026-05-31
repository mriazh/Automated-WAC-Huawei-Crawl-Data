"""Unit tests for gui/validators.py module."""

import os
import tempfile

import pytest

from gui.validators import validate_login_fields, validate_paths, validate_port


class TestValidatePort:
    """Tests for validate_port function."""

    def test_valid_port_minimum(self):
        valid, error = validate_port("1")
        assert valid is True
        assert error == ""

    def test_valid_port_maximum(self):
        valid, error = validate_port("65535")
        assert valid is True
        assert error == ""

    def test_valid_port_common(self):
        valid, error = validate_port("22")
        assert valid is True
        assert error == ""

    def test_valid_port_with_whitespace(self):
        valid, error = validate_port("  8080  ")
        assert valid is True
        assert error == ""

    def test_invalid_port_zero(self):
        valid, error = validate_port("0")
        assert valid is False
        assert "between 1 and 65535" in error

    def test_invalid_port_negative(self):
        valid, error = validate_port("-1")
        assert valid is False
        assert "between 1 and 65535" in error

    def test_invalid_port_too_high(self):
        valid, error = validate_port("65536")
        assert valid is False
        assert "between 1 and 65535" in error

    def test_invalid_port_non_numeric(self):
        valid, error = validate_port("abc")
        assert valid is False
        assert "valid integer" in error

    def test_invalid_port_empty(self):
        valid, error = validate_port("")
        assert valid is False
        assert "required" in error

    def test_invalid_port_whitespace_only(self):
        valid, error = validate_port("   ")
        assert valid is False
        assert "required" in error

    def test_invalid_port_float(self):
        valid, error = validate_port("22.5")
        assert valid is False
        assert "valid integer" in error


class TestValidateLoginFields:
    """Tests for validate_login_fields function."""

    def test_all_valid(self):
        errors = validate_login_fields("192.168.1.1", "22", "admin", "secret")
        assert errors == {}

    def test_empty_host(self):
        errors = validate_login_fields("", "22", "admin", "secret")
        assert "host" in errors
        assert len(errors) == 1

    def test_empty_port(self):
        errors = validate_login_fields("192.168.1.1", "", "admin", "secret")
        assert "port" in errors

    def test_invalid_port(self):
        errors = validate_login_fields("192.168.1.1", "99999", "admin", "secret")
        assert "port" in errors

    def test_empty_username(self):
        errors = validate_login_fields("192.168.1.1", "22", "", "secret")
        assert "username" in errors

    def test_empty_password(self):
        errors = validate_login_fields("192.168.1.1", "22", "admin", "")
        assert "password" in errors

    def test_all_empty(self):
        errors = validate_login_fields("", "", "", "")
        assert "host" in errors
        assert "port" in errors
        assert "username" in errors
        assert "password" in errors
        assert len(errors) == 4

    def test_whitespace_only_fields(self):
        errors = validate_login_fields("  ", "  ", "  ", "  ")
        assert "host" in errors
        assert "port" in errors
        assert "username" in errors
        assert "password" in errors


class TestValidatePaths:
    """Tests for validate_paths function."""

    def test_all_valid_paths(self):
        # Create temporary files and directory
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as ap_file:
            ap_path = ap_file.name
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as sw_file:
            sw_path = sw_file.name
        out_dir = tempfile.mkdtemp()

        try:
            errors = validate_paths(ap_path, sw_path, out_dir)
            assert errors == {}
        finally:
            os.unlink(ap_path)
            os.unlink(sw_path)
            os.rmdir(out_dir)

    def test_empty_ap_list_path(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as sw_file:
            sw_path = sw_file.name
        out_dir = tempfile.mkdtemp()

        try:
            errors = validate_paths("", sw_path, out_dir)
            assert "ap_list_path" in errors
            assert "required" in errors["ap_list_path"]
        finally:
            os.unlink(sw_path)
            os.rmdir(out_dir)

    def test_nonexistent_ap_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as sw_file:
            sw_path = sw_file.name
        out_dir = tempfile.mkdtemp()

        try:
            errors = validate_paths("/nonexistent/file.txt", sw_path, out_dir)
            assert "ap_list_path" in errors
            assert "does not exist" in errors["ap_list_path"]
        finally:
            os.unlink(sw_path)
            os.rmdir(out_dir)

    def test_nonexistent_switch_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as ap_file:
            ap_path = ap_file.name
        out_dir = tempfile.mkdtemp()

        try:
            errors = validate_paths(ap_path, "/nonexistent/file.txt", out_dir)
            assert "switch_list_path" in errors
            assert "does not exist" in errors["switch_list_path"]
        finally:
            os.unlink(ap_path)
            os.rmdir(out_dir)

    def test_nonexistent_output_dir(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as ap_file:
            ap_path = ap_file.name
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as sw_file:
            sw_path = sw_file.name

        try:
            errors = validate_paths(ap_path, sw_path, "/nonexistent/directory")
            assert "output_dir" in errors
            assert "does not exist" in errors["output_dir"]
        finally:
            os.unlink(ap_path)
            os.unlink(sw_path)

    def test_all_empty_paths(self):
        errors = validate_paths("", "", "")
        assert "ap_list_path" in errors
        assert "switch_list_path" in errors
        assert "output_dir" in errors
        assert len(errors) == 3

    def test_whitespace_only_paths(self):
        errors = validate_paths("   ", "   ", "   ")
        assert "ap_list_path" in errors
        assert "switch_list_path" in errors
        assert "output_dir" in errors

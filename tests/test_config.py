"""Unit tests for config.py — credential loading and validation.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
"""

import logging

import pytest

from config import Config, load_config


class TestLoadConfigValid:
    """Tests for valid .env loading with all fields."""

    def test_valid_config_all_fields(self, tmp_path):
        """Valid .env with all required and optional fields loads correctly."""
        f = tmp_path / ".env"
        f.write_text(
            "HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\n"
            "SSH_TIMEOUT=60\nAP_CONNECT_TIMEOUT=45\nCOMMAND_TIMEOUT=20\n"
        )
        result = load_config(str(f))
        assert result.host == "10.0.0.1"
        assert result.port == 22
        assert result.username == "admin"
        assert result.password == "secret"
        assert result.ssh_timeout == 60
        assert result.ap_connect_timeout == 45
        assert result.command_timeout == 20

    def test_valid_config_required_only(self, tmp_path):
        """Valid .env with only required fields uses default timeouts."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\n")
        result = load_config(str(f))
        assert result.host == "10.0.0.1"
        assert result.port == 22
        assert result.username == "admin"
        assert result.password == "secret"
        assert result.ssh_timeout == 30
        assert result.ap_connect_timeout == 30
        assert result.command_timeout == 15

    def test_port_boundary_min(self, tmp_path):
        """PORT=1 is valid (minimum boundary)."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=1\nUSERNAME=admin\nPASSWORD=secret\n")
        result = load_config(str(f))
        assert result.port == 1

    def test_port_boundary_max(self, tmp_path):
        """PORT=65535 is valid (maximum boundary)."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=65535\nUSERNAME=admin\nPASSWORD=secret\n")
        result = load_config(str(f))
        assert result.port == 65535

    def test_whitespace_trimmed(self, tmp_path):
        """Leading/trailing whitespace in values is trimmed."""
        f = tmp_path / ".env"
        f.write_text("HOST= 10.0.0.1 \nPORT= 22 \nUSERNAME= admin \nPASSWORD= secret \n")
        result = load_config(str(f))
        assert result.host == "10.0.0.1"
        assert result.port == 22
        assert result.username == "admin"


class TestLoadConfigMissingFile:
    """Tests for missing .env file triggering SystemExit."""

    def test_missing_file_exits(self):
        """Missing .env file triggers SystemExit."""
        with pytest.raises(SystemExit):
            load_config("/nonexistent/.env")

    def test_missing_file_exits_relative_path(self, tmp_path):
        """Non-existent relative path triggers SystemExit."""
        with pytest.raises(SystemExit):
            load_config(str(tmp_path / "does_not_exist.env"))


class TestLoadConfigMissingFields:
    """Tests for missing required fields triggering SystemExit."""

    def test_missing_host_exits(self, tmp_path):
        """Missing HOST key triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("PORT=22\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_missing_port_exits(self, tmp_path):
        """Missing PORT key triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_missing_username_exits(self, tmp_path):
        """Missing USERNAME key triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_empty_password_exits(self, tmp_path):
        """Empty PASSWORD value triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_whitespace_only_host_exits(self, tmp_path):
        """Whitespace-only HOST value triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=   \nPORT=22\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))


class TestLoadConfigInvalidPort:
    """Tests for invalid PORT value triggering SystemExit."""

    def test_port_not_number_exits(self, tmp_path):
        """Non-numeric PORT triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=abc\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_port_zero_exits(self, tmp_path):
        """PORT=0 (below valid range) triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=0\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_port_negative_exits(self, tmp_path):
        """Negative PORT triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=-1\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_port_too_high_exits(self, tmp_path):
        """PORT=99999 (above valid range) triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=99999\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_port_float_exits(self, tmp_path):
        """Floating-point PORT triggers SystemExit."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22.5\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))


class TestLoadConfigInvalidTimeouts:
    """Tests for invalid optional timeout values using defaults with warning."""

    def test_non_numeric_timeout_uses_default_with_warning(self, tmp_path, caplog):
        """Non-numeric SSH_TIMEOUT logs warning and uses default."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\nSSH_TIMEOUT=abc\n")
        with caplog.at_level(logging.WARNING):
            result = load_config(str(f))
        assert result.ssh_timeout == 30
        assert "SSH_TIMEOUT" in caplog.text

    def test_negative_timeout_uses_default_with_warning(self, tmp_path, caplog):
        """Negative AP_CONNECT_TIMEOUT logs warning and uses default."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\nAP_CONNECT_TIMEOUT=-5\n")
        with caplog.at_level(logging.WARNING):
            result = load_config(str(f))
        assert result.ap_connect_timeout == 30
        assert "AP_CONNECT_TIMEOUT" in caplog.text

    def test_zero_timeout_uses_default_with_warning(self, tmp_path, caplog):
        """Zero COMMAND_TIMEOUT logs warning and uses default."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\nCOMMAND_TIMEOUT=0\n")
        with caplog.at_level(logging.WARNING):
            result = load_config(str(f))
        assert result.command_timeout == 15
        assert "COMMAND_TIMEOUT" in caplog.text

    def test_all_invalid_timeouts_use_defaults(self, tmp_path):
        """All invalid timeout values fall back to their respective defaults."""
        f = tmp_path / ".env"
        f.write_text(
            "HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\n"
            "SSH_TIMEOUT=abc\nAP_CONNECT_TIMEOUT=-5\nCOMMAND_TIMEOUT=0\n"
        )
        result = load_config(str(f))
        assert result.ssh_timeout == 30
        assert result.ap_connect_timeout == 30
        assert result.command_timeout == 15


class TestLoadConfigDefaultTimeouts:
    """Tests for default timeout values when optional keys are absent."""

    def test_defaults_when_timeouts_absent(self, tmp_path):
        """When no timeout keys are present, defaults are used."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\n")
        result = load_config(str(f))
        assert result.ssh_timeout == 30
        assert result.ap_connect_timeout == 30
        assert result.command_timeout == 15

    def test_partial_timeouts_use_defaults_for_missing(self, tmp_path):
        """Only specified timeouts are used; missing ones get defaults."""
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\nSSH_TIMEOUT=60\n")
        result = load_config(str(f))
        assert result.ssh_timeout == 60
        assert result.ap_connect_timeout == 30
        assert result.command_timeout == 15

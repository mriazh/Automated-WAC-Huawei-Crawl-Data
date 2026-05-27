"""Unit tests for config.py — credential loading and validation."""

import pytest

from config import Config, load_config


class TestLoadConfig:
    def test_valid_config(self, tmp_path):
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

    def test_missing_file_exits(self):
        with pytest.raises(SystemExit):
            load_config("/nonexistent/.env")

    def test_missing_host_exits(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("PORT=22\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_missing_port_exits(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_empty_password_exits(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_invalid_port_not_number_exits(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=abc\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_port_zero_exits(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=0\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_port_too_high_exits(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=99999\nUSERNAME=admin\nPASSWORD=secret\n")
        with pytest.raises(SystemExit):
            load_config(str(f))

    def test_custom_timeouts(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\nSSH_TIMEOUT=60\nAP_CONNECT_TIMEOUT=45\nCOMMAND_TIMEOUT=20\n")
        result = load_config(str(f))
        assert result.ssh_timeout == 60
        assert result.ap_connect_timeout == 45
        assert result.command_timeout == 20

    def test_invalid_timeout_uses_default(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST=10.0.0.1\nPORT=22\nUSERNAME=admin\nPASSWORD=secret\nSSH_TIMEOUT=abc\nAP_CONNECT_TIMEOUT=-5\nCOMMAND_TIMEOUT=0\n")
        result = load_config(str(f))
        assert result.ssh_timeout == 30
        assert result.ap_connect_timeout == 30
        assert result.command_timeout == 15

    def test_whitespace_trimmed(self, tmp_path):
        f = tmp_path / ".env"
        f.write_text("HOST= 10.0.0.1 \nPORT= 22 \nUSERNAME= admin \nPASSWORD= secret \n")
        result = load_config(str(f))
        assert result.host == "10.0.0.1"
        assert result.username == "admin"

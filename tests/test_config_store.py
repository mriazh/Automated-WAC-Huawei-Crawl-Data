"""Unit tests for gui/config_store.py — ConfigStore and StoredConfig."""

import json
import os
from dataclasses import asdict
from unittest.mock import MagicMock

import pytest

from gui.config_store import ConfigStore, StoredConfig


@pytest.fixture
def mock_encryption_service():
    """Provide a mock EncryptionService."""
    return MagicMock()


@pytest.fixture
def config_store(tmp_path, monkeypatch, mock_encryption_service):
    """Create a ConfigStore pointing to a temp directory."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return ConfigStore(mock_encryption_service)


class TestStoredConfigDefaults:
    """Test StoredConfig dataclass default values."""

    def test_defaults(self):
        config = StoredConfig()
        assert config.host == ""
        assert config.port == ""
        assert config.username == ""
        assert config.encrypted_password == ""
        assert config.remember_me is False
        assert config.ap_list_path == ""
        assert config.switch_list_path == ""
        assert config.output_dir == ""
        assert config.theme == "dark"


class TestConfigStoreInit:
    """Test ConfigStore initialization."""

    def test_config_path_uses_appdata(self, tmp_path, monkeypatch, mock_encryption_service):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        store = ConfigStore(mock_encryption_service)
        expected = os.path.join(str(tmp_path), "WAC-Crawl", "config.json")
        assert store.config_path == expected

    def test_config_path_fallback_when_no_appdata(self, monkeypatch, mock_encryption_service):
        monkeypatch.delenv("APPDATA", raising=False)
        store = ConfigStore(mock_encryption_service)
        expected = os.path.join(".", "WAC-Crawl", "config.json")
        assert store.config_path == expected


class TestConfigStoreLoad:
    """Test ConfigStore.load() behavior."""

    def test_load_returns_defaults_when_file_missing(self, config_store):
        config = config_store.load()
        assert config == StoredConfig()

    def test_load_returns_defaults_on_corrupt_json(self, config_store):
        os.makedirs(os.path.dirname(config_store.config_path), exist_ok=True)
        with open(config_store.config_path, "w") as f:
            f.write("{invalid json content!!!")

        config = config_store.load()
        assert config == StoredConfig()

    def test_load_ignores_unknown_fields(self, config_store):
        os.makedirs(os.path.dirname(config_store.config_path), exist_ok=True)
        data = asdict(StoredConfig(host="10.0.0.1"))
        data["unknown_field"] = "should be ignored"
        with open(config_store.config_path, "w") as f:
            json.dump(data, f)

        config = config_store.load()
        assert config.host == "10.0.0.1"


class TestConfigStoreSave:
    """Test ConfigStore.save() behavior."""

    def test_save_creates_directory_and_file(self, config_store):
        config = StoredConfig(host="192.168.1.1", port="22")
        config_store.save(config)

        assert os.path.exists(config_store.config_path)

    def test_save_load_round_trip(self, config_store):
        original = StoredConfig(
            host="10.0.0.1",
            port="2222",
            username="admin",
            encrypted_password="encrypted_data_here",
            remember_me=True,
            ap_list_path="C:\\data\\ap_list.txt",
            switch_list_path="C:\\data\\switch_list.txt",
            output_dir="C:\\output",
            theme="light",
        )
        config_store.save(original)
        loaded = config_store.load()
        assert loaded == original


class TestConfigStoreClearCredentials:
    """Test ConfigStore.clear_credentials() behavior."""

    def test_clear_credentials_removes_only_credential_fields(self, config_store):
        original = StoredConfig(
            host="10.0.0.1",
            port="22",
            username="admin",
            encrypted_password="secret",
            remember_me=True,
            ap_list_path="/path/to/ap.txt",
            switch_list_path="/path/to/switch.txt",
            output_dir="/output",
            theme="light",
        )
        config_store.save(original)
        config_store.clear_credentials()

        loaded = config_store.load()
        # Credential fields should be cleared
        assert loaded.host == ""
        assert loaded.port == ""
        assert loaded.username == ""
        assert loaded.encrypted_password == ""
        assert loaded.remember_me is False
        # Preferences should be preserved
        assert loaded.ap_list_path == "/path/to/ap.txt"
        assert loaded.switch_list_path == "/path/to/switch.txt"
        assert loaded.output_dir == "/output"
        assert loaded.theme == "light"

    def test_clear_credentials_when_no_file_exists(self, config_store):
        # Should not raise — loads defaults, clears credentials (already empty), saves
        config_store.clear_credentials()
        loaded = config_store.load()
        assert loaded.host == ""
        assert loaded.remember_me is False

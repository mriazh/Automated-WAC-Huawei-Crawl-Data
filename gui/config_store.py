"""JSON configuration persistence at %APPDATA%/WAC-Crawl/config.json.

Manages loading, saving, and clearing of application configuration including
credentials, file paths, and theme preferences. The ConfigStore does not
handle encryption/decryption directly — callers are responsible for encrypting
passwords before saving and decrypting after loading.
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, fields

logger = logging.getLogger(__name__)


@dataclass
class StoredConfig:
    """Persisted application configuration."""

    host: str = ""
    port: str = ""
    username: str = ""
    encrypted_password: str = ""
    remember_me: bool = False
    ap_list_path: str = ""
    switch_list_path: str = ""
    output_dir: str = ""
    theme: str = "dark"


class ConfigStore:
    """Manages JSON config at %APPDATA%/WAC-Crawl/config.json."""

    def __init__(self, encryption_service) -> None:
        """Initialize with encryption service reference.

        Args:
            encryption_service: EncryptionService instance (kept for reference;
                actual encrypt/decrypt is handled by callers).
        """
        self._encryption_service = encryption_service
        appdata = os.environ.get("APPDATA", ".")
        self._config_dir = os.path.join(appdata, "WAC-Crawl")
        self._config_path = os.path.join(self._config_dir, "config.json")

    @property
    def config_path(self) -> str:
        """Return the full path to the config file."""
        return self._config_path

    def load(self) -> StoredConfig:
        """Load config from disk.

        Returns defaults if file is missing or corrupt. Logs a warning
        on corruption (invalid JSON).
        """
        if not os.path.exists(self._config_path):
            return StoredConfig()

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Config file corrupt or unreadable at %s: %s. Using defaults.",
                self._config_path,
                e,
            )
            return StoredConfig()

        # Build StoredConfig from loaded data, using defaults for missing fields
        valid_fields = {field.name for field in fields(StoredConfig)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return StoredConfig(**filtered_data)

    def save(self, config: StoredConfig) -> None:
        """Write config to disk as JSON. Creates directory if needed."""
        os.makedirs(self._config_dir, exist_ok=True)

        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2)

    def clear_credentials(self) -> None:
        """Remove stored credentials, keep other preferences.

        Loads the current config, clears credential fields (host, port,
        username, encrypted_password, remember_me), and saves back.
        """
        config = self.load()
        config.host = ""
        config.port = ""
        config.username = ""
        config.encrypted_password = ""
        config.remember_me = False
        self.save(config)

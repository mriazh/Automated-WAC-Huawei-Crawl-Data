"""Configuration loader for WAC Huawei LLDP Crawl Data tool.

Loads and validates SSH credentials and timeout settings from a .env file.
"""

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """SSH and timeout configuration for the WAC crawl tool."""

    host: str
    port: int
    username: str
    password: str
    ssh_timeout: int = 30
    ap_connect_timeout: int = 30
    command_timeout: int = 15


def load_config(env_path: str = ".env") -> Config:
    """Load and validate configuration from .env file.

    Required keys: HOST, PORT, USERNAME, PASSWORD
    Optional keys: SSH_TIMEOUT, AP_CONNECT_TIMEOUT, COMMAND_TIMEOUT

    Raises SystemExit on missing file or invalid required fields.
    Logs warning for invalid optional timeout values and uses defaults.
    """
    env_file = Path(env_path)

    if not env_file.exists():
        print(f"Error: .env file not found at '{env_path}'")
        sys.exit(1)

    values = dotenv_values(env_path)

    # Validate required fields
    required_keys = ["HOST", "PORT", "USERNAME", "PASSWORD"]
    missing = []
    for key in required_keys:
        val = values.get(key, "")
        if val is None or val.strip() == "":
            missing.append(key)

    if missing:
        print(f"Error: Missing or empty required fields: {', '.join(missing)}")
        sys.exit(1)

    # Validate PORT is numeric integer in range 1-65535
    port_str = values["PORT"].strip()
    try:
        port = int(port_str)
    except ValueError:
        print(f"Error: PORT value '{port_str}' is not a valid integer")
        sys.exit(1)

    if port < 1 or port > 65535:
        print(f"Error: PORT value '{port}' is not in valid range (1-65535)")
        sys.exit(1)

    # Parse optional timeout values with defaults
    ssh_timeout = _parse_timeout(values, "SSH_TIMEOUT", 30)
    ap_connect_timeout = _parse_timeout(values, "AP_CONNECT_TIMEOUT", 30)
    command_timeout = _parse_timeout(values, "COMMAND_TIMEOUT", 15)

    return Config(
        host=values["HOST"].strip(),
        port=port,
        username=values["USERNAME"].strip(),
        password=values["PASSWORD"].strip(),
        ssh_timeout=ssh_timeout,
        ap_connect_timeout=ap_connect_timeout,
        command_timeout=command_timeout,
    )


def _parse_timeout(values: dict, key: str, default: int) -> int:
    """Parse an optional timeout value from the env values dict.

    Returns the parsed integer if valid, or the default value if the key
    is absent or the value is not a positive integer.
    Logs a warning for invalid values.
    """
    raw = values.get(key)
    if raw is None or raw.strip() == "":
        return default

    raw = raw.strip()
    try:
        val = int(raw)
    except ValueError:
        logger.warning(
            "Invalid value '%s' for %s (not a valid integer). Using default: %d",
            raw,
            key,
            default,
        )
        return default

    if val <= 0:
        logger.warning(
            "Invalid value '%s' for %s (must be a positive integer). Using default: %d",
            raw,
            key,
            default,
        )
        return default

    return val

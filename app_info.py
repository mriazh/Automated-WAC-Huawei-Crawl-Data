"""Application metadata and constants."""

import os
import tempfile
from pathlib import Path

def get_log_dir() -> Path:
    """Get the application log directory."""
    base_dir = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    log_dir = Path(base_dir) / "WAC-Crawl"
    return log_dir


APP_NAME = "WAC Huawei LLDP Crawl Data"
APP_VERSION = "1.0.1"
APP_BUILD_DATE = "2026"
GITHUB_REPO = "mriazh/Automated-WAC-Huawei-Crawl-Data"
RELEASES_URL = "https://github.com/mriazh/Automated-WAC-Huawei-Crawl-Data/releases"
LATEST_RELEASE_API = "https://api.github.com/repos/mriazh/Automated-WAC-Huawei-Crawl-Data/releases/latest"
INSTALLER_ASSET_PREFIX = "WAC-Crawl-Setup"
INSTALLER_ASSET_SUFFIX = ".exe"

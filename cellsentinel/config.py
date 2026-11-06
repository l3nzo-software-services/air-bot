"""
Configuration management for CellSentinel.
Loads settings from environment variables with sensible production defaults.
"""

import os
from pathlib import Path
from typing import Optional


class Settings:
    """Application settings and telecom parameters."""

    APP_NAME: str = "CellSentinel"
    APP_VERSION: str = "2.0.0"

    # Base directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/cellsentinel_platform.db")

    # OpenCellID API Integration
    OPENCELLID_API_KEY: Optional[str] = os.getenv("OPENCELLID_API_KEY", None)
    OPENCELLID_BASE_URL: str = os.getenv("OPENCELLID_BASE_URL", "https://opencellid.org/cell/get")
    API_TIMEOUT_SECONDS: float = float(os.getenv("API_TIMEOUT_SECONDS", "4.0"))
    API_MAX_RETRIES: int = int(os.getenv("API_MAX_RETRIES", "2"))

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "cellsentinel-telecom-secret-salt-2026")
    API_TOKEN_SALT: str = "CellSentinel-Token-Salt-v2"

    # Server Settings
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # Verified Reference Data File
    VERIFIED_TOWERS_FILE: Path = DATA_DIR / "verified_towers.json"


settings = Settings()

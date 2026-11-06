"""
Configuration settings for CellSentinel.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """System configuration parameters."""

    # Server settings
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "true").lower() in ("true", "1", "yes"))
    APP_NAME: str = "CellSentinel"
    APP_VERSION: str = "1.0.0"

    # Database
    DATABASE_PATH: str = Field(default_factory=lambda: os.getenv("DATABASE_PATH", "cellsentinel.db"))

    # External Geolocation Providers (optional)
    OPENCELLID_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("OPENCELLID_API_KEY") or None)
    OPENCELLID_BASE_URL: str = "https://opencellid.org/cell/get"
    MLS_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("MLS_API_KEY") or None)
    MLS_BASE_URL: str = "https://location.services.mozilla.com/v1/geolocate"
    UNWIRED_API_KEY: Optional[str] = Field(default_factory=lambda: os.getenv("UNWIRED_API_KEY") or None)
    UNWIRED_BASE_URL: str = "https://us1.unwiredlabs.com/v2/process.php"

    # RF Propagation parameters
    REFERENCE_POWER_DBM: float = Field(default_factory=lambda: float(os.getenv("REFERENCE_POWER_DBM", "-42.0")))
    PATH_LOSS_EXPONENT: float = Field(default_factory=lambda: float(os.getenv("PATH_LOSS_EXPONENT", "3.2")))
    MIN_ACCURACY_RADIUS_METERS: float = Field(default_factory=lambda: float(os.getenv("MIN_ACCURACY_RADIUS_METERS", "120.0")))
    MAX_ACCURACY_RADIUS_METERS: float = Field(default_factory=lambda: float(os.getenv("MAX_ACCURACY_RADIUS_METERS", "4500.0")))
    DEFAULT_ACCURACY_RADIUS_METERS: float = Field(default_factory=lambda: float(os.getenv("DEFAULT_ACCURACY_RADIUS_METERS", "850.0")))

    # Base directory
    BASE_DIR: Path = Path(__file__).resolve().parent.parent


# Singleton settings instance
settings = Settings()

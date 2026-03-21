from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the backend package (backend/)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Pi-hole connection (optional — enables always-on sync without login)
    pihole_api_url: str = ""
    pihole_api_password: str = ""

    # Session
    session_timeout_hours: int = 24  # Idle timeout — session expires after this many hours of inactivity

    # Logging
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"


settings = Settings()

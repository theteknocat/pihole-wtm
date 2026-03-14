import json
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Pi-hole connection
    pihole_api_url: str = "http://pihole"
    pihole_api_password: SecretStr = SecretStr("")
    # Note: "v5" is accepted by the validator but not yet implemented; only "v6" is supported
    pihole_api_version: Literal["v5", "v6", "auto"] = "auto"

    # TrackerDB
    trackerdb_path: str = "/app/data/trackerdb.db"
    trackerdb_update_interval_hours: int = 24
    trackerdb_release: str = "latest"  # "latest" or a specific tag e.g. "202603111257"

    # Application server
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: Literal["debug", "info", "warning", "error", "critical"] = "info"
    # Allowed CORS origins — comma-separated or JSON array:
    # CORS_ORIGINS=https://pihole-wtm.ddev.site:5174,http://localhost:5173
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:5174"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [url.strip() for url in v.split(",") if url.strip()]
        return v


settings = Settings()

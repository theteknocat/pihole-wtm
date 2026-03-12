from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Pi-hole connection
    pihole_mode: Literal["sqlite", "api"] = "api"
    pihole_sqlite_path: str = "/etc/pihole/pihole-FTL.db"
    pihole_api_url: str = "http://pihole"
    pihole_api_password: str = ""
    pihole_api_version: Literal["v5", "v6", "auto"] = "auto"

    # TrackerDB
    trackerdb_path: str = "/app/data/trackerdb.db"
    trackerdb_update_interval_hours: int = 24

    # Application server
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"


settings = Settings()

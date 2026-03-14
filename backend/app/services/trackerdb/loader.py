import logging
import os
import time
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/ghostery/trackerdb/releases"

# Tables and columns our queries depend on — used to validate a downloaded DB
REQUIRED_SCHEMA: dict[str, set[str]] = {
    "tracker_domains": {"domain", "tracker"},
    "trackers": {"id", "name", "category_id", "company_id", "alias"},
    "categories": {"id", "name"},
    "companies": {"id", "name", "country"},
}


class TrackerDbLoadError(Exception):
    pass


def _db_path() -> Path:
    return Path(settings.trackerdb_path)


def _is_stale() -> bool:
    path = _db_path()
    if not path.exists():
        return True
    if settings.trackerdb_update_interval_hours == 0:
        return False
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    return age_hours >= settings.trackerdb_update_interval_hours


async def _get_download_url() -> tuple[str, str]:
    """Return (download_url, tag_name) for the configured release."""
    release = settings.trackerdb_release
    if release == "latest":
        url = f"{GITHUB_API}/latest"
    else:
        url = f"{GITHUB_API}/tags/{release}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers={"Accept": "application/vnd.github+json"})
        response.raise_for_status()

    data = response.json()
    tag = data["tag_name"]
    for asset in data.get("assets", []):
        if asset["name"] == "trackerdb.db":
            return asset["browser_download_url"], tag

    raise TrackerDbLoadError(f"No trackerdb.db asset found in release {tag}")


def _validate_schema(db_path: Path) -> list[str]:
    """
    Check that the DB contains the tables and columns we depend on.
    Returns a list of validation errors (empty = valid).
    """
    import sqlite3

    errors: list[str] = []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table, required_cols in REQUIRED_SCHEMA.items():
            if table not in existing_tables:
                errors.append(f"Missing table: {table}")
                continue
            cursor.execute(f"PRAGMA table_info({table})")  # noqa: S608
            existing_cols = {row[1] for row in cursor.fetchall()}
            missing = required_cols - existing_cols
            if missing:
                errors.append(f"Table '{table}' missing columns: {missing}")

        conn.close()
    except sqlite3.Error as e:
        errors.append(f"SQLite error during schema validation: {e}")

    return errors


async def _download(url: str, dest: Path) -> None:
    """Download a file to dest, writing atomically via a .tmp file."""
    tmp = dest.with_suffix(".db.tmp")
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with tmp.open("wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

    errors = _validate_schema(tmp)
    if errors:
        tmp.unlink(missing_ok=True)
        raise TrackerDbLoadError(
            f"Downloaded TrackerDB failed schema validation: {'; '.join(errors)}"
        )

    tmp.rename(dest)


async def ensure_trackerdb() -> None:
    """
    Ensure a valid trackerdb.db exists at the configured path.
    Downloads from GitHub Releases if missing or stale.
    Keeps the existing file if the download or validation fails.
    """
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if not _is_stale():
        logger.debug("TrackerDB is up to date at %s", path)
        return

    logger.info("TrackerDB is missing or stale — downloading from GitHub Releases")
    try:
        download_url, tag = await _get_download_url()
        logger.info("Downloading TrackerDB release %s", tag)
        await _download(download_url, path)
        logger.info("TrackerDB updated to release %s (%s)", tag, path)
    except Exception as e:
        if path.exists():
            logger.warning("TrackerDB download failed, keeping existing file: %s", e)
        else:
            raise TrackerDbLoadError(f"TrackerDB unavailable and no local copy: {e}") from e


def trackerdb_exists() -> bool:
    return _db_path().exists()

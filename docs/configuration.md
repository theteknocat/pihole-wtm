# Configuration Reference

All configuration is provided via environment variables. In Docker Compose deployments these are set in `docker-compose.yml` or a `.env` file. In ddev they are set in `.ddev/docker-compose.backend.yaml`. In bare-metal deployments they can be exported in a shell or loaded via a `.env` file with `python-dotenv`.

Copy `.env.example` to `.env` to get started:

```bash
cp .env.example .env
```

---

## Pi-hole Connection

### `PIHOLE_API_URL`

Base URL of the Pi-hole web interface.

**Default:** `http://pihole`

**Examples:**

```text
PIHOLE_API_URL=http://192.168.1.1
PIHOLE_API_URL=http://pihole          # Docker container name on shared network
PIHOLE_API_URL=https://pihole.local
```

Do not include a trailing slash or path. The backend appends `/api/...` paths automatically.

---

### `PIHOLE_API_PASSWORD`

Pi-hole web interface password. Used to obtain a session token for the Pi-hole v6 API, or the HMAC auth hash for the Pi-hole v5 API.

**Default:** empty (works if Pi-hole has no password set)

---

### `PIHOLE_API_VERSION`

Force a specific Pi-hole API version. If not set, the backend auto-detects the version by probing the Pi-hole URL.

| Value | Description                                             |
| ----- | ------------------------------------------------------- |
| `v5`  | Pi-hole 5.x — uses legacy `api.php` endpoints           |
| `v6`  | Pi-hole 6.x — uses REST API with session authentication |

**Default:** auto-detect

---

## TrackerDB

### `TRACKERDB_PATH`

Path where the Ghostery TrackerDB SQLite file is stored. The file is downloaded automatically from GitHub Releases on startup if absent or stale. The directory must be writable by the backend process.

**Default:** `/app/data/trackerdb.db` (inside the Docker container)

In Docker deployments, mount a named volume to persist the downloaded database across restarts:

```yaml
volumes:
  - trackerdb_data:/app/data
```

---

### `TRACKERDB_UPDATE_INTERVAL_HOURS`

How often to check for a new TrackerDB release from Ghostery. On each check, the backend queries the GitHub Releases API and downloads a new file if a newer version is available.

**Default:** `24`

Set to `0` to disable automatic updates (use the bundled or manually placed file only).

---

## Application Server

### `APP_HOST`

Host address for the uvicorn server to bind to.

**Default:** `0.0.0.0`

---

### `APP_PORT`

Port for the uvicorn server.

**Default:** `8000`

---

### `LOG_LEVEL`

Logging verbosity. Passed to both uvicorn and the Python `logging` module.

| Value     | Description                                                |
| --------- | ---------------------------------------------------------- |
| `debug`   | Verbose: all SQL queries, HTTP requests, cache hits/misses |
| `info`    | Normal operation messages                                  |
| `warning` | Warnings only                                              |
| `error`   | Errors only                                                |

**Default:** `info`

---

## Docker Deployment

### `DASHBOARD_PORT`

Host port that the nginx frontend container binds to, making the dashboard accessible.

**Default:** `8080`

**Example:** Access dashboard at `http://your-host:8080`

---

### `PIHOLE_NETWORK`

Name of the Docker network that Pi-hole is connected to. The backend container joins this network to reach Pi-hole's API by container name.

**Default:** `pihole_default`

Find the correct network name with:

```bash
docker network ls
docker inspect <pihole-container-name> | grep NetworkMode
```

---

## Example `.env` Files

### Docker Compose

```bash
PIHOLE_API_URL=http://pihole
PIHOLE_API_PASSWORD=supersecretpassword
PIHOLE_API_VERSION=v6
PIHOLE_NETWORK=pihole_default
DASHBOARD_PORT=8080
TRACKERDB_UPDATE_INTERVAL_HOURS=24
```

### Bare-metal

```bash
PIHOLE_API_URL=http://192.168.1.1
PIHOLE_API_PASSWORD=supersecretpassword
TRACKERDB_PATH=/var/lib/pihole-wtm/trackerdb.db
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=info
TRACKERDB_UPDATE_INTERVAL_HOURS=24
```

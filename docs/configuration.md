# Configuration Reference

pihole-wtm is designed to work out of the box with minimal configuration. You can install it and start using it immediately by logging in via the web UI — no environment variables are required.

For production use, setting `PIHOLE_API_URL` and `PIHOLE_API_PASSWORD` as environment variables is recommended to enable always-on background sync.

---

## Pi-hole Connection

### `PIHOLE_API_URL`

Base URL of the Pi-hole web interface. **Optional** — if not set, the user enters the URL on the login page each session.

**Default:** empty (not set)

**Examples:**

```text
PIHOLE_API_URL=http://192.168.1.1
PIHOLE_API_URL=http://pihole.home.arpa
PIHOLE_API_URL=http://pihole          # Docker container name on shared network
```

Do not include a trailing slash or path — the backend appends `/api/...` automatically.

> **Note:** Pi-hole v6 is required. Pi-hole v5 is not supported.

---

### `PIHOLE_API_PASSWORD`

Pi-hole web interface password. When set alongside `PIHOLE_API_URL`, enables **always-on background sync** — the sync service starts on boot and runs continuously, independent of whether a user is logged into the dashboard.

**Default:** empty (not set)

If omitted, sync only runs while a user is logged in (the password is entered on the login page and held in server memory for the session duration). This is a valid fallback but means no data is collected when nobody is using the dashboard. The footer displays an amber indicator when running in this mode.

For production/Docker deployments, setting this env var is recommended so that query data is collected continuously.

---

## Session

### `SESSION_TIMEOUT_HOURS`

How many hours an idle session lasts before the user must log in again. The timeout resets on each authenticated API request.

**Default:** `24`

When session-driven sync is active (no `PIHOLE_API_PASSWORD` env var), session expiry also stops the sync service. Setting a higher value is fine for a local dashboard — sessions are memory-only and cleared on server restart regardless.

---

## Logging

### `LOG_LEVEL`

Logging verbosity for both uvicorn and the Python logging module.

| Value      | Description                           |
| ---------- | ------------------------------------- |
| `debug`    | Verbose — HTTP requests, cache events |
| `info`     | Normal operation (recommended)        |
| `warning`  | Warnings and errors only              |
| `error`    | Errors only                           |
| `critical` | Critical failures only                |

**Default:** `info`

---

## Hardcoded Defaults

The following settings use sensible defaults and do not require configuration. They will be made configurable via the dashboard UI in a future update.

| Setting | Default | Description |
| --- | --- | --- |
| Sync interval | 60 seconds | How often the sync service polls Pi-hole for new queries |
| Data retention | 7 days | How long query data is kept before automatic purging |
| TrackerDB update interval | 24 hours | How often to check for a newer TrackerDB release |
| Disconnect.me update interval | 24 hours | How often to refresh the Disconnect.me tracking list |
| Database paths | `backend/data/` | `pihole_wtm.db` and `trackerdb.db` are stored relative to the backend directory |

---

## Example `.env` Files

### Docker Compose (recommended)

```bash
PIHOLE_API_URL=http://pihole
PIHOLE_API_PASSWORD=your-pihole-password
```

### Bare-metal

```bash
PIHOLE_API_URL=http://192.168.1.1
PIHOLE_API_PASSWORD=your-pihole-password
LOG_LEVEL=info
```

> **Note:** `PIHOLE_API_PASSWORD` is recommended for continuous sync but can be omitted — in that case, sync only runs while a user is logged in. See [authentication.md](authentication.md) for details.

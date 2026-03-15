# Authentication

> **Status: Planned enhancement** — Not yet implemented. Authentication will be added as part of the pre-release hardening phase. See [roadmap.md](roadmap.md) for phasing.
>
> **Architecture note:** The design below was written when every API request called Pi-hole directly. With the sync service architecture, the Pi-hole connection is owned by the background sync process rather than individual requests. The session management and Pi-hole credential handling sections will need to be revisited during implementation to reflect this.

## Overview

Rather than storing the Pi-hole password in a configuration file, pihole-wtm uses the Pi-hole password itself as the login credential for the dashboard. This means:

- No separate pihole-wtm password to manage
- If the Pi-hole password changes, the user simply logs in with the new one
- The password is **never written to disk** — it lives only in server-side session memory
- On server restart, sessions are cleared and users re-login (acceptable behaviour for a local dashboard)

## Login Flow

1. User visits pihole-wtm — no valid session → redirected to login page
2. Login page shows the Pi-hole URL (read-only if set via env var, editable otherwise) and a password field
3. On submit, the backend authenticates against the Pi-hole API using the provided credentials
4. If Pi-hole accepts → pihole-wtm creates a server-side session containing:
   - Pi-hole URL
   - Pi-hole password (in memory only, never persisted to disk)
   - Current Pi-hole session token (sid)
5. User is redirected to the dashboard
6. When the Pi-hole session expires (30 min idle), the backend re-authenticates silently using the password stored in the session — no user action required
7. Logout deletes the pihole-wtm session and also calls the Pi-hole logout endpoint to invalidate the sid

## Pi-hole URL Configuration

The Pi-hole URL is configured via a two-tier system:

### Tier 1 — Environment variable (immutable, admin-set)

Set `PIHOLE_API_URL` in your `.env` file or Docker Compose environment. When set this way, the URL is treated as authoritative and **the app never modifies it**.

On the login page, the URL field is displayed as **read-only** with a note indicating it is set via environment variable. Only the password field is active.

This is the recommended approach for Docker deployments and any setup managed by an administrator.

### Tier 2 — Runtime config file (app-managed)

If `PIHOLE_API_URL` is not set via environment, the URL is read from and written to `data/app-config.json` — a small JSON file in the same data directory as `trackerdb.db`.

On the login page, the URL field is **editable**. On first successful login, the entered URL is saved to `data/app-config.json` and used for all subsequent sessions. If the URL is changed on the login page and authentication succeeds, the config file is updated.

In Docker deployments, `data/` is mounted as a named volume, so `app-config.json` persists across container restarts.

**Priority order:** env var → `data/app-config.json` → empty (user must enter on login page)

### CLI setup command

For power users who prefer to configure the URL before first use without editing a `.env` file:

```bash
# Docker
docker run --rm -v pihole_wtm_data:/app/data pihole-wtm setup

# Bare-metal
pihole-wtm setup
```

This prompts for the Pi-hole URL and writes `data/app-config.json`. Equivalent to what the login page does, but from the terminal.

## Session Management

- Sessions are stored **server-side in memory** (a UUID-keyed dict)
- The session token is sent to the browser as an **HTTP-only signed cookie**
- Sessions are cleared on server restart — users re-login
- No session data (including the Pi-hole password) is ever written to disk
- A `SECRET_KEY` environment variable is required to sign session cookies (auto-generated on first run if not set, but setting it explicitly ensures sessions survive hot-reloads)

## Security Notes

- This application is designed for **local network use only** and is not intended to be exposed to the public internet
- The Pi-hole password is held in server memory only for the duration of the session
- The `.env` file is never modified by the application at runtime
- `data/app-config.json` contains only the Pi-hole URL (not sensitive), and is only written when no env var is set

## Implementation Plan

### Backend

- `app/services/auth/session_store.py` — in-memory session store (UUID → session data dict)
- `app/services/auth/config_store.py` — read/write `data/app-config.json` for the Pi-hole URL
- `app/routers/auth.py` — `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/status`
- Session middleware using `itsdangerous` for signed cookies
- Dependency injection: `require_session` used on all protected routers
- `PiholeApiClient` refactored to be instantiated per-session rather than globally

### Frontend

- `LoginView.vue` — URL field (read-only or editable based on config tier) + password field
- Route guard in `router/index.ts` — redirect to `/login` if no active session
- `stores/auth.ts` — session state, login/logout actions
- `AppHeader.vue` — logout button

### CLI

- `backend/pihole_wtm/cli.py` — `setup` command using `click`, writes `data/app-config.json`
- Entry point registered in `pyproject.toml`

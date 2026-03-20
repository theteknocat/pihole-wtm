# Authentication

> **Status: Planned** — Not yet implemented. Authentication will be added as part of the pre-release hardening phase. See [roadmap.md](roadmap.md) for phasing.

## Overview

pihole-wtm uses the Pi-hole password as its login credential. The user authenticates by entering their Pi-hole password, which is verified against the Pi-hole API. On success, the password is held **in server memory only** and used for all subsequent Pi-hole API calls (sync, queries, etc.).

This means:

- No separate pihole-wtm password to manage
- The Pi-hole password is **never stored on disk** — not in `.env`, not in config files, not in the database
- If the Pi-hole password changes, the user simply logs in again with the new one
- On server restart, sessions are cleared and users re-login (acceptable for a local dashboard)
- The background sync service only runs while an authenticated session exists

## Login Flow

1. User visits pihole-wtm → no valid session → login page shown
2. Login page displays:
   - **Pi-hole URL**: read-only if set via `PIHOLE_API_URL` env var; editable (IP/hostname input) if not set
   - **Password field**: always editable
3. On submit, the backend authenticates against the Pi-hole API using the provided credentials
4. If Pi-hole accepts → pihole-wtm creates a server-side session containing:
   - Pi-hole URL (resolved from env var or user input)
   - Pi-hole password (in memory only)
   - Current Pi-hole session token (sid)
5. The background sync service starts using the session credentials
6. User is redirected to the dashboard
7. When the Pi-hole session expires (30 min idle), the backend re-authenticates silently using the password held in the session — no user action required
8. Logout:
   - Deletes the pihole-wtm session
   - Calls the Pi-hole logout endpoint to invalidate the sid
   - Stops the background sync service

## Pi-hole URL Configuration

The Pi-hole URL uses a two-tier system:

### Tier 1 — Environment variable (immutable, admin-set)

Set `PIHOLE_API_URL` in your `.env` file, Docker environment, or container manager config. When set this way:

- The URL is treated as authoritative and the app never modifies it
- The login page displays the URL as **read-only** text
- Only the password field is active

This is the recommended approach for Docker deployments and any setup managed by an administrator.

### Tier 2 — Runtime config file (app-managed)

If `PIHOLE_API_URL` is not set via environment, the URL is read from and written to `data/app-config.json` — a small JSON file in the persistent data directory.

- **First visit (no saved URL):** the login page shows an editable URL field. The user enters their Pi-hole IP/hostname. On successful login, the URL is saved to `data/app-config.json`.
- **Subsequent visits (URL saved):** the login page shows the saved URL as **read-only**, same as tier 1. Only the password field is active. The user does not need to re-enter the URL.
- **Changing the Pi-hole URL** is intentionally not available from the login page once saved — the system is designed for a single Pi-hole instance. To switch to a different Pi-hole, the user must either:
  - Delete or edit `data/app-config.json` manually
  - Use the `pihole-wtm setup` CLI command to reconfigure
  - Set `PIHOLE_API_URL` as an env var (overrides the config file)

In Docker deployments, `data/` is mounted as a named volume, so `app-config.json` persists across container restarts.

**Priority order:** env var → `data/app-config.json` → empty (first-time setup via login page)

### URL reachability check

When the login page loads, the backend checks whether the configured Pi-hole URL is reachable:

- **Reachable:** a green status indicator is shown next to the URL, and the password field is enabled
- **Unreachable:** a red status indicator with an error message is shown. The password field is disabled since login cannot succeed. If the URL was entered manually (first visit), the user can correct it.
- The check calls the Pi-hole API's unauthenticated health/version endpoint (no password required)
- On first visit with an editable URL, the check runs on blur/submit rather than on every keystroke

## Session Management

- Sessions are stored **server-side in memory** (a UUID-keyed dict)
- The session token is sent to the browser as an **HTTP-only signed cookie**
- Sessions are cleared on server restart — users re-login
- No session data (including the Pi-hole password) is ever written to disk
- A `SECRET_KEY` environment variable is required to sign session cookies (auto-generated on first run if not set, but setting it explicitly ensures sessions survive hot-reloads)

## UI Changes

### Login page

The login page replaces the current `OverviewView` as the landing page when no session exists. It contains only:

- App title/branding
- Pi-hole URL field (read-only or editable per tier)
- Password field
- Login button
- Error message area (invalid password, unreachable Pi-hole, etc.)

### Health/status footer

The system health information currently shown on the Overview page moves to a **fixed footer** visible on all authenticated pages. This provides at-a-glance status without needing a dedicated page:

- Backend connection status
- Pi-hole connection status and version
- Tracker source status (loaded/unavailable)
- Compact, visual design — icons and badges rather than text-heavy layout

### Navigation changes

- Unauthenticated: only the login page is accessible
- Authenticated: all current views (Dashboard, Timeline, Detailed Report) plus a logout action in the header

## Security Notes

- This application is designed for **local network use only** and is not intended to be exposed to the public internet
- The Pi-hole password is held in server memory only for the duration of the session
- The `.env` file contains only the Pi-hole URL and operational settings — never the password
- `data/app-config.json` contains only the Pi-hole URL (not sensitive)

## Implementation Plan

### Backend

- `app/services/auth/session_store.py` — in-memory session store (UUID → session data dict)
- `app/services/auth/config_store.py` — read/write `data/app-config.json` for the Pi-hole URL (tier 2)
- `app/routers/auth.py` — `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/status`
- Session middleware using `itsdangerous` for signed cookies
- Dependency injection: `require_session` guard on all protected API routes
- `PiholeApiClient` refactored to be instantiated from session credentials (not global config)
- Sync service lifecycle tied to session: starts on login, stops on logout/session expiry
- Remove `PIHOLE_API_PASSWORD` from env var config — password only comes from login

### Frontend

- `LoginView.vue` — URL field (read-only or editable) + password field
- Route guard in `router/index.ts` — redirect to `/login` if `GET /api/auth/status` returns unauthenticated
- `stores/auth.ts` — session state, login/logout actions
- `AppHeader.vue` — logout button added
- `AppFooter.vue` — fixed footer with health/status display (replaces OverviewView)
- `OverviewView.vue` — removed or repurposed

### Configuration changes

- Remove `PIHOLE_API_PASSWORD` from `.env.example` and `Settings` model
- Add `SECRET_KEY` to `.env.example`
- `PIHOLE_API_URL` remains optional (tier 1/tier 2 system)

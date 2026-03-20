# Authentication

## Overview

pihole-wtm uses the Pi-hole password as its login credential. The user authenticates by entering their Pi-hole password, which is verified against the Pi-hole API. On success, the password is held **in server memory only** and used for all subsequent Pi-hole API calls (sync, queries, etc.).

This means:

- No separate pihole-wtm password to manage
- The Pi-hole password is **never stored on disk** — not in `.env`, not in config files, not in the database
- If the Pi-hole password changes, the user simply logs in again with the new one
- On server restart, sessions are cleared and users re-login (acceptable for a local dashboard)
- The background sync service only runs while an authenticated session exists

## Login Flow

1. User visits pihole-wtm → no valid session → redirected to `/login`
2. Login page displays:
   - **Pi-hole URL**: read-only if set via `PIHOLE_API_URL` env var or previously saved; editable input if not configured
   - **Reachability indicator**: green/red status next to the URL label, checked via the Pi-hole's unauthenticated version endpoint
   - **Password field**: enabled only after the Pi-hole URL is confirmed reachable
3. On submit, the backend authenticates against the Pi-hole API using the provided credentials
4. If Pi-hole accepts → pihole-wtm creates a server-side session containing:
   - Pi-hole URL (resolved from env var, database, or user input)
   - Pi-hole password (in memory only)
5. The background sync service starts using the session credentials
6. User is redirected to the dashboard
7. When the Pi-hole session token expires, the `PiholeApiClient` re-authenticates silently using the password held in the session — no user action required
8. Logout:
   - Deletes the pihole-wtm session
   - Stops the background sync service
   - Clears the session cookie

## Pi-hole URL Configuration

The Pi-hole URL uses a two-tier system:

### Tier 1 — Environment variable (immutable, admin-set)

Set `PIHOLE_API_URL` in your `.env` file, Docker environment, or container manager config. When set this way:

- The URL is treated as authoritative and the app never modifies it
- The login page displays the URL as **read-only** text
- Only the password field is active

This is the recommended approach for Docker deployments and any setup managed by an administrator.

### Tier 2 — Database config (app-managed)

If `PIHOLE_API_URL` is not set via environment, the URL is read from and written to the `user_config` table in the local SQLite database.

- **First visit (no saved URL):** the login page shows an editable URL field with a reachability check button. The user enters their Pi-hole IP/hostname. On successful login, the URL is saved to the database.
- **Subsequent visits (URL saved):** the login page shows the saved URL as **read-only**, same as tier 1. Only the password field is active. The user does not need to re-enter the URL.

In Docker deployments, the database is in a named volume, so the saved URL persists across container restarts.

**Priority order:** env var → database `user_config` → empty (first-time setup via login page)

### URL reachability check

Before the password field is enabled, the backend checks whether the configured Pi-hole URL is reachable:

- **Reachable:** a green indicator with version info is shown next to the URL label
- **Unreachable:** a red indicator is shown. The password field and submit button remain disabled since login cannot succeed
- The check calls `GET /api/auth/check-url`, which hits Pi-hole's unauthenticated `/api/info/version` endpoint
- When the URL is editable (first visit), the check runs on blur and via a manual check button (InputGroup with attached button)

## Session Management

- Sessions are stored **server-side in memory** (a single-session store keyed by UUID)
- The session token is sent to the browser as an **HTTP-only cookie** (`pihole_wtm_session`, `samesite=strict`)
- Only one session exists at a time (single-user dashboard)
- Sessions expire after 24 hours of inactivity
- Sessions are cleared on server restart — users re-login
- No session data (including the Pi-hole password) is ever written to disk

## Route Protection

### Backend

All API routes except `/api/auth/*` are protected by the `require_session` FastAPI dependency. This reads the session cookie and returns 401 if the session is missing or expired.

### Frontend

- **Vue Router guard** (`beforeEach` in `router.ts`): checks session status on first navigation via `GET /api/auth/status`. Redirects unauthenticated users to `/login` and authenticated users away from `/login`.
- **`apiFetch` wrapper** (`utils/api.ts`): wraps `fetch()` for all authenticated API calls. On a 401 response (session expired mid-use), clears the auth state and navigates to `/login` via the Vue Router. A `redirecting` flag prevents multiple concurrent redirects.
- **Auth composable** (`useAuth.ts`): module-level reactive refs shared across all consumers. Provides `isAuthenticated`, `piholeUrl`, `checking`, `checkSession()`, `login()`, and `logout()`.

## Sync Service Lifecycle

The sync service is tied to the session:

- **Login** → `start_sync_service()` creates a `PiholeApiClient` with the session credentials and starts the background sync loop
- **Logout** → `stop_sync_service()` cancels the sync task and closes the Pi-hole client
- **Server restart with active session** → the lifespan handler checks for an active session and resumes the sync service automatically
- The sync manager (`sync_manager.py`) is extracted from `main.py` to avoid circular imports between the app factory and auth routes

## Security Notes

- This application is designed for **local network use only** and is not intended to be exposed to the public internet
- The Pi-hole password is held in server memory only for the duration of the session
- The `.env` file contains only the Pi-hole URL and operational settings — never the password
- The session cookie uses `httponly=True` and `samesite=strict` to prevent XSS and CSRF attacks
- The session cookie uses `secure=False` since local network deployments typically don't use HTTPS

## Implementation Files

### Backend Files

- `app/services/auth/session_store.py` — in-memory session store (`Session` dataclass, `SessionStore` class, global `session_store` singleton)
- `app/services/auth/config_store.py` — two-tier Pi-hole URL resolver (env var → database)
- `app/services/auth/middleware.py` — `require_session` FastAPI dependency, `SESSION_COOKIE` constant
- `app/routers/auth.py` — `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/status`, `GET /api/auth/check-url`
- `app/services/sync_manager.py` — sync service lifecycle management (start/stop), extracted to break circular imports

### Frontend Files

- `views/LoginView.vue` — URL field (read-only or editable with InputGroup), reachability check, password field, login form
- `router.ts` — route definitions, `beforeEach` navigation guard, `getRouter()` export for use by `apiFetch`
- `composables/useAuth.ts` — module-level reactive auth state, `checkSession()`, `login()`, `logout()`
- `utils/api.ts` — `apiFetch` wrapper with 401 redirect handling
- `App.vue` — header/nav hidden when unauthenticated, sign-out button

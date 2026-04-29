# CLAUDE.md — pihole-wtm

## Project Overview

**Stack**: FastAPI (Python 3.12, aiosqlite/SQLite) + Vue 3 (TypeScript, PrimeVue, Pinia, Vite). Dev via ddev.

**What it does**: Syncs Pi-hole v6 DNS query history, enriches domains with tracker intelligence (Ghostery TrackerDB, Disconnect.me, RDAP), and serves a dashboard.

---

## Key File Locations

| Concern | Path |
| --- | --- |
| All API routes | `backend/app/main.py` |
| Database queries + schema | `backend/app/services/database.py` |
| Pi-hole API client | `backend/app/services/pihole/api_client.py` |
| Background sync loop | `backend/app/services/sync.py` |
| App config / env vars | `backend/app/config.py` |
| API TypeScript types | `frontend/src/types/api.ts` |
| Report views | `frontend/src/views/` |
| Dialogs / layout components | `frontend/src/components/layout/` |
| Shared composables | `frontend/src/composables/` |
| Pinia stores | `frontend/src/stores/` |
| Backend tests | `backend/tests/` |
| Frontend tests | `frontend/src/tests/` |

---

## Database Tables

| Table | Key Columns | Purpose |
| --- | --- | --- |
| `queries` | `id, timestamp, domain, client_ip, status` | Raw DNS query log |
| `domains` | `domain, category, company, tracker` | Enriched domain info |
| `device_info` | `client_ip PK, name, hostname, mac_vendor, mdns_name, mdns_services` | Device names + auto-discovered info |
| `device_groups` | `id, name` | Named groups of client IPs |
| `device_group_members` | `group_id, client_ip` | Group membership (unique per IP) |
| `sync_state` | `last_synced_id` | Pi-hole sync cursor |
| `user_config` | `key, value` | User settings |
| `schema_version` | `version` | Migration tracking |

Schema lives in `_MIGRATIONS` in `database.py` — forward-only, version-stamped. Use `IF NOT EXISTS / IF EXISTS` in migrations.

---

## Architecture Patterns

**New stat/data type**: DB method in `database.py` → route in `main.py` → TS interface in `api.ts`.

**New dialog**: follow the `DeviceStatsDialog` / `ClientBreakdownDialog` pattern — `visible = ref(true)`, emits `close` on hide, `v-if` mount in parent view.

**Report filters**: `useReportData` composable owns filter state, URL query param sync, and data fetching for domain and client report views.

**Time window**: always use `useWindowStore().queryParams({...})` to build API query strings.

**Exclusions**: every new stats DB method must call `await this._apply_exclusions(conditions, params)`.

**Pi-hole sync loop**: `sync.py` runs `_sync_once()` every 60 s. Heavy passes (e.g. RDAP) run every 10 cycles via `_RDAP_EVERY_N_CYCLES`. Add new periodic passes with the same counter pattern in `run_sync_loop()`.

**Pi-hole API client**: `PiholeApiClient` handles auth (POST `/api/auth`, SID stored in `_sid`, sent as `X-FTL-SID` header). Add new Pi-hole endpoints as methods using the existing `_get()` helper.

**Device/client display**: all API responses carry `client_ip` and `client_name`. Frontend always renders `client_name ?? client_ip`. Backend resolves `client_name` via `COALESCE(di.name, di.hostname, di.mac_vendor)` joined from `device_info`.

---

## Frontend Conventions

**Icons**: PrimeIcons (`pi pi-*`) plus FontAwesome Free (`fa-brands`, `fa-solid`). Use `pi pi-mobile` as generic device fallback.

**Device name display**: render `client_name ?? client_ip` — `client_name` is the resolved fallback from the backend; never resolve client-side.

---

## Python Linting

Multi-line ruff suppression: use `# ruff: disable[RULE]` on the line before and `# ruff: enable[RULE]` after. Do **not** use `# noqa: RULE` on the opening line of a multi-line construct — it becomes part of the string content.

---

## Dev Commands

All commands via ddev; Python tools require the `.venv/bin/` prefix.

```bash
# Linting + type checking
ddev exec -d /var/www/html/backend .venv/bin/ruff check app tests
ddev exec -d /var/www/html/backend .venv/bin/mypy app
ddev exec -d /var/www/html/frontend npm run lint
ddev exec -d /var/www/html/frontend npm run type-check

# Tests
ddev exec -d /var/www/html/backend .venv/bin/pytest
ddev exec -d /var/www/html/frontend npm run test
```

---

## Commits

Conventional Commits: `feat:` → minor bump, `fix:` → patch bump, `chore:`/`refactor:`/`test:` → no changelog. Release Please batches into one release PR.

---

## CI / CD

**CI**: ruff/mypy/pytest + eslint/vue-tsc/vitest on every push and PR. **Release Please**: opens release PR on `feat:`/`fix:` commits to master; merge → GitHub release. **Release**: multi-arch Docker image (`amd64`, `arm64`, `arm/v7`) pushed to GHCR; frontend build pinned to `amd64` to avoid QEMU hangs.

---

## Code Review Workflow

After completing a significant feature or refactor, suggest a code review of files touched. Flag by severity: 🔴 Must Fix / 🟡 Should Fix / 🟢 Minor. Add deferred 🟢 items to [`docs/tech-debt.md`](docs/tech-debt.md).

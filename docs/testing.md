# Testing & CI Plan

Checklist for Phase 3 testing. Backend test infrastructure (pytest, pytest-asyncio) is already configured in `pyproject.toml`. Frontend needs vitest and vue-test-utils added.

---

## Backend Tests (pytest)

### Setup

- [x] Confirm `tests/` directory structure: `tests/conftest.py`, `tests/test_*.py`
- [x] Create shared fixtures: async test client, in-memory SQLite database, mock Pi-hole responses

### API Endpoints

- [x] `GET /api/health` — returns sync status, source health, data range
- [x] `GET /api/pihole/test` — Pi-hole connectivity check
- [x] `GET /api/pihole/summary` — summary stats passthrough
- [x] `GET /api/queries` — pagination (cursor, limit), status_type filter, tracker_only filter
- [x] `GET /api/stats/trackers` — time window params, client_ip filter
- [x] `GET /api/stats/timeline` — bucketed counts, hours/end_ts params
- [x] `GET /api/stats/timeline/clients` — per-client timeline buckets
- [x] `GET /api/stats/domains` — category, company, client_ip, domain, domain_exact filters
- [x] `GET /api/domains/search` — autocomplete search
- [x] `GET /api/stats/clients` — per-client aggregation with category/company filters
- [x] `GET /api/settings/options` — available categories and companies
- [x] `GET /api/settings` — returns all user config
- [x] `PUT /api/settings/{key}` — validation (int ranges, JSON arrays)
- [x] `GET /api/clients` — client list with names
- [x] `PUT /api/clients/{client_ip}` — set friendly name
- [x] `DELETE /api/clients/{client_ip}` — remove name mapping
- [x] `POST /api/admin/reenrich` — flags domains for re-enrichment
- [x] `POST /api/admin/reset` — clears data and resets sync

### Auth Routes

- [x] `GET /api/auth/status` — unauthenticated and authenticated responses
- [x] `GET /api/auth/check-url` — reachable and unreachable Pi-hole URLs
- [x] `POST /api/auth/login` — successful login, wrong password, unreachable Pi-hole
- [x] `POST /api/auth/logout` — clears session
- [x] Session middleware — missing cookie, expired session, valid session

### Database Service

- [x] Schema creation and migrations
- [x] Query storage (insert, deduplication via `INSERT OR IGNORE`)
- [x] Query fetch with filters (status_type, tracker_only, cursor pagination)
- [x] Tracker stats aggregation (by_category with companies)
- [x] Timeline bucketing (hourly for 24h, 6-hourly for 7d)
- [x] Domain stats with filters
- [x] Client stats aggregation
- [x] Domain search (prefix match)
- [x] Settings get/set (int config, JSON exclusion lists)
- [x] Client name CRUD
- [x] Data retention purge (orphaned domains cleanup)
- [x] Domain enrichment tracking (`needs_reenrichment` flag)

### Pi-hole API Client

- [x] `_authenticate()` — successful auth, failed auth (bad password), connection error
- [x] `_get()` — successful request, 401 re-authentication, connection error
- [x] Double-checked locking — concurrent requests only authenticate once
- [x] `get_summary()` — response parsing
- [x] `get_queries()` — pagination, cursor handling, field mapping
- [x] `test_connection()` — delegates through `_get()`
- [x] `close()` — session cleanup

### Sync Service

- [x] `_enrich_from_sources()` — priority ordering, fallback chain
- [x] `_gate_from_sources()` — exact-match filtering (allowed vs blocked)
- [x] `_process_batch()` — stores queries, enriches new domains
- [x] Batch processing with no new data (empty response)

### Tracker Sources

- [x] **TrackerDB** — `lookup_exact()` hit and miss, `enrich()` subdomain fallback, LRU cache behaviour, health check
- [x] **Disconnect.me** — `lookup_exact()` hit and miss, JSON loading, refresh-when-stale
- [x] Source registration via `get_tracker_sources()`

### Heuristic Enrichment

- [x] `extract_category()` — keyword matching (e.g. "analytics.example.com" → analytics)
- [x] `extract_company_name()` — eTLD+1 extraction
- [x] Edge cases: short domains, no match, ambiguous keywords

### RDAP + WHOIS

- [x] `lookup_company()` — successful RDAP lookup, privacy proxy detection
- [x] WHOIS fallback triggered when RDAP returns no registrant
- [x] WHOIS fallback filters privacy proxy names
- [x] WHOIS not called when RDAP succeeds
- [x] LRU cache behaviour
- [x] Network error handling

### Session Store

- [x] `create()` / `get()` / `delete()` / `clear()`
- [x] Idle timeout expiry
- [x] `get_active()` — returns None for expired sessions

---

## Frontend Tests (Vitest + Vue Test Utils)

### Frontend Setup

- [x] Install vitest, @vue/test-utils, jsdom
- [x] Create `vitest.config.ts` with Vue plugin and path aliases
- [x] Confirm test runner works with a trivial test

### Window Store

- [x] Default state (hours=24, periodsBack=0, isHistorical=false)
- [x] `availablePeriods` — filters by data span, always includes at least one
- [x] `goPrev()` / `goNext()` — increments/decrements periodsBack
- [x] `goOldest()` — calculates max periods from data range
- [x] `goLatest()` — resets to 0
- [x] `canGoPrev` / `canGoNext` — boundary conditions
- [x] `effectiveEndTs` / `fromTs` — derived from newestTs and periodsBack
- [x] `endTs` — null when live, computed when historical
- [x] `queryParams()` — builds correct query string with and without end_ts
- [x] Changing `hours` resets `periodsBack` to 0
- [x] `setDataRange()` updates oldestTs/newestTs

### Composables

- [x] **useAuth** — `checkSession()` sets auth state, `login()` success/failure, `logout()` clears state
- [x] **useHealth** — `fetchHealth()` updates health ref and window store data range, error handling
- [x] **useReportData** — filter application, URL param sync, `resetFilters()`, mode switching (domain/client)

### Utilities

- [x] `formatCategory()` — slug to title case ("ad_fraud" → "Ad Fraud", null → "Uncategorized")
- [x] `apiFetch()` — 401 triggers redirect to /login, normal responses pass through

---

## CI — GitHub Actions

### Workflow: `ci.yml` (on push and PR)

- [x] **Backend lint**: `ruff check .` (includes B and S rules)
- [x] **Backend type check**: `mypy app/`
- [x] **Backend tests**: `pytest`
- [x] **Frontend lint**: `eslint src/`
- [x] **Frontend type check**: `vue-tsc --noEmit`
- [x] **Frontend tests**: `vitest run`

### Workflow: `release.yml` (on tag, future)

- [ ] Multi-arch Docker build (amd64 + arm64)
- [ ] Push to GHCR

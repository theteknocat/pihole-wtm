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

### RDAP

- [x] `lookup_company()` — successful lookup, privacy proxy detection
- [x] LRU cache behaviour
- [x] Network error handling

### Session Store

- [x] `create()` / `get()` / `delete()` / `clear()`
- [x] Idle timeout expiry
- [x] `get_active()` — returns None for expired sessions

---

## Frontend Tests (Vitest + Vue Test Utils)

### Setup

- [ ] Install vitest, @vue/test-utils, jsdom
- [ ] Create `vitest.config.ts` with Vue plugin and path aliases
- [ ] Confirm test runner works with a trivial test

### Window Store

- [ ] Default state (hours=24, periodsBack=0, isHistorical=false)
- [ ] `availablePeriods` — filters by data span, always includes at least one
- [ ] `goPrev()` / `goNext()` — increments/decrements periodsBack
- [ ] `goOldest()` — calculates max periods from data range
- [ ] `goLatest()` — resets to 0
- [ ] `canGoPrev` / `canGoNext` — boundary conditions
- [ ] `effectiveEndTs` / `fromTs` — derived from newestTs and periodsBack
- [ ] `endTs` — null when live, computed when historical
- [ ] `queryParams()` — builds correct query string with and without end_ts
- [ ] Changing `hours` resets `periodsBack` to 0
- [ ] `setDataRange()` updates oldestTs/newestTs

### Composables

- [ ] **useAuth** — `checkSession()` sets auth state, `login()` success/failure, `logout()` clears state
- [ ] **useHealth** — `fetchHealth()` updates health ref and window store data range, error handling
- [ ] **useReportData** — filter application, URL param sync, `clearFilters()`, mode switching (domain/client)

### Utilities

- [ ] `formatCategory()` — slug to title case ("ad_fraud" → "Ad Fraud", null → "Uncategorized")
- [ ] `apiFetch()` — 401 triggers redirect to /login, normal responses pass through

---

## CI — GitHub Actions

### Workflow: `ci.yml` (on push and PR)

- [ ] **Backend lint**: `ruff check backend/` (includes B and S rules)
- [ ] **Backend type check**: `mypy backend/`
- [ ] **Backend tests**: `pytest --cov` with coverage threshold
- [ ] **Frontend lint**: `eslint frontend/src/`
- [ ] **Frontend type check**: `vue-tsc --noEmit`
- [ ] **Frontend tests**: `vitest run`

### Workflow: `release.yml` (on tag, future)

- [ ] Multi-arch Docker build (amd64 + arm64)
- [ ] Push to GHCR

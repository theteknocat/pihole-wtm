# Roadmap

This document describes the planned phased implementation of pihole-wtm. Phases are designed so each delivers independently useful functionality — the project is usable after Phase 1, and each subsequent phase adds meaningful depth.

---

## Phase 1: MVP — Functional Core

**Goal:** A working dashboard that proves the concept end-to-end. Sync query data from Pi-hole into a local database, enrich with TrackerDB, display results in a functional UI.

### Phase 1 — Backend

- [x] Project scaffolding: `pyproject.toml`, FastAPI app factory, pydantic-settings config
- [x] `PiholeApiClient` — Pi-hole v6 HTTP API with session authentication (httpx)
- [x] `TrackerSource` protocol — pluggable source interface with `lookup_exact()`, `enrich()`, `initialize()`, `refresh_if_stale()`, `api_router()`, plus `get_tracker_sources()` registry
- [x] `TrackerDBSource` — downloads trackerdb.db, subdomain fallback enrichment + LRU cache, exact-match gating, debug routes
- [x] `DisconnectSource` — services.json in-memory loader, exact-match lookup, debug routes
- [x] Stats endpoint: `/api/stats/trackers` (category + company breakdown by time window)
- [x] Queries endpoint: `/api/queries` (with status and tracker-only filtering)
- [x] Debug endpoints: `/api/debug/raw-query`, `/api/debug/pihole`
- [x] Local SQLite sync database (`pihole-wtm.db`) with `queries`, `domains`, `sync_state` tables
- [x] `SyncService` — background coroutine, cursor-based pagination, filtered storage
- [x] Migrate stats and queries endpoints to read from local database
- [x] `/api/stats/domains` — per-domain query breakdown with category/company filter
- [x] `/api/admin/reset` — clears all stored queries and domains, resets sync cursor
- [x] Exact-match-only gating for allowed queries (TrackerDB + Disconnect.me); subdomain fallback retained for display enrichment of blocked queries
- [x] Periodic source refresh via `refresh_if_stale()` — TrackerDB re-downloads when file is stale, Disconnect.me re-fetches when data age exceeds configured interval
- [x] Per-source health check and status on `/api/health` endpoint

### Phase 1 — Frontend

- [x] Vue 3 + Vite + TypeScript scaffold, Tailwind CSS, PrimeVue (Aura), Vue Router
- [x] App header with dark mode toggle, settings sidebar trigger
- [x] ~~`OverviewView`~~ System health info moved to app footer (backend status, Pi-hole connection, per-source indicators)
- [x] `DashboardView` — tracker category chart, top companies chart, top companies tables, recent query tables
- [x] `CategoryBarChart`, `CompanyBarChart` — horizontal stacked bar charts (blocked/allowed), clickable to drill down
- [x] `TopCompaniesTable` — clickable rows navigate to domain drill-down
- [x] `RecentQueriesTable` — enriched, tracker-only filter toggle
- [x] 24h / 7d time window selection, persisted across views via Pinia store
- [x] Dark mode (system default, persisted to localStorage)
- [x] `DetailedReportView` — domain/device breakdown with togglable grouping, category/company/device filters, navigated from dashboard
- [x] `SettingsSidebar` — slide-in panel with data reset (inline confirm/cancel)
- [x] Auto-refresh of all visible reports (30s interval and after settings changes)
- [x] `ClientNameDialog` — modal for assigning/clearing friendly names for client IP addresses
- [x] `DeviceStatsDialog` — per-device tracker breakdown chart with category/company toggle and click-through drill-down
- [x] Per-device query breakdown on Detailed Report (device grouping mode)
- [x] ~~`QueryLogView`~~ `DetailedReportView` — domain/device grouped report with category, company, and device filters (replaces original query log concept)
- [x] Domain search filter on Detailed Report (domain grouping mode) — autocomplete with exact match toggle
- [x] Loading skeleton states for all data tables and charts
- [x] Empty states for zero-data scenarios

### Phase 1 — Infrastructure

- [x] `.ddev/config.yaml` with `web_extra_daemons` for uvicorn and Vite dev server
- [x] `docker-compose.yml` for production deployment
- [x] `Dockerfile` — multi-stage build (frontend + backend + nginx in single image)
- [x] `docker/nginx.conf` — SPA routing + `/api` proxy to uvicorn
- [x] `.env.example` — all configurable environment variables

**Phase 1 outcome:** A deployable dashboard showing tracker stats, a browsable enriched query log, and category/company breakdown charts — all served from a local pre-enriched database.

---

## Phase 2: Enrichment Depth and Analysis Features

**Goal:** Richer tracker coverage, more actionable data, and deeper filtering.

### Phase 2 — Backend

- [x] Disconnect.me tracking protection lists as secondary enrichment source
- [x] eTLD+1 heuristic enrichment — company name from registered domain, category from subdomain keywords
- [x] RDAP company name lookup for heuristic-enriched domains (background upgrade pass, cached)
- [x] `needs_reenrichment` background re-processing when new enrichment sources are added
- [x] Graceful handling of enrichment gaps — unlabelled domains show category "Uncategorized"
- [x] Tracker source architecture refactor — `TrackerSource` protocol, pluggable source plugins with self-registration, per-source API routes, health checks, and lifecycle management; `main.py` fully source-agnostic
- [x] Tracker source configuration — `user_config` table in SQLite; excluded categories, companies, and domains stored as JSON arrays; exclusions applied at query time (display-only, data still collected)
- [x] `GET /api/stats/timeline` — bucketed query/block counts over time (hourly for 24h, 6-hourly for 7d)
- [x] `GET /api/stats/timeline/clients` — per-device bucketed query counts over time
- [x] Automatic data retention — default 7 days, purged each sync cycle, orphaned domains cleaned up (will be UI-configurable)
- [x] `/api/stats/clients` — per-client query aggregation with category/company filters
- [x] `/api/clients` — client IP listing with names and query counts; `PUT`/`DELETE` for name management
- [x] `client_names` table — user-managed friendly names for client IPs, joined at query time
- [ ] Full filtering on `/api/queries`: status, category, company, client IP, date range, domain search

### Phase 2 — Frontend

- [x] Tracker source configuration dialog — category checkboxes, company checkboxes with search, domain exclusion list; accessible from settings sidebar
- [x] `TimelineView` — dedicated page with summary stats and line + area chart, period selector (24h / 7d)
- [x] `DeviceTimelineChart` — stacked area chart showing per-device query volume below the main timeline
- [x] Header navigation — Dashboard and Timeline links with active-state highlighting
- [x] ~~Full filter panel on `QueryLogView`~~ Filters implemented on `DetailedReportView` (category, company, client IP)
- [x] Domain search filter on Detailed Report (domain grouping mode) — autocomplete with exact match toggle
- [x] URL query param sync for Detailed Report filters (category, company, client_ip)
- [x] Auto-refresh for Overview stats (uses shared refresh interval)
- [x] Connection error display when Pi-hole is unreachable

**Phase 2 outcome:** Full drill-down from tracker category → company → domain → individual queries. Richer company data from multiple enrichment sources. Historical timeline.

---

## Phase 3: Polish and Community Readiness

**Goal:** Make the project maintainable, well-documented, and welcoming to contributors. Cut a v1.0 release.

### Phase 3 — Testing

- [ ] Backend: 80%+ test coverage — all API endpoints, sync service, enricher edge cases
- [ ] Frontend: Vitest + `@vue/test-utils` for Pinia store logic and key components
- [ ] GitHub Actions CI: lint + type-check + test on every push and pull request

### Phase 3 — Deployment

- [ ] Multi-arch Docker image builds (`linux/amd64` and `linux/arm64` for Raspberry Pi)
- [ ] GitHub Actions release workflow: tag → build → push to GitHub Container Registry (GHCR)
- [ ] Unraid Community App template
- [ ] Rate limiting on API endpoints (`slowapi`)
- [ ] Content Security Policy headers in nginx config
- [ ] `pihole-wtm setup` CLI command — interactive first-run configuration wizard, validates Pi-hole connection and writes `.env` file (see `docs/configuration.md`)

### Phase 3 — Documentation

- [ ] All `docs/` pages complete and reviewed
- [ ] Screenshots in README
- [ ] API reference doc generated from FastAPI OpenAPI spec
- [ ] `CONTRIBUTING.md` with code style guide, PR process, and development workflow
- [ ] `CHANGELOG.md` initialised

### Phase 3 — UX Polish

- [ ] Responsive layout (tablet and mobile friendly)
- [ ] Empty states for zero-data scenarios (no Pi-hole connected, no queries in range)
- [x] ~~Onboarding flow in `OverviewView`~~ Login page handles first-time setup (Pi-hole URL entry + reachability check)
- [ ] Country flag display for tracker companies
- [ ] Tooltip explanations for each tracker category on hover

### Phase 3 — Security

- [ ] Audit: Pi-hole password never logged, masked in settings UI
- [ ] Confirm local database is never exposed directly (backend process only)
- [ ] Input validation on all API endpoints
- [ ] Dependency vulnerability scanning in CI (`pip-audit`, `npm audit`)

**Phase 3 outcome:** A polished v1.0.0 release with multi-arch Docker images, automated CI/CD, comprehensive tests, and complete documentation.

---

## Future Ideas (Post-v1.0)

These are not committed to any phase but are worth tracking as potential future directions:

- **Notifications** — alert when a new tracker category is first seen, or when blocked query rate spikes
- **Allowlist/blocklist suggestions** — surface domains that are pure trackers but not yet on the Pi-hole blocklist
- **Multiple Pi-hole instances** — support monitoring multiple Pi-hole installations from one dashboard
- **Export** — CSV/JSON export of enriched query data
- ~~**Authentication** — optional login to protect the dashboard~~ **Done** — see [authentication.md](authentication.md)
- **Grafana data source plugin** — for users who already have Grafana dashboards
- **DuckDuckGo Tracker Radar** — [duckduckgo/tracker-radar](https://github.com/duckduckgo/tracker-radar) as an additional enrichment source. Rich per-domain data (categories, company/owner, prevalence, fingerprinting scores) across ~1000+ categorized domains. Dataset is distributed as individual JSON files per domain per region (~100MB+ full tarball). Implementation challenge is efficient ingestion — options include downloading the full release tarball and extracting only domain JSON files, or using just the `build-data/static/categorized_trackers.csv` (~1000 domains, categories only, no company data) as a lighter alternative

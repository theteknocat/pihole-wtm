# Roadmap

This document describes the planned phased implementation of pihole-wtm. Phases are designed so each delivers independently useful functionality — the project is usable after Phase 1, and each subsequent phase adds meaningful depth.

---

## Phase 1: MVP — Functional Core

**Goal:** A working dashboard that proves the concept end-to-end. Sync query data from Pi-hole into a local database, enrich with TrackerDB, display results in a functional UI.

### Phase 1 — Backend

- [x] Project scaffolding: `pyproject.toml`, FastAPI app factory, pydantic-settings config
- [x] `PiholeApiClient` — Pi-hole v6 HTTP API with session authentication (httpx)
- [x] `TrackerdbLoader` — downloads `trackerdb.db` from Ghostery GitHub releases on startup
- [x] `TrackerRepository` — domain lookup SQL against `trackerdb.db`
- [x] `TrackerEnricher` — subdomain fallback logic (exact → eTLD+1 → parent domains), LRU cached
- [x] Stats endpoint: `/api/stats/trackers` (category + company breakdown by time window)
- [x] Queries endpoint: `/api/queries` (with status and tracker-only filtering)
- [x] Debug endpoints: `/api/debug/raw-query`, `/api/debug/pihole`
- [x] Local SQLite sync database (`pihole-wtm.db`) with `queries`, `domains`, `sync_state` tables
- [x] `SyncService` — background coroutine, cursor-based pagination, filtered storage
- [x] Migrate stats and queries endpoints to read from local database
- [ ] Background task for periodic TrackerDB refresh

### Phase 1 — Frontend

- [x] Vue 3 + Vite + TypeScript scaffold, Tailwind CSS, PrimeVue (Aura), Vue Router
- [x] `AppHeader` with dark mode toggle and Pi-hole status indicator
- [x] `OverviewView` — health check, Pi-hole connection status
- [x] `DashboardView` — tracker category chart, top companies chart, top companies tables, recent query tables
- [x] `CategoryBarChart`, `CompanyBarChart` — horizontal stacked bar charts (blocked/allowed)
- [x] `TopCompaniesTable`, `RecentQueriesTable` — sortable, enriched
- [x] 24h / 7d time window toggle, tracker-only filter toggle
- [x] Dark mode (system default, persisted to localStorage)
- [ ] `QueryLogView` — full paginated, filterable query log (separate page)
- [ ] Loading skeleton states for all data tables and charts
- [ ] Empty states for zero-data scenarios

### Phase 1 — Infrastructure

- [x] `.ddev/config.yaml` with `web_extra_daemons` for uvicorn and Vite dev server
- [ ] `docker-compose.yml` for production deployment
- [ ] `docker/backend.Dockerfile` and `docker/frontend.Dockerfile`
- [ ] `nginx.conf` — SPA routing + `/api` proxy
- [ ] `.env.example`

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
- [ ] `GET /api/stats/timeline` — bucketed query/block counts over time (24h, 7d, 30d)
- [ ] Full filtering on `/api/queries`: status, category, company, client IP, date range, domain search

### Phase 2 — Frontend

- [ ] `QueryTimeline` — line + area chart, period selector (24h / 7d / 30d)
- [ ] Full filter panel on `QueryLogView` (status, category, company, client IP, date range, domain search)
- [ ] URL query param sync for all filters (shareable/bookmarkable URLs)
- [ ] Auto-refresh for Overview stats (configurable interval)
- [ ] Connection error display when Pi-hole is unreachable

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
- [ ] Onboarding flow in `OverviewView` when no Pi-hole connection is configured
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
- **Per-client breakdown** — show which devices on the network generate the most tracker queries
- **Export** — CSV/JSON export of enriched query data
- **Authentication** — optional login to protect the dashboard on networks where it shouldn't be publicly accessible (see `docs/authentication.md`)
- **Grafana data source plugin** — for users who already have Grafana dashboards

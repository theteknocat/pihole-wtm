# Roadmap

This document describes the planned phased implementation of pihole-wtm. Phases are designed so each delivers independently useful functionality — the project is usable after Phase 1, and each subsequent phase adds meaningful depth.

---

## Phase 1: MVP — Functional Core

**Goal:** A working dashboard that proves the concept end-to-end. Query data from Pi-hole, enrich it with TrackerDB, display the results in a basic but functional UI.

### Backend

- [ ] Project scaffolding: `pyproject.toml`, FastAPI app factory, pydantic-settings config, `.gitignore`, `Makefile`
- [ ] `PiholeClient` abstract interface with `RawQuery` and `SummaryStats` Pydantic models
- [ ] `SqliteClient` — reads from `pihole-FTL.db` via `aiosqlite`
- [ ] `ApiClient` — Pi-hole v6 HTTP API with session authentication (httpx)
- [ ] `TrackerdbLoader` — downloads `trackerdb.db` from Ghostery GitHub releases on startup
- [ ] `TrackerRepository` — domain lookup SQL against `trackerdb.db`
- [ ] `TrackerEnricher` — subdomain fallback logic (exact → eTLD+1 → parent domains)
- [ ] LRU cache wrapping the enricher (50k entries)
- [ ] `EnrichmentService` — orchestrates PiholeClient + TrackerEnricher
- [ ] API endpoints: `/api/health`, `/api/stats/summary`, `/api/queries`, `/api/trackers/categories`
- [ ] Background task for periodic TrackerDB refresh
- [ ] Basic test suite with fixture databases

### Frontend

- [ ] Vue 3 + Vite + TypeScript scaffold, Tailwind CSS, Pinia, Vue Router
- [ ] `AppSidebar` and `AppHeader` layout components
- [ ] `SettingsView` — connection mode selector + test button
- [ ] `OverviewView` — four `KpiCard` tiles (total queries, blocked %, tracker types seen, top company)
- [ ] `CategoryPieChart` — doughnut chart of tracker categories
- [ ] `QueryLogView` — basic `QueryTable` with tracker category and company columns
- [ ] `CategoryBadge` and `StatusBadge` UI components

### Infrastructure

- [ ] `.ddev/config.yaml` with `web_extra_daemons` for uvicorn and Vite
- [ ] `docker-compose.yml` for production deployment
- [ ] `docker/backend.Dockerfile` and `docker/frontend.Dockerfile`
- [ ] `nginx.conf` — SPA routing + `/api` proxy
- [ ] `.env.example`
- [ ] End-to-end test: `ddev start` → load dashboard → see enriched query data

**Phase 1 outcome:** A deployable dashboard at `localhost:8080` showing query stats, a browsable enriched query log, and a category breakdown chart.

---

## Phase 2: Enrichment and Analysis Features

**Goal:** Make the data actionable. Historical trends, drill-down by company and domain, robust filtering, Pi-hole v5 support.

### Backend

- [ ] `GET /api/stats/timeline` — bucketed query/block counts over time (24h, 7d, 30d)
- [ ] `GET /api/trackers/companies` — top companies by blocked query count, filterable by category
- [ ] `GET /api/trackers/domains` — top domains by query count, filterable by company
- [ ] Pi-hole v5 API support in `ApiClient` (legacy `api.php` endpoints)
- [ ] Auto-detection of Pi-hole API version
- [ ] Pagination and filtering on `/api/queries` (status, category, company, client IP, date range, domain search)
- [ ] Graceful handling of domains not in TrackerDB (labelled "Unknown")
- [ ] Auto-reconnect on Pi-hole v6 session expiry

### Frontend

- [ ] `QueryTimeline` — line + area chart, period selector (24h / 7d / 30d)
- [ ] `TrackersView` — category filter tabs, `TrackerTable`, `TopCompaniesBar` chart
- [ ] Click-through from chart segments to filtered query log
- [ ] Full filter panel on `QueryLogView` (status, category, company, client IP, date range, domain search)
- [ ] URL query param sync for all filters (shareable/bookmarkable URLs)
- [ ] Loading skeleton states for all data tables and charts
- [ ] Connection error display in `AppHeader` when Pi-hole is unreachable
- [ ] Auto-refresh for Overview stats (configurable interval, default 30s)
- [ ] Dark mode toggle (via `@vueuse/core` `useDark`)

**Phase 2 outcome:** Full drill-down capability from tracker category → company → domain → individual queries. Historical timeline. Robust error handling. Production-grade behaviour.

---

## Phase 3: Polish and Community Readiness

**Goal:** Make the project maintainable, well-documented, and welcoming to contributors. Cut a v1.0 release.

### Testing

- [ ] Backend: 80%+ test coverage — all API endpoints, both Pi-hole clients, enricher edge cases
- [ ] Frontend: Vitest + `@vue/test-utils` for Pinia store logic and key components
- [ ] GitHub Actions CI: lint + type-check + test on every push and pull request

### Deployment

- [ ] Multi-arch Docker image builds (`linux/amd64` and `linux/arm64` for Raspberry Pi)
- [ ] GitHub Actions release workflow: tag → build → push to GitHub Container Registry (GHCR)
- [ ] Unraid Community App template
- [ ] Rate limiting on API endpoints (`slowapi`)
- [ ] Content Security Policy headers in nginx config

### Documentation

- [ ] All `docs/` pages complete and reviewed
- [ ] Screenshots in README
- [ ] API reference doc generated from FastAPI OpenAPI spec
- [ ] `CONTRIBUTING.md` with code style guide, PR process, and development workflow
- [ ] `CHANGELOG.md` initialised

### UX Polish

- [ ] Responsive layout (tablet and mobile friendly)
- [ ] Empty states for zero-data scenarios (no Pi-hole connected, no queries in range)
- [ ] Onboarding flow in `SettingsView` when no connection is configured
- [ ] Country flag display for tracker companies
- [ ] Tooltip explanations for each tracker category on hover

### Security

- [ ] Audit: Pi-hole password never logged, masked in SettingsView UI
- [ ] Confirm read-only SQLite access (no write operations possible)
- [ ] Input validation on all API endpoints
- [ ] Dependency vulnerability scanning in CI (e.g., `pip-audit`, `npm audit`)

**Phase 3 outcome:** A polished v1.0.0 release with multi-arch Docker images, automated CI/CD, comprehensive tests, and a complete documentation site.

---

## Future Ideas (Post-v1.0)

These are not committed to any phase but are worth tracking as potential future directions:

- **Notifications** — alert when a new type of tracker is first seen, or when blocked query rate spikes
- **Allowlist/blocklist suggestions** — surface domains that are pure trackers but not yet on the Pi-hole blocklist
- **Multiple Pi-hole instances** — support monitoring multiple Pi-hole installations from one dashboard
- **Per-client breakdown** — show which devices on the network generate the most tracker queries
- **Export** — CSV/JSON export of enriched query data
- **Grafana data source plugin** — for users who already have Grafana dashboards

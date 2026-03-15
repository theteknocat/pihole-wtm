# Project Structure

This document describes the intended directory layout of the pihole-wtm repository and explains the purpose of each significant file and directory.

```text
pihole-wtm/
│
├── README.md                          # Project overview and quick-start
│
├── .ddev/                             # ddev local development environment
│   ├── config.yaml                    # ddev project config (generic type)
│   ├── docker-compose.backend.yaml    # Custom service: exposes backend/frontend ports
│   └── commands/
│       └── web/
│           └── pihole-wtm             # Custom ddev command for convenience tasks
│
├── backend/                           # Python FastAPI application
│   ├── pyproject.toml                 # Project metadata and dependencies (PEP 621)
│   ├── uv.lock                        # Reproducible lock file (managed by uv)
│   ├── data/                          # Runtime data directory (gitignored)
│   │   ├── trackerdb.db               # Downloaded Ghostery TrackerDB (auto-managed)
│   │   └── pihole-wtm.db              # Local sync database (auto-created on first run)
│   │
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, lifespan hooks, CORS config
│   │   ├── config.py                  # Pydantic-settings: all env var definitions
│   │   ├── dependencies.py            # FastAPI dependency injectors (get_db, etc.)
│   │   │
│   │   ├── routers/                   # One module per resource group
│   │   │   ├── health.py              # GET /api/health
│   │   │   ├── stats.py               # GET /api/stats/trackers, /api/stats/timeline
│   │   │   ├── queries.py             # GET /api/queries
│   │   │   └── debug.py               # GET /api/debug/raw-query, /api/debug/pihole
│   │   │
│   │   ├── services/
│   │   │   ├── pihole/
│   │   │   │   └── api_client.py      # httpx client for Pi-hole v6 HTTP API
│   │   │   ├── trackerdb/
│   │   │   │   ├── loader.py          # Download/cache trackerdb.db from Ghostery releases
│   │   │   │   ├── repository.py      # aiosqlite queries against trackerdb.db
│   │   │   │   └── enricher.py        # Domain → TrackerInfo with subdomain fallback + LRU cache
│   │   │   ├── sync/
│   │   │   │   ├── service.py         # Background sync coroutine (polls Pi-hole, stores queries)
│   │   │   │   └── database.py        # Local SQLite setup, schema creation, query helpers
│   │   │   ├── enrichment/
│   │   │   │   ├── pipeline.py        # Orchestrates enrichment sources in priority order
│   │   │   │   ├── disconnect.py      # Disconnect.me list loader and domain lookup
│   │   │   │   └── rdap.py            # RDAP company name lookup (async, cached)
│   │   │   └── stats.py               # Aggregation queries for dashboard stats
│   │   │
│   │   └── models/
│   │       ├── pihole.py              # Pydantic: RawQuery, SummaryStats
│   │       ├── tracker.py             # Pydantic: TrackerInfo, CategoryBreakdown, Company
│   │       └── enriched.py            # Pydantic: EnrichedQuery, TrackerSummary
│   │
│   └── tests/
│       ├── conftest.py                # Shared fixtures: test app, mock clients, temp databases
│       ├── test_api_client.py
│       ├── test_enricher.py
│       ├── test_sync_service.py
│       ├── test_routes_stats.py
│       ├── test_routes_queries.py
│       └── fixtures/
│           ├── sample_trackerdb.db    # Minimal TrackerDB for tests
│           └── sample_pihole_wtm.db   # Minimal local database for tests
│
├── frontend/                          # Vue 3 + Vite TypeScript SPA
│   ├── index.html                     # Vite entry point
│   ├── vite.config.ts                 # Vite config: dev proxy, build output
│   ├── tsconfig.json
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── .env.development               # VITE_API_BASE_URL=http://localhost:8000
│   ├── .env.production                # VITE_API_BASE_URL=/api (nginx proxy)
│   ├── public/
│   │   └── favicon.svg
│   └── src/
│       ├── main.ts                    # createApp, router, pinia, PrimeVue
│       ├── App.vue                    # Root: AppHeader + RouterView
│       ├── style.css                  # CSS layer ordering, dark mode base styles
│       │
│       ├── router/
│       │   └── index.ts               # Route definitions
│       │
│       ├── stores/                    # Pinia stores
│       │   ├── stats.ts               # Tracker stats and timeline data
│       │   ├── queries.ts             # Query log with filters and pagination
│       │   └── trackers.ts            # Category/company breakdown data
│       │
│       ├── api/                       # API client functions (fetch wrappers)
│       │   ├── client.ts              # Base fetch wrapper, error handling
│       │   ├── stats.ts
│       │   ├── queries.ts
│       │   └── trackers.ts
│       │
│       ├── composables/
│       │   └── useAuth.ts             # Auth state (placeholder until auth is implemented)
│       │
│       ├── views/                     # Top-level route components
│       │   ├── OverviewView.vue       # Pi-hole connection status and health
│       │   ├── DashboardView.vue      # Main tracker dashboard (charts + tables)
│       │   ├── QueryLogView.vue       # Paginated, filterable enriched query log
│       │   └── SettingsView.vue       # Pi-hole connection configuration
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppSidebar.vue     # Navigation sidebar
│       │   │   └── AppHeader.vue      # Top bar with dark mode toggle + Pi-hole status
│       │   ├── dashboard/
│       │   │   ├── CategoryBarChart.vue    # Horizontal stacked bar: tracker categories
│       │   │   ├── CompanyBarChart.vue     # Horizontal stacked bar: top companies
│       │   │   ├── TopCompaniesTable.vue   # Sortable top companies table
│       │   │   └── RecentQueriesTable.vue  # Recent blocked/allowed queries table
│       │   ├── charts/
│       │   │   └── QueryTimeline.vue       # Area chart: queries over time
│       │   ├── tables/
│       │   │   └── QueryTable.vue          # Full query log table
│       │   └── ui/
│       │       ├── KpiCard.vue             # Summary stat tile
│       │       ├── CategoryBadge.vue       # Colour-coded tracker category pill
│       │       └── StatusBadge.vue         # Pi-hole query status (blocked/allowed/cached)
│       │
│       └── types/
│           └── api.ts                 # TypeScript interfaces mirroring backend response shapes
│
├── docs/                              # Project documentation (you are here)
│   ├── overview.md                    # Vision, problem statement, use cases
│   ├── architecture.md                # System design, data flow, database schema
│   ├── project-structure.md           # This file
│   ├── development.md                 # Local development with ddev
│   ├── configuration.md               # Environment variable reference
│   ├── deployment.md                  # Production deployment guide
│   ├── roadmap.md                     # Phased implementation plan
│   ├── tracker-categories.md          # Tracker category reference
│   ├── authentication.md              # Planned authentication design
│   └── tech-debt.md                   # Deferred fixes and lower-priority improvements
│
├── docker/
│   ├── backend.Dockerfile             # Python production image
│   └── frontend.Dockerfile            # Multi-stage: Vite build + nginx serve
│
├── docker-compose.yml                 # Production: backend + frontend + volumes
├── docker-compose.dev.yml             # Optional non-ddev docker dev setup
├── nginx.conf                         # nginx: SPA routing + /api proxy
├── .env.example                       # Template for all required environment variables
├── .gitignore
├── .editorconfig                      # Consistent editor settings across contributors
└── Makefile                           # Convenience targets: dev, test, build, lint, docker
```

## Key Conventions

### Backend

- All configuration comes from environment variables, parsed by `pydantic-settings` in `app/config.py`. No hardcoded values.
- Routers are thin: they validate input and return output. Business logic lives in `services/`.
- API routers read exclusively from the local SQLite database — never from the Pi-hole API directly. Only the sync service calls the Pi-hole API.
- `aiosqlite` is used for all SQLite access (async, non-blocking). WAL mode is enabled on `pihole-wtm.db` for concurrent reads during writes.
- `httpx.AsyncClient` is used for all outbound HTTP calls.
- Enrichment runs in the background, not in the request path. API responses are always fast.

### Frontend

- All API calls go through `src/api/` functions — never `fetch()` directly in components or stores.
- Components do not own data — they read from Pinia stores and dispatch store actions.
- Type definitions in `src/types/` are kept in sync with backend Pydantic response shapes.
- Environment-specific configuration (API base URL) comes from `.env.*` files, not hardcoded strings.
- Dark mode uses `useDark()` from `@vueuse/core`, which reads the system preference and persists the user's choice to localStorage.
- No pie charts. Bar charts only.

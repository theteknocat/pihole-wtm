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
│   │   └── trackerdb.db               # Downloaded Ghostery TrackerDB (auto-managed)
│   │
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory, lifespan hooks, CORS config
│   │   ├── config.py                  # Pydantic-settings: all env var definitions
│   │   ├── dependencies.py            # FastAPI dependency injectors (get_pihole_client, etc.)
│   │   │
│   │   ├── routers/                   # One module per resource group
│   │   │   ├── health.py              # GET /api/health
│   │   │   ├── stats.py               # GET /api/stats/summary, /api/stats/timeline
│   │   │   ├── queries.py             # GET /api/queries
│   │   │   ├── trackers.py            # GET /api/trackers/categories, /companies, /domains
│   │   │   └── settings.py            # GET /api/settings, POST /api/settings/test-connection
│   │   │
│   │   ├── services/
│   │   │   ├── pihole/
│   │   │   │   ├── base.py            # Abstract PiholeClient interface
│   │   │   │   ├── sqlite_client.py   # Direct aiosqlite reader for pihole-FTL.db
│   │   │   │   └── api_client.py      # httpx client for Pi-hole HTTP API (v5 + v6)
│   │   │   ├── trackerdb/
│   │   │   │   ├── loader.py          # Download/cache trackerdb.db from Ghostery releases
│   │   │   │   ├── repository.py      # aiosqlite queries against trackerdb.db
│   │   │   │   └── enricher.py        # Domain → TrackerInfo with subdomain fallback
│   │   │   └── enrichment.py          # Orchestrates PiholeClient + TrackerEnricher
│   │   │
│   │   ├── models/
│   │   │   ├── pihole.py              # Pydantic: RawQuery, SummaryStats
│   │   │   ├── tracker.py             # Pydantic: TrackerInfo, CategoryBreakdown, Company
│   │   │   └── enriched.py            # Pydantic: EnrichedQuery, TrackerSummary
│   │   │
│   │   ├── cache/
│   │   │   └── tracker_cache.py       # LRU cache wrapping TrackerEnricher
│   │   │
│   │   └── tasks/
│   │       └── tracker_sync.py        # Background coroutine: periodic TrackerDB refresh
│   │
│   └── tests/
│       ├── conftest.py                # Shared fixtures: test app, mock clients
│       ├── test_sqlite_client.py
│       ├── test_api_client.py
│       ├── test_enricher.py
│       ├── test_routes_stats.py
│       ├── test_routes_queries.py
│       └── fixtures/
│           ├── sample_ftl.db          # Minimal Pi-hole SQLite DB for tests
│           └── sample_trackerdb.db    # Minimal TrackerDB for tests
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
│       ├── main.ts                    # createApp, router, pinia
│       ├── App.vue                    # Root: layout shell with RouterView
│       │
│       ├── router/
│       │   └── index.ts               # Route definitions
│       │
│       ├── stores/                    # Pinia stores
│       │   ├── stats.ts               # Summary stats, timeline data
│       │   ├── queries.ts             # Query log with filters and pagination
│       │   ├── trackers.ts            # Category/company breakdown data
│       │   └── settings.ts            # Pi-hole connection config (persisted to localStorage)
│       │
│       ├── api/                       # API client functions (fetch wrappers)
│       │   ├── client.ts              # Base fetch wrapper, error handling
│       │   ├── stats.ts
│       │   ├── queries.ts
│       │   └── trackers.ts
│       │
│       ├── views/                     # Top-level route components
│       │   ├── OverviewView.vue       # KPI tiles + category chart + timeline
│       │   ├── QueryLogView.vue       # Paginated, filterable query table
│       │   ├── TrackersView.vue       # Category/company breakdown
│       │   └── SettingsView.vue       # Pi-hole connection configuration
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppSidebar.vue     # Navigation sidebar
│       │   │   └── AppHeader.vue      # Top bar with Pi-hole status indicator
│       │   ├── charts/
│       │   │   ├── CategoryPieChart.vue   # Doughnut: tracker categories
│       │   │   ├── QueryTimeline.vue      # Area chart: queries over time
│       │   │   └── TopCompaniesBar.vue    # Horizontal bar: top companies
│       │   ├── tables/
│       │   │   ├── QueryTable.vue         # Main query log table
│       │   │   └── TrackerTable.vue       # Company/domain breakdown table
│       │   └── ui/
│       │       ├── KpiCard.vue            # Summary stat tile
│       │       ├── CategoryBadge.vue      # Colour-coded tracker category pill
│       │       ├── StatusBadge.vue        # Pi-hole query status (blocked/allowed/cached)
│       │       └── LoadingSpinner.vue
│       │
│       └── types/                     # TypeScript type definitions mirroring backend models
│           ├── pihole.ts
│           ├── tracker.ts
│           └── enriched.ts
│
├── docs/                              # Project documentation (you are here)
│   ├── overview.md                    # Vision, problem statement, use cases
│   ├── architecture.md                # System design and data flow
│   ├── project-structure.md           # This file
│   ├── development.md                 # Local development with ddev
│   ├── configuration.md               # Environment variable reference
│   ├── deployment.md                  # Production deployment guide
│   ├── roadmap.md                     # Phased implementation plan
│   └── tracker-categories.md          # Tracker category reference
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
- All Pi-hole data access goes through the `PiholeClient` abstract interface — never import `SqliteClient` or `ApiClient` directly in routers.
- `aiosqlite` is used for all SQLite access (async, non-blocking).
- `httpx.AsyncClient` is used for all outbound HTTP calls.

### Frontend

- All API calls go through `src/api/` functions — never `fetch()` directly in components or stores.
- Components do not own data — they read from Pinia stores and dispatch store actions.
- Type definitions in `src/types/` are kept in sync with backend Pydantic models.
- Environment-specific configuration (API base URL) comes from `.env.*` files, not hardcoded strings.

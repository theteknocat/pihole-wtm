# Project Structure

This document describes the intended directory layout of the pihole-wtm repository and explains the purpose of each significant file and directory.

```text
pihole-wtm/
│
├── README.md                          # Project overview and quick-start
│
├── .ddev/                             # ddev local development environment
│   └── config.yaml                    # ddev project config (ports, daemons, env vars, hooks)
│
├── backend/                           # Python FastAPI application
│   ├── pyproject.toml                 # Project metadata and dependencies (PEP 621)
│   ├── uv.lock                        # Reproducible lock file (managed by uv)
│   ├── data/                          # Runtime data directory (gitignored)
│   │   ├── trackerdb.db               # Downloaded Ghostery TrackerDB (auto-managed)
│   │   └── pihole_wtm.db              # Local sync database (auto-created on first run)
│   │
│   └── app/
│       ├── main.py                    # FastAPI app factory, lifespan, CORS config, all routes
│       ├── config.py                  # Pydantic-settings: all env var definitions
│       │
│       ├── models/
│       │   ├── pihole.py              # Pydantic: RawQuery, SummaryStats
│       │   └── tracker.py             # Pydantic: TrackerInfo
│       │
│       └── services/
│           ├── database.py            # Local SQLite: schema, sync state, query/domain helpers
│           ├── sync.py                # Background sync coroutine + enrichment orchestration
│           ├── heuristic.py           # eTLD+1 company name + subdomain keyword category
│           ├── rdap.py                # RDAP company name lookup (async, LRU cached)
│           ├── pihole/
│           │   └── api_client.py      # httpx client for Pi-hole v6 HTTP API
│           ├── trackerdb/
│           │   ├── loader.py          # Download/cache trackerdb.db from Ghostery releases
│           │   ├── repository.py      # aiosqlite queries against trackerdb.db
│           │   └── enricher.py        # Domain → TrackerInfo with subdomain fallback + LRU cache
│           └── disconnect/
│               └── loader.py          # Disconnect.me services.json loader and domain lookup
│
├── frontend/                          # Vue 3 + Vite TypeScript SPA
│   ├── index.html                     # Vite entry point
│   ├── vite.config.ts                 # Vite config: dev proxy, build output
│   ├── tsconfig.json
│   ├── package.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.ts                    # createApp, router, pinia, PrimeVue
│       ├── App.vue                    # Root: AppHeader + RouterView
│       ├── style.css                  # CSS layer ordering, dark mode base styles
│       │
│       ├── router/
│       │   └── index.ts               # Route definitions
│       │
│       ├── stores/                    # Pinia stores
│       │   └── trackerStats.ts        # Tracker stats data and time window state
│       │
│       ├── api/                       # API client functions (fetch wrappers)
│       │   └── client.ts              # Base fetch wrapper, error handling
│       │
│       ├── views/                     # Top-level route components
│       │   ├── OverviewView.vue       # Pi-hole connection status and health
│       │   └── DashboardView.vue      # Main tracker dashboard (charts + tables)
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   └── AppHeader.vue      # Top bar with dark mode toggle + Pi-hole status
│       │   └── dashboard/
│       │       ├── CategoryBarChart.vue    # Horizontal stacked bar: tracker categories
│       │       ├── CompanyBarChart.vue     # Horizontal stacked bar: top companies
│       │       ├── TopCompaniesTable.vue   # Sortable top companies table
│       │       └── RecentQueriesTable.vue  # Recent blocked/allowed queries table
│       │
│       └── types/
│           └── api.ts                 # TypeScript interfaces mirroring backend response shapes
│
└── docs/                              # Project documentation (you are here)
    ├── overview.md                    # Vision, problem statement, use cases
    ├── architecture.md                # System design, data flow, database schema
    ├── project-structure.md           # This file
    ├── development.md                 # Local development with ddev
    ├── configuration.md               # Environment variable reference
    ├── deployment.md                  # Production deployment guide
    ├── roadmap.md                     # Phased implementation plan
    ├── tracker-categories.md          # Tracker category reference
    ├── authentication.md              # Planned authentication design
    └── tech-debt.md                   # Deferred fixes and lower-priority improvements
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

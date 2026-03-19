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
│           ├── sources.py             # TrackerSource protocol + get_tracker_sources() registry
│           ├── database.py            # Local SQLite: schema, sync state, query/domain helpers
│           ├── sync.py                # Background sync coroutine + enrichment orchestration
│           ├── heuristic.py           # eTLD+1 company name + subdomain keyword category
│           ├── rdap.py                # RDAP company name lookup (async, LRU cached)
│           ├── pihole/
│           │   └── api_client.py      # httpx client for Pi-hole v6 HTTP API
│           ├── trackerdb/
│           │   └── source.py          # TrackerDBSource: download, lookup, enrich, debug routes
│           └── disconnectme/
│               └── source.py          # DisconnectSource: services.json loader, lookup, debug routes
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
│       ├── App.vue                    # Root: header (logo, nav, dark mode, settings) + RouterView
│       ├── style.css                  # CSS layer ordering, dark mode base styles
│       │
│       ├── stores/                    # Pinia stores
│       │   └── window.ts              # Shared time window, refreshKey, reportGroupBy (localStorage-persisted)
│       │
│       ├── views/                     # Top-level route components
│       │   ├── OverviewView.vue       # System health: backend, Pi-hole, and per-source status
│       │   ├── DashboardView.vue      # Tracker charts, company tables, recent queries
│       │   ├── TimelineView.vue       # Query volume timeline with summary stats
│       │   └── DetailedReportView.vue # Domain/device breakdown with filters; togglable grouping
│       │
│       ├── composables/
│       │   ├── useAuth.ts             # Authentication state composable
│       │   ├── useScrolled.ts         # Reactive scroll-position tracker for sticky header compaction
│       │   └── useTrackerBarChart.ts  # Shared bar chart config (datasets, tooltips, scales)
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── SettingsSidebar.vue     # Slide-in settings panel (data reset, config access)
│       │   │   ├── ConfigDialog.vue        # Tracker source exclusion config (categories, companies, domains)
│       │   │   ├── ClientNameDialog.vue    # Modal for setting/clearing a friendly name for a client IP
│       │   │   └── DeviceStatsDialog.vue   # Near-fullscreen modal: per-device tracker breakdown chart
│       │   ├── timeline/
│       │   │   ├── TimelineChart.vue       # Line + area chart: blocked/allowed query volume over time
│       │   │   └── DeviceTimelineChart.vue # Stacked area chart: per-device query volume over time
│       │   └── dashboard/
│       │       ├── CategoryBarChart.vue    # Horizontal stacked bar: tracker categories (clickable)
│       │       ├── CompanyBarChart.vue     # Horizontal stacked bar: top companies (clickable)
│       │       ├── TopCompaniesTable.vue   # Top companies by blocked/allowed count (clickable)
│       │       └── RecentQueriesTable.vue  # Recent blocked/allowed queries
│       │
│       ├── utils/
│       │   └── format.ts              # Display formatting helpers (e.g. formatCategory)
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
    ├── release-prep.md                # One-time tasks before first public release
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

- View components own their data fetching — `fetch()` calls are made directly in `onMounted` and `watch` handlers within each view. This keeps data concerns local and avoids premature abstraction.
- Pinia stores hold only truly shared session state (time window, refresh signals). They do not hold fetched data.
- Type definitions in `src/types/` are kept in sync with backend Pydantic response shapes.
- Dark mode uses `useDark()` from `@vueuse/core`, which reads the system preference and persists the user's choice to localStorage.
- No pie charts. Bar charts for breakdowns, line/area charts for timelines.

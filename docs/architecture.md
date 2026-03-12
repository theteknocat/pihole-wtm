# Architecture

## System Overview

pihole-wtm is a two-tier web application: a Python/FastAPI backend that reads and enriches data, and a Vue 3 single-page application frontend that presents it. In production, an nginx reverse proxy serves the frontend static files and proxies API calls to the backend.

```text
┌─────────────────────────────────────────────────────────────────┐
│                        User's Browser                           │
│                    Vue 3 SPA (port 8080)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP /api/*
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     nginx (port 80/443)                         │
│   /api/* → proxy → backend:8000                                 │
│   /*     → serve /usr/share/nginx/html (Vue build output)       │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│              FastAPI Backend (port 8000)                         │
│                                                                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌────────────────┐   │
│  │   Routers   │───►│EnrichmentService │───►│ TrackerEnricher│   │
│  │ /stats      │    │                  │    │ (LRU cached)   │   │
│  │ /queries    │    └────────┬─────────┘    └───────┬────────┘   │
│  │ /trackers   │             │                      │            │
│  │ /settings   │             ▼                      ▼            │
│  └─────────────┘    ┌────────────────┐    ┌────────────────────┐ │
│                     │  PiholeClient  │    │  TrackerRepository │ │
│                     │  (interface)   │    │  (trackerdb.db)    │ │
│                     └───────┬────────┘    └────────────────────┘ │
│                      ┌──────┴──────┐                             │
│                      ▼             ▼                             │
│              ┌──────────────┐ ┌──────────────┐                   │
│              │SqliteClient  │ │ ApiClient    │                   │
│              │(pihole-FTL   │ │(Pi-hole HTTP │                   │
│              │  .db direct) │ │  API v5/v6)  │                   │
│              └──────────────┘ └──────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────┐      ┌──────────────────────┐
│  pihole-FTL.db       │      │  Pi-hole HTTP API    │
│  (SQLite, read-only) │      │  http://pihole/api/* │
└──────────────────────┘      └──────────────────────┘
```

## Components

### Backend (FastAPI)

**Routers** handle HTTP routing and input validation. Each router delegates to the `EnrichmentService` rather than touching data sources directly.

**EnrichmentService** is the core orchestrator. It fetches raw queries from the `PiholeClient`, enriches each domain via the `TrackerEnricher`, and assembles the final response models.

**PiholeClient** is an abstract interface with two concrete implementations:

- `SqliteClient` — opens `pihole-FTL.db` directly with `aiosqlite`. Enables arbitrary SQL, date range queries, and bulk reads without API rate limits. Used when the database file is accessible on the filesystem.
- `ApiClient` — communicates with the Pi-hole HTTP API using `httpx`. Supports Pi-hole v5 (legacy `api.php` endpoints) and v6 (REST API with session authentication). Used when Pi-hole is on a different host.

**TrackerEnricher** takes a domain string and returns tracker metadata by querying the TrackerDB. Lookups walk from the most-specific hostname match to the registered domain (eTLD+1), enabling a match even for subdomains not explicitly listed. Results are cached with an LRU cache.

**TrackerRepository** wraps `aiosqlite` reads against `trackerdb.db`. It exposes methods for domain lookup, category listing, and company aggregation.

**Background tasks** handle TrackerDB updates: on startup, the latest `trackerdb.db` is downloaded from Ghostery's GitHub releases if missing or stale. A periodic background coroutine refreshes it according to `TRACKERDB_UPDATE_INTERVAL_HOURS`.

### Frontend (Vue 3 + Vite)

**Vue Router** manages four views: Overview, Query Log, Trackers, and Settings.

**Pinia stores** hold application state: stats, query list with filters/pagination, tracker category/company data, and connection settings. Stores handle API calls and cache results in memory.

**Chart.js** (via `vue-chartjs`) powers all visualisations: the category doughnut chart, the query timeline area chart, and the top-companies bar chart.

**Tailwind CSS** provides utility-class styling.

### Data Sources

**`pihole-FTL.db`** is Pi-hole's primary SQLite database, managed by the FTL (Faster Than Light) DNS resolver. The `queries` table contains every DNS request with timestamp, domain, client, and resolution status codes.

**`trackerdb.db`** is Ghostery's TrackerDB compiled to SQLite. It contains tables for trackers, organisations, categories, and domain patterns. Released periodically on GitHub at [ghostery/trackerdb](https://github.com/ghostery/trackerdb/releases).

## Data Flow

### Query Log Request

```text
1. Browser requests GET /api/queries?limit=50&offset=0&category=advertising

2. FastAPI router validates query parameters, calls EnrichmentService

3. EnrichmentService calls PiholeClient.get_queries(limit, offset, filters)
   └─ SqliteClient: SELECT ... FROM queries WHERE ... (async, aiosqlite)
   └─ ApiClient: GET /api/queries?... (async, httpx, with session token)

4. For each RawQuery, EnrichmentService calls TrackerEnricher.enrich(domain)
   └─ LRU cache hit? Return cached TrackerInfo immediately
   └─ Cache miss: TrackerRepository.lookup(domain)
      ├─ Try exact match: SELECT ... FROM domains WHERE domain = ?
      ├─ Try eTLD+1: strip subdomains, retry
      └─ No match: return None (domain labelled "Unknown")

5. EnrichmentService assembles list[EnrichedQuery] and returns JSON response

6. Vue QueryLogView receives JSON, updates Pinia store, renders QueryTable
```

### TrackerDB Update

```text
1. FastAPI lifespan startup:
   └─ Check if trackerdb.db exists and is < TRACKERDB_UPDATE_INTERVAL_HOURS old
   └─ If stale/missing: fetch latest release from GitHub API
      └─ GET https://api.github.com/repos/ghostery/trackerdb/releases/latest
      └─ Download trackerdb.db asset
      └─ Write to temp file, rename atomically (prevents corrupt reads)
      └─ Invalidate LRU cache

2. Background coroutine sleeps for TRACKERDB_UPDATE_INTERVAL_HOURS, then repeats
```

## Pi-hole Connection Modes

The connection mode is selected at startup via the `PIHOLE_MODE` environment variable.

| Mode     | When to use                                                              | How it works                                                                                             |
| -------- | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- |
| `sqlite` | pihole-wtm on same host as Pi-hole, or Pi-hole DB mounted into container | Opens `pihole-FTL.db` directly with `aiosqlite`. Faster, richer query capability, no network dependency. |
| `api`    | Pi-hole on a different host or container                                 | Authenticates to Pi-hole's REST API, polls endpoints. Works over any network.                            |

Auto-detection is planned: the backend will attempt SQLite access first and fall back to the API if the file is not accessible.

## Caching Strategy

**TrackerDB domain lookups** are cached with an in-process LRU cache (50,000 entries). Pi-hole query logs have a long-tailed domain distribution — the top few hundred domains account for the majority of queries. A large LRU cache means most per-query enrichment calls are O(1) dictionary lookups.

The cache is invalidated when TrackerDB is updated on disk.

**API responses** are not cached at the HTTP layer by default. The frontend Pinia stores hold the last-fetched data in memory and re-fetch on a configurable interval (default 30 seconds for the Overview summary).

## Security Considerations

- The Pi-hole database is opened **read-only**. No writes are ever made to Pi-hole's data.
- The Pi-hole API password is stored only in the environment/config; it is never logged and never returned by the pihole-wtm API.
- `TRACKERDB_PATH` is validated to prevent path traversal.
- TrackerDB downloads are verified against the GitHub release asset (not arbitrary URLs).
- nginx sets appropriate Content Security Policy headers.

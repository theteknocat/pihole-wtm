# Architecture

## System Overview

pihole-wtm is a two-tier web application: a Python/FastAPI backend that syncs, stores, and enriches data, and a Vue 3 single-page application frontend that presents it. In production, an nginx reverse proxy serves the frontend static files and proxies API calls to the backend.

```text
┌─────────────────────────────────────────────────────────────────┐
│                        User's Browser                           │
│                       Vue 3 SPA                                 │
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
│                  FastAPI Backend (port 8000)                     │
│                                                                  │
│  ┌─────────────┐                                                 │
│  │   Routers   │──────────────────────────────┐                  │
│  │ /stats      │                              │                  │
│  │ /queries    │                              │                  │
│  │ /config     │                              ▼                  │
│  │ /debug      │         ┌────────────────────────────────────┐  │
│  └─────────────┘         │     Local SQLite (pihole-wtm.db)   │  │
│                          │                                    │  │
│  ┌─────────────┐         │  ┌──────────┐  ┌──────────────┐    │  │
│  │Sync Service │────────►│  │ queries  │  │   domains    │    │  │
│  │(background) │         │  └──────────┘  └──────────────┘    │  │
│  └──────┬──────┘         │  ┌──────────┐  ┌─────────────┐     │  │
│         │                │  │sync_state│  │ user_config │     │  │
│         │ enrich         │  └──────────┘  └─────────────┘     │  │
│         ▼                └────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────┐                │
│  │             Enrichment Pipeline              │                │
│  │  1. TrackerDB (primary, in-memory cached)    │                │
│  │  2. Disconnect.me (secondary, in-memory)     │                │
│  │  3. eTLD+1 heuristic (company + category)    │                │
│  │  4. RDAP (background upgrade, periodic)      │                │
│  └──────────────────────────────────────────────┘                │
└──────────┬───────────────────────────────────────────────────────┘
           │ periodic sync (~60s)
           ▼
┌──────────────────────────┐
│   Pi-hole HTTP API v6    │
│   http://pihole/api/*    │
└──────────────────────────┘
```

## Components

### Backend (FastAPI)

**Routers** handle HTTP routing and input validation. They read exclusively from the local SQLite database — they never call the Pi-hole API directly.

**Sync Service** is a background asyncio coroutine that runs on a configurable interval (default 60 seconds). It fetches new queries from Pi-hole using cursor-based pagination (tracking the highest query ID seen), applies the enrichment pipeline, and writes results to the local database. The Pi-hole API is only used by this service.

**Local SQLite database (`pihole-wtm.db`)** is the single source of truth for the dashboard. It holds four tables:

- `queries` — filtered Pi-hole query history with Pi-hole fields captured at sync time
- `domains` — one row per unique domain, holding all enrichment results across sources
- `sync_state` — single-row cursor tracking the last synced Pi-hole query ID
- `user_config` — key-value store for user preferences (excluded categories, companies, domains)

**Enrichment Pipeline** processes each newly discovered domain after it is first stored. It iterates over configured tracker sources in priority order, writing the best available result to the `domains` table. Enrichment runs in the background and never blocks API responses. A `needs_reenrichment` flag on the `domains` table allows background re-processing when new sources are added.

**TrackerSource protocol** defines the common interface for all tracker data sources. Each source implements `lookup_exact()` (for storage gating), `enrich()` (for display enrichment with optional fallback strategies), `initialize()`, `refresh_if_stale()`, and `api_router()` (for optional debug endpoints). Sources self-describe their capabilities via `gates` (whether they participate in allowed-query gating), `priority` (lower = tried first), and `label` (human-friendly display name). A `get_tracker_sources()` registration function instantiates all configured sources.

**TrackerDBSource** (Ghostery's `trackerdb.db`) is the primary source. It manages its own lifecycle: downloading the SQLite file from GitHub Releases on startup, validating the schema, and refreshing when stale. It exposes two lookup strategies — `lookup_exact()` (direct DB hit, no fallback) and `enrich()` (subdomain fallback + 50k-entry LRU cache). It also registers debug API routes at `/api/sources/trackerdb/`.

**DisconnectSource** (Disconnect.me `services.json`) is the secondary source. Data is downloaded and parsed into an in-memory dict on startup. All lookups are exact-match only — Disconnect.me lists root domains of companies that operate ad networks, so subdomain fallback would incorrectly flag legitimate services. Debug routes registered at `/api/sources/disconnect/`.

### Frontend (Vue 3 + Vite)

**Vue Router** manages views: Overview (system health with per-source status indicators), Dashboard (tracker charts and summary tables), and Domain Report (per-domain drill-down, navigated to from chart bars and company table rows).

**Pinia stores** hold shared session state. The `window` store tracks the active time window (24h/7d) and a `refreshKey` counter used to signal cross-component data refreshes — for example, causing all visible reports to reload after a data reset from the settings sidebar.

**PrimeVue** (Aura theme) provides the component library — cards, tables, buttons, and the Chart component which wraps Chart.js for bar charts.

**Chart.js** is used via PrimeVue's Chart component for bar chart visualisations (companies by query share, categories by query share). No pie or doughnut charts. Chart configuration is shared via the `useTrackerBarChart` composable, which provides dark-mode-aware datasets, tooltip formatting, and scale options.

**Tailwind CSS** provides utility-class layout and spacing. Tailwind's dark mode uses the `class` strategy, toggled by `@vueuse/core`'s `useDark()` which defaults to the system preference and persists the user's choice to localStorage.

### Data Sources

**`trackerdb.db`** is Ghostery's TrackerDB compiled to SQLite. It contains tables for trackers, organisations, categories, and domain patterns. Released periodically on GitHub at [ghostery/trackerdb](https://github.com/ghostery/trackerdb/releases). Managed by `TrackerDBSource`.

**Disconnect.me tracking protection lists** — categorised domain lists covering Advertising, Analytics, Social, Content, and Cryptomining. Loaded into memory on startup and refreshed when stale (configurable via `DISCONNECT_UPDATE_INTERVAL_HOURS`). Managed by `DisconnectSource`. Used as a secondary enrichment source for domains not in TrackerDB.

**eTLD+1 heuristic** — a lightweight fallback for domains not matched by TrackerDB or Disconnect.me. Extracts a company name from the registered domain label and infers a tracker category from well-known subdomain keywords (e.g. `telemetry.*` → "telemetry", `analytics.*` → "analytics"). Less reliable than a curated database but meaningfully better than showing nothing.

**RDAP** — Registration Data Access Protocol lookups provide registrant organisation names for domains enriched only via the heuristic. Lookups run as a periodic background upgrade pass (every ~10 sync cycles), with a 0.5s delay per domain to stay within rate limits. Results are cached in-memory per registered domain. The parser flattens nested RDAP entities (registrant inside registrar), skips non-owner roles (registrar, technical, abuse, etc.), and filters out WHOIS privacy proxy names. Domains where RDAP returns no usable name are marked `rdap_failed` to prevent repeated retries. Existing heuristic-derived category and company name are preserved when RDAP upgrades a domain.

## Data Flow

### Sync Cycle (background, every ~60s)

```text
1. SyncService reads last_query_id from sync_state table

2. Fetch new queries from Pi-hole:
   GET /api/queries?cursor=<last_query_id>&length=100
   Repeat with cursor = batch[-1].id until no new results

3. For each new query:
   a. If status is BLOCKED → always store
   b. If status is ALLOWED → exact-match gate (no subdomain fallback):
      - Domain exactly matches TrackerDB or Disconnect.me? → store (known tracker allowed through)
      - Otherwise → discard (legitimate traffic, not relevant to this dashboard)
      Exact-match is intentional: subdomain fallback would incorrectly flag legitimate services
      (mail.google.com, calendar.google.com) because their parent company (google.com) appears
      in tracker databases as an advertising entity.

4. Upsert domain into domains table if not already present

5. Run enrichment pipeline to populate display metadata (category, company, tracker name):
   a. Blocked queries: iterate sources in priority order using enrich() (includes subdomain
      fallback for TrackerDB, exact-match for Disconnect.me)
   b. Allowed queries: reuse the exact-match gating result directly (no second lookup)
   c. eTLD+1 heuristic — company name from registered domain, category from subdomain keywords
      (if all configured sources missed)
   Write category, company_name, tracker_name, enrichment_source to domains table

   A separate periodic background pass (every ~10 sync cycles) upgrades heuristic-enriched
   domains with registrant names from RDAP, one domain at a time with a 0.5s delay.
   Domains where RDAP returns no usable name are marked `rdap_failed` so they are not
   retried on subsequent cycles.

6. Insert filtered queries into queries table

7. Update sync_state.last_query_id = highest ID processed
```

### API Request (dashboard load)

```text
1. Browser requests GET /api/stats/trackers?hours=24

2. FastAPI router queries local SQLite:
   SELECT domain, category, company_name, status, COUNT(*)
   FROM queries JOIN domains USING (domain)
   WHERE timestamp > now - 86400
   GROUP BY company_name, category

3. Returns pre-enriched aggregated result — no Pi-hole API call, no inline enrichment
```

### Source Lifecycle

```text
1. FastAPI lifespan startup:
   └─ get_tracker_sources() instantiates all sources, sorted by priority
   └─ For each source: await source.initialize()
      ├─ TrackerDBSource: check if trackerdb.db exists and is fresh
      │  └─ If stale/missing: GET GitHub Releases API → download → validate schema → atomic rename
      └─ DisconnectSource: download and parse services.json into memory

2. Each sync cycle: await source.refresh_if_stale() for each source
   ├─ TrackerDBSource: re-downloads if file mtime exceeds TRACKERDB_UPDATE_INTERVAL_HOURS;
   │  clears LRU cache only if the file actually changed
   └─ DisconnectSource: re-downloads if loaded_at exceeds DISCONNECT_UPDATE_INTERVAL_HOURS

3. Each source optionally registers debug routes via api_router():
   └─ /api/sources/{source_name}/status, /api/sources/{source_name}/lookup
```

## Database Schema

### Migrations

Schema changes are managed by a lightweight version-stamped migration system in `database.py`. There is no external migration tool — the backend handles it on startup.

- A `schema_version` table tracks the current version (single row, integer).
- Migrations are defined as an ordered list of `(version, description, sql)` tuples in `_MIGRATIONS`.
- On startup, `LocalDatabase.init()` checks the current version and applies any pending migrations in order, committing after each one.
- Migrations are forward-only (no down migrations). If an upgrade fails, the user resets the database.
- All DDL uses `IF NOT EXISTS` / `IF EXISTS` so migrations are idempotent.
- Migration 1 is the initial schema — there is no separate bootstrap path. A fresh database starts at version 0 and applies all migrations from the beginning.

To add a new migration: append a tuple to `_MIGRATIONS` with the next version number. Never modify existing entries.

### Tables

```sql
-- Schema version tracking (single row).
CREATE TABLE schema_version (
    id      INTEGER PRIMARY KEY DEFAULT 1,
    version INTEGER NOT NULL
);

-- One row per unique domain encountered.
-- All enrichment data lives here, not on query rows.
CREATE TABLE domains (
    domain              TEXT PRIMARY KEY,
    tracker_name        TEXT,
    category            TEXT,
    company_name        TEXT,
    company_country     TEXT,
    enrichment_source   TEXT,    -- 'trackerdb', 'disconnect', 'rdap', 'rdap_failed', 'heuristic'
    enriched_at         REAL,
    needs_reenrichment  INTEGER DEFAULT 0
);

-- Filtered Pi-hole query history.
-- Only blocked queries and allowed queries matching a known tracker/malware source.
CREATE TABLE queries (
    id          INTEGER PRIMARY KEY,  -- Pi-hole's own query ID
    timestamp   REAL NOT NULL,
    domain      TEXT NOT NULL REFERENCES domains(domain),
    client_ip   TEXT,
    client_name TEXT,
    status      TEXT NOT NULL,
    query_type  TEXT,
    reply_type  TEXT,
    reply_time  REAL,
    upstream    TEXT,
    list_id     INTEGER
);

-- Single-row sync cursor.
CREATE TABLE sync_state (
    id              INTEGER PRIMARY KEY DEFAULT 1,
    last_query_id   INTEGER NOT NULL DEFAULT 0,
    last_synced_at  REAL
);

-- User configuration (key-value store).
-- Stores tracker source exclusion settings (excluded_categories, excluded_companies,
-- excluded_domains) as JSON arrays. Kept in the same database so config survives
-- container restarts alongside data.
CREATE TABLE user_config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE INDEX idx_queries_timestamp ON queries(timestamp);
CREATE INDEX idx_queries_status    ON queries(status);
CREATE INDEX idx_queries_domain    ON queries(domain);
CREATE INDEX idx_queries_client    ON queries(client_ip);
CREATE INDEX idx_domains_category  ON domains(category);
CREATE INDEX idx_domains_company   ON domains(company_name);
```

## Caching Strategy

**TrackerDB domain lookups** are cached with an in-process LRU cache (50,000 entries). Pi-hole query logs have a long-tailed domain distribution — the top few hundred domains account for the majority of queries. The cache is invalidated when TrackerDB is updated on disk.

**Local SQLite** is the primary cache for enriched query data. Because the sync service pre-enriches all stored queries, API requests read pre-computed data with no inline enrichment overhead.

**API responses** are not cached at the HTTP layer. The frontend Pinia stores hold the last-fetched data in memory.

## Pi-hole Compatibility

pihole-wtm targets **Pi-hole v6** exclusively. Pi-hole v6 uses a REST API with session-based authentication (`POST /api/auth` → `X-FTL-SID` header). Pi-hole v5 is not supported.

## Security Considerations

- The Pi-hole API password is stored only in the environment/config; it is never logged and never returned by the pihole-wtm API.
- `TRACKERDB_PATH` and `LOCAL_DB_PATH` are validated to prevent path traversal.
- TrackerDB downloads are verified against the GitHub release asset (not arbitrary URLs).
- nginx sets appropriate Content Security Policy headers.
- The local SQLite database is read-write only by the backend process; it is never exposed directly.

# CLAUDE.md — pihole-wtm

Project-level instructions for Claude Code. These apply to every conversation in this repository.

---

## Project Overview

**Stack**: FastAPI (Python 3.12, aiosqlite/SQLite) + Vue 3 (TypeScript, PrimeVue, Pinia, Vite). Dev environment runs via ddev.

**What it does**: Syncs Pi-hole DNS query history, enriches domains with tracker intelligence (Ghostery TrackerDB, Disconnect.me, RDAP), and serves a dashboard.

---

## Key File Locations

| Concern                     | Path                               |
| --------------------------- | ---------------------------------- |
| All API routes              | `backend/app/main.py`              |
| Database queries            | `backend/app/services/database.py` |
| API TypeScript types        | `frontend/src/types/api.ts`        |
| Report views                | `frontend/src/views/`              |
| Dialogs / layout components | `frontend/src/components/layout/`  |
| Shared composables          | `frontend/src/composables/`        |
| Pinia stores                | `frontend/src/stores/`             |
| Backend tests               | `backend/tests/`                   |
| Frontend tests              | `frontend/src/tests/`              |

---

## Architecture Patterns

**Adding a new stat/data type**: DB method in `database.py` → route in `main.py` → TS interface in `api.ts`.

**Adding a new dialog**: follow the `DeviceStatsDialog` / `DomainClientsDialog` pattern — `visible = ref(true)`, emits `close` on hide, mounted with `v-if` in parent view.

**Report filters**: `useReportData` composable owns filter state, URL query param sync, and data fetching for both domain and client report views.

**Time window**: always use `useWindowStore().queryParams({...})` to build API query strings so the active time window is included.

**Exclusions**: every new stats DB method must call `await this._apply_exclusions(conditions, params)` so user exclusion settings are respected.

---

## Python Linting Notes

When suppressing a ruff rule across multiple lines (e.g. a multi-line f-string), use block-level comments — `# ruff: disable[RULE]` on the line before and `# ruff: enable[RULE]` after. Do not use `# noqa: RULE` on the opening line of a multi-line construct — it becomes part of the string content, not a comment.

---

## Dev Commands

Full details in `docs/development.md`. All commands run via ddev; Python tools require the `.venv/bin/` prefix.

```bash
# Linting + type checking
ddev exec -d /var/www/html/backend .venv/bin/ruff check app tests
ddev exec -d /var/www/html/backend .venv/bin/mypy app
ddev exec -d /var/www/html/frontend npm run lint
ddev exec -d /var/www/html/frontend npm run type-check

# Tests
ddev exec -d /var/www/html/backend .venv/bin/pytest
ddev exec -d /var/www/html/frontend npm run test
```

---

## Commits

Uses Conventional Commits. `feat:` → minor bump, `fix:` → patch bump, `chore:`/`refactor:`/`test:` → no changelog entry. Release Please batches all commits into one release PR — multiple `feat:` commits don't cause multiple version bumps.

---

## CI / CD Workflows

**CI** (`.github/workflows/ci.yml`): runs on every push (except release-please branches) and on PRs. Runs backend (ruff, mypy, pytest) and frontend (eslint, vue-tsc, vitest) checks in parallel.

**Release Please** (`.github/workflows/release-please.yml`): runs on every push to master. Opens/updates a release PR on every push, but only `feat:` and `fix:` commits appear in the changelog and affect the version bump. When the PR is merged, creates a GitHub release and publishes it automatically.

**Release** (`.github/workflows/release.yml`): triggers on `release published` (i.e. automatically when the Release Please PR is merged) and on `workflow_dispatch`. Builds and pushes the multi-arch Docker image (`linux/amd64`, `linux/arm64`, `linux/arm/v7`) to GHCR. The frontend build stage runs pinned to `linux/amd64` to avoid QEMU hangs — the static output is platform-agnostic.

---

## Code Review Workflow

After completing a significant feature or refactor, suggest a code review of the files touched. When reviewing: read files thoroughly first, flag findings by severity (🔴 Must Fix / 🟡 Should Fix / 🟢 Minor), and add any deferred 🟢 items to [`docs/tech-debt.md`](docs/tech-debt.md) so they aren't lost.

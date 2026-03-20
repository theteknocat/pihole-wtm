# Release Prep — v1.0

Tasks to complete before cutting the first public release. These are one-time cleanup items that only make sense while there are no external users with existing databases or deployments.

---

## Database

### Collapse migrations into a single initial schema

The current migration history (3 migrations) includes a `DROP COLUMN client_name` in migration 3 that removes a column added in migration 1. Since no external users have databases to migrate, all three migrations can be collapsed into a single clean initial schema that creates the tables correctly from the start:

- `queries` without `client_name`
- `client_names` table included from the beginning
- `user_config` table included from the beginning

This eliminates the `DROP COLUMN` (which has no `IF EXISTS` in SQLite) and simplifies the migration history for anyone reading the code.

**When to do this:** Just before the first tagged release. After this point, all schema changes must be proper incremental migrations.

---

## Documentation

- [ ] All `docs/` pages reviewed and up to date
- [ ] README deployment guide covering:
  - Docker Compose setup (standard Linux/Mac)
  - QNAP Container Station specific instructions
  - General guidance for other container managers (env vars, volumes, networking)
- [ ] Screenshots in README showing dashboard, timeline, and detailed report views
- [ ] API reference generated from FastAPI OpenAPI spec
- [ ] `CONTRIBUTING.md` with code style guide and PR process
- [ ] `CHANGELOG.md` initialised

---

## Infrastructure

- [x] `docker-compose.yml` for production deployment
- [x] `Dockerfile` — multi-stage build (frontend + backend + nginx)
- [x] `docker/nginx.conf` — SPA routing + `/api` proxy
- [x] `.env.example` with documented defaults
- [ ] Multi-arch Docker image builds (`linux/amd64` + `linux/arm64`)
- [ ] GitHub Actions CI: lint + type-check + test

---

## Code Quality

- [ ] Run `ruff check backend/` with `B` and `S` rules and resolve findings
- [ ] Address all items in `docs/tech-debt.md`
- [ ] Backend test coverage for API endpoints and sync service
- [ ] Frontend tests for Pinia store logic and key components

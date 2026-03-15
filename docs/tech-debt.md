# Tech Debt & Deferred Fixes

Minor items identified during code review that are worth addressing before release but not urgent.

---

## Backend

### `api_client.py` — `test_connection` bypasses the auth lock

`test_connection()` calls `_authenticate()` directly instead of going through `_get()`, so it doesn't acquire `_auth_lock`. This means a concurrent call to `test_connection()` and a regular request could both trigger authentication simultaneously.

Low risk in practice (the test endpoint is rarely called), but should be fixed when the auth layer is refactored as part of the planned per-session `PiholeApiClient` work.

### `api_client.py` — `self._sid` type after auth lock may cause mypy warnings

`self._sid` is typed as `str | None` but is used as `str` immediately after the auth lock block. Mypy strict mode may flag this since it can't infer that `_authenticate()` guarantees a non-None value. Fix with an assertion or local variable after the lock.

### `types/api.ts` — missing new fields on `EnrichedQuery`

The frontend `EnrichedQuery` interface is missing `client_name`, `upstream`, and `list_id` fields added in the sync database refactor. These are returned by the API but not typed on the frontend.

---

## Frontend

### Chart options duplicated across `CategoryBarChart` and `CompanyBarChart`

Both components contain identical logic for computing `textColor`, `gridColor`, the tooltip callback, and scale/legend config. Extract to a `useChartOptions(totalTrackerQueries)` composable to keep it in one place.

### `RecentQueriesTable` — `type` prop unused in template

The `type: 'allowed' | 'blocked'` prop is declared but not used for any visual differentiation. Either colour-code the rows/cells based on type (e.g. a coloured left border or status badge) or remove the prop if it turns out to not be needed.

### `OverviewView` — non-2xx response from `/api/pihole/test` shows no error detail

If the backend returns a 503, `res.json()` parses `{"detail": "..."}` as the pihole object. `pihole.connected` is `undefined` so the UI correctly shows "disconnected", but the backend error message is never displayed. Add a `res.ok` check and surface the `detail` field.

---

## Tooling

### Add ruff `B` and `S` rules to CI enforcement

`B` (flake8-bugbear) and `S` (bandit/security) are now selected in `pyproject.toml` but have not been run against the full codebase yet. Run `ruff check` inside ddev and resolve any new findings before the first release.

```bash
ruff check backend/
```

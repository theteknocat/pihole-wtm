# Tech Debt & Deferred Fixes

Minor items identified during code review that are worth addressing before release but not urgent.

---

## Backend

### `api_client.py` — `test_connection` bypasses the auth lock

`test_connection()` calls `_authenticate()` directly instead of going through `_get()`, so it doesn't acquire `_auth_lock`. This means a concurrent call to `test_connection()` and a regular request could both trigger authentication simultaneously.

Low risk in practice (the test endpoint is rarely called), but should be fixed when the auth layer is refactored as part of the planned per-session `PiholeApiClient` work.

### `api_client.py` — `self._sid` type after auth lock may cause mypy warnings

`self._sid` is typed as `str | None` but is used as `str` immediately after the auth lock block. Mypy strict mode may flag this since it can't infer that `_authenticate()` guarantees a non-None value. Fix with an assertion or local variable after the lock.

### `stats.py` — `category_total()` computed twice per category

The `category_total()` helper is called once in the sort key and once when building the response dict, doing the same sum twice. Could precompute into a dict before sorting. Not a performance concern at current scale.

### `main.py` — `EnrichedQuery` model round-trip in `/api/queries`

`EnrichedQuery(**q.model_dump(), ...)` constructs a Pydantic model only to immediately call `model_dump()` on it. Could be replaced with a plain dict construction to skip the unnecessary validation round-trip.

---

## Performance

### `stats.py` — `/api/stats/trackers` has no caching

Every request paginates through the full query window and enriches all domains. For a 24h window this can take several seconds. A short TTL cache (e.g. 5 minutes) on the aggregated result would make the endpoint suitable for dashboard use. Consider `cachetools.TTLCache` keyed on `hours`.

---

## Tooling

### Add ruff `B` and `S` rules to CI enforcement

`B` (flake8-bugbear) and `S` (bandit/security) are now selected in `pyproject.toml` but have not been run against the full codebase yet. Run `ruff check` inside ddev and resolve any new findings before the first release.

```bash
ruff check backend/
```

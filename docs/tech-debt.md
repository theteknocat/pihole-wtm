# Tech Debt & Deferred Fixes

Minor items identified during code review that are worth addressing before release but not urgent.

---

## Backend

### `api_client.py` — `test_connection` bypasses the auth lock

`test_connection()` calls `_authenticate()` directly instead of going through `_get()`, so it doesn't acquire `_auth_lock`. This means a concurrent call to `test_connection()` and a regular request could both trigger authentication simultaneously.

Low risk in practice (the test endpoint is rarely called), but should be fixed when the auth layer is refactored as part of the planned per-session `PiholeApiClient` work.

---

## Tooling

### Add ruff `B` and `S` rules to CI enforcement

`B` (flake8-bugbear) and `S` (bandit/security) are now selected in `pyproject.toml` but have not been run against the full codebase yet. Run `ruff check` inside ddev and resolve any new findings before the first release.

```bash
ruff check backend/
```

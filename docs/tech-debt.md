# Tech Debt & Deferred Fixes

Minor items identified during code review that are worth addressing before release but not urgent.

---

## Frontend

### `RecentQueriesTable` — `type` prop unused in template

The `type: 'allowed' | 'blocked'` prop is declared but not used for any visual differentiation. Either colour-code the rows/cells based on type (e.g. a coloured left border or status badge) or remove the prop if it turns out to not be needed.

## Tooling

### Add ruff `B` and `S` rules to CI enforcement

`B` (flake8-bugbear) and `S` (bandit/security) are now selected in `pyproject.toml` but have not been run against the full codebase yet. Run `ruff check` inside ddev and resolve any new findings before the first release.

```bash
ruff check backend/
```

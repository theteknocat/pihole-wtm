# Tech Debt & Deferred Fixes

Minor items identified during code review that are worth addressing before release but not urgent.

---

## Tooling

### Add ruff `B` and `S` rules to CI enforcement

`B` (flake8-bugbear) and `S` (bandit/security) are now selected in `pyproject.toml` but have not been run against the full codebase yet. Run `ruff check` inside ddev and resolve any new findings before the first release.

```bash
ruff check backend/
```

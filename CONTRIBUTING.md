# Contributing to pihole-wtm

## How to Contribute

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Create a branch** for your change (`git checkout -b feat/my-feature`)
4. Make your changes, following the code standards below
5. **Push** to your fork and open a **Pull Request** against `master`

Please open an issue first for significant changes so the approach can be discussed before you invest time in implementation.

## Development Setup

See [docs/development.md](docs/development.md) for full setup instructions. The short version:

```bash
git clone https://github.com/theteknocat/pihole-wtm.git
cd pihole-wtm
npm install   # installs git hooks
ddev start
```

## Commit Messages

This project enforces [Conventional Commits](https://www.conventionalcommits.org/). A git hook will reject any commit that doesn't match the format. The `npm install` step above installs the hook automatically.

### Format

```text
type(scope)?: description
```

### Types

| Type       | When to use                                      |
| ---------- | ------------------------------------------------ |
| `feat`     | A new feature                                    |
| `fix`      | A bug fix                                        |
| `chore`    | Maintenance, dependencies, tooling               |
| `docs`     | Documentation changes only                       |
| `refactor` | Code restructuring with no behaviour change      |
| `test`     | Adding or updating tests                         |
| `perf`     | Performance improvements                         |
| `ci`       | CI/CD workflow changes                           |
| `style`    | Formatting, whitespace (no logic change)         |
| `revert`   | Reverting a previous commit                      |

### Examples

```text
feat: add dark mode toggle
fix(auth): handle expired sessions correctly
chore: update Python dependencies
docs: add deployment guide for bare-metal
feat!: redesign API response format  ← breaking change, bumps major version
```

Breaking changes use `!` after the type and trigger a major version bump when merged to master.

## Pull Requests

- Keep PRs focused — one feature or fix per PR
- All CI checks must pass before merging (lint, type-check, tests)
- Use a conventional commit message for the PR title — release-please uses it for the changelog

## Code Standards

### Backend (Python)

- Linter: **ruff** — run `ddev exec -d /var/www/html/backend .venv/bin/ruff check app tests`
- Type checker: **mypy** (strict mode) — run `ddev exec -d /var/www/html/backend .venv/bin/mypy app`
- All new code must pass both without errors

### Frontend (TypeScript / Vue)

- Linter: **ESLint** — run `ddev exec -d /var/www/html/frontend npm run lint`
- Type checker: **vue-tsc** — run `ddev exec -d /var/www/html/frontend npm run type-check`
- Tests: **Vitest** — run `ddev exec -d /var/www/html/frontend npm test`

### Tests

- Backend: add tests for any new API endpoints or service logic
- Frontend: add composable tests for new data-fetching or state logic
- CI runs all checks on every push — fix failures before requesting review

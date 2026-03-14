# CLAUDE.md — pihole-wtm

Project-level instructions for Claude Code. These apply to every conversation in this repository.

---

## Code Review Workflow

After completing a significant chunk of work — such as finishing a new feature, a set of related endpoints, or a major refactor — suggest doing a code review of the files touched. Don't do this after every small edit; use judgement to identify natural milestones (e.g. "we've just built out the full query enrichment pipeline — good time for a review?").

When doing a review:

1. Read all relevant files thoroughly before forming opinions
2. Categorise findings by severity:
   - 🔴 Must Fix — correctness bugs, security issues, broken behaviour
   - 🟡 Should Fix — code quality, typing, error handling, best practice
   - 🟢 Minor — style, nice-to-haves, low-priority improvements
3. Apply all 🔴 and 🟡 fixes immediately (with user approval)
4. For 🟢 items: apply the ones that are clearly beneficial and low-risk; add the rest to [`docs/tech-debt.md`](docs/tech-debt.md) so they aren't lost

# pihole-wtm

A standalone dashboard that brings tracker intelligence to your Pi-hole.

> **Status: Active Development** — The core MVP is functional. Pi-hole query syncing, multi-source tracker enrichment, and the dashboard are working. Production deployment (Docker, nginx) is not yet ready.

## What It Does

Pi-hole tells you *that* a domain was blocked. pihole-wtm tells you *why it matters* — enriching your DNS query history with tracker intelligence so you can see at a glance that a blocked domain was an advertising tracker operated by a major ad network, or an analytics beacon embedded across thousands of sites.

Enrichment draws from multiple sources: [Ghostery TrackerDB](https://github.com/ghostery/trackerdb) and [Disconnect.me](https://github.com/disconnectme/disconnect-tracking-protection) for curated tracker data, RDAP for registered company names, and a subdomain keyword heuristic as a last-resort fallback. Most domains end up with a category and company name even if they're not in any tracker database. RDAP lookups filter out WHOIS privacy proxies and skip non-owner entities so only genuine registrant names are used.

The dashboard sits alongside your existing Pi-hole installation without modifying it. It syncs query data from the Pi-hole v6 API into a local database, enriches it, and serves all results from its own store — so the dashboard is fast and Pi-hole is never under load when you're browsing. Users can configure which tracker categories, companies, and individual domains to exclude from dashboard views.

## What It Hopes to Become

- A polished, self-hosted dashboard installable as a Docker container or directly on a Pi-hole host
- ~~A breakdown of blocked queries by tracker category (advertising, analytics, fingerprinting, CDN, etc.)~~ ✓
- ~~A company-level view — which organisations' trackers appear most often in your query log~~ ✓
- ~~Deep-drill filtering: click a category to see the queries, click a company to see its domains~~ ✓
- ~~Historical timelines showing how your tracker exposure changes over time~~ ✓
- Multi-arch Docker images for Raspberry Pi and x86 hosts
- A zero-configuration "just works" experience when run on the same machine as Pi-hole

## Tech Stack

| Layer           | Technology                                                                                                                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend         | Python 3.12 + FastAPI (async)                                                                                                                        |
| Frontend        | Vue 3 + Vite (TypeScript)                                                                                                                            |
| Tracker data    | [Ghostery TrackerDB](https://github.com/ghostery/trackerdb) · [Disconnect.me](https://github.com/disconnectme/disconnect-tracking-protection) · RDAP |
| Pi-hole data    | Pi-hole v6 HTTP API                                                                                                                                  |
| Dev environment | [ddev](https://ddev.com/)                                                                                                                            |
| Production      | Docker Compose                                                                                                                                       |

## Documentation

See the [`docs/`](docs/) directory for detailed planning documents:

- [Overview & Vision](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Project Structure](docs/project-structure.md)
- [Development Setup](docs/development.md)
- [Configuration Reference](docs/configuration.md)
- [Deployment Guide](docs/deployment.md)
- [Roadmap](docs/roadmap.md)
- [Tracker Categories](docs/tracker-categories.md)
- [Authentication](docs/authentication.md)

## License

To be determined. Tracker data is provided by Ghostery TrackerDB under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

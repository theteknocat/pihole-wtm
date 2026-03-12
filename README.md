# pihole-wtm

A standalone dashboard that brings tracker intelligence to your Pi-hole.

> **Status: Early Development** — This project is in the planning and scaffolding phase. No stable release yet.

## What It Does

Pi-hole tells you *that* a domain was blocked. pihole-wtm tells you *why it matters* — by enriching your DNS query history with tracker intelligence from the [Ghostery TrackerDB](https://github.com/ghostery/trackerdb). You can see at a glance that the domain blocked was an advertising tracker operated by a major ad network, or a fingerprinting script embedded on thousands of sites.

The dashboard sits alongside your existing Pi-hole installation without modifying it. It reads Pi-hole data either directly from the SQLite database (when running on the same host) or via the Pi-hole HTTP API (when running remotely or in a separate container).

## What It Hopes to Become

- A polished, self-hosted dashboard installable as a Docker container or directly on a Pi-hole host
- A breakdown of blocked queries by tracker category (advertising, analytics, fingerprinting, CDN, etc.)
- A company-level view — which organisations' trackers appear most often in your query log
- Historical timelines showing how your tracker exposure changes over time
- Deep-drill filtering: click a category to see the queries, click a company to see its domains
- Multi-arch Docker images for Raspberry Pi and x86 hosts
- A zero-configuration "just works" experience when run on the same machine as Pi-hole

## Tech Stack

| Layer           | Technology                                                                      |
| --------------- | ------------------------------------------------------------------------------- |
| Backend         | Python 3.12 + FastAPI (async)                                                   |
| Frontend        | Vue 3 + Vite (TypeScript)                                                       |
| Tracker data    | [Ghostery TrackerDB](https://github.com/ghostery/trackerdb) (SQLite, CC-BY-4.0) |
| Pi-hole data    | Direct SQLite DB access or Pi-hole HTTP API (v5/v6)                             |
| Dev environment | [ddev](https://ddev.com/)                                                       |
| Production      | Docker Compose                                                                  |

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

## License

To be determined. Tracker data is provided by Ghostery TrackerDB under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

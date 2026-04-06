# pihole-wtm

A standalone dashboard that brings tracker intelligence to your Pi-hole.

> **Requires Pi-hole v6.** pihole-wtm connects to the Pi-hole v6 REST API and is not compatible with Pi-hole v5.

## What It Does

Pi-hole tells you *that* a domain was blocked. pihole-wtm tells you *why it matters* — enriching your DNS query history with tracker intelligence so you can see at a glance that a blocked domain was an advertising tracker operated by a major ad network, or an analytics beacon embedded across thousands of sites.

Enrichment draws from multiple sources: [Ghostery TrackerDB](https://github.com/ghostery/trackerdb) and [Disconnect.me](https://github.com/disconnectme/disconnect-tracking-protection) for curated tracker data, RDAP and WHOIS for registered company names, and a subdomain keyword heuristic as a last-resort fallback. Most domains end up with a category and company name even if they're not in any tracker database. RDAP is tried first; if it returns no registrant data, a WHOIS fallback is attempted. Both paths filter out privacy proxy names so only genuine registrant names are used.

The dashboard sits alongside your existing Pi-hole installation without modifying it. It syncs query data from the Pi-hole v6 API into a local database, enriches it, and serves all results from its own store — so the dashboard is fast and Pi-hole is never under load when you're browsing. Users can configure which tracker categories, companies, and individual domains to exclude from dashboard views.

## Quick Start

```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/theteknocat/pihole-wtm/master/docker-compose.yml
docker compose up -d
```

Open `http://your-host` in your browser. Enter your Pi-hole URL and password on the login page.

For full configuration options see the [Deployment Guide](docs/deployment.md).

## Tech Stack

| Layer           | Technology                                                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Backend         | Python 3.12 + FastAPI (async)                                                                                                                                |
| Frontend        | Vue 3 + Vite (TypeScript)                                                                                                                                    |
| Tracker data    | [Ghostery TrackerDB](https://github.com/ghostery/trackerdb) · [Disconnect.me](https://github.com/disconnectme/disconnect-tracking-protection) · RDAP · WHOIS |
| Pi-hole data    | Pi-hole v6 HTTP API                                                                                                                                          |
| Deployment      | Docker Compose · multi-arch (amd64 + arm64)                                                                                                                  |
| Dev environment | [ddev](https://ddev.com/)                                                                                                                                    |

## Documentation

See the [`docs/`](docs/) directory for detailed documentation:

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

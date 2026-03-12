# Overview

## The Problem

Pi-hole is excellent at blocking trackers, ads, and malicious domains at the DNS level. Its dashboard gives you counts — total queries, blocked percentage, top blocked domains. What it doesn't tell you is *what kind* of surveillance infrastructure you're blocking, or *who* is behind it.

A blocked domain like `px.ads.linkedin.com` is just a string. Without context, you don't know that it's an advertising tracker operated by LinkedIn (Microsoft), that it appears on a significant fraction of the web, or that it falls into the "advertising" category of trackers.

## The Solution

pihole-wtm enriches your Pi-hole query history with tracker intelligence from [Ghostery's TrackerDB](https://github.com/ghostery/trackerdb) — the same dataset that powers the Ghostery browser extension. For every domain in your query log, we look up:

- **Tracker category** — is this advertising, analytics, fingerprinting, a CDN, consent management?
- **Company** — which organisation operates this tracker?
- **Country** — where is that company based?

This turns raw DNS log data into a meaningful picture of the tracking ecosystem you interact with daily.

## Target Audience

- Privacy-conscious home users who run Pi-hole and want to understand their data better
- Sysadmins managing Pi-hole for households or small organisations
- Privacy researchers interested in DNS-level tracker exposure
- Anyone curious about the commercial surveillance infrastructure embedded in everyday web browsing

## Use Cases

**"What kinds of trackers does Pi-hole block for me?"**
The Overview dashboard breaks down your blocked queries by category — you might discover that 60% of your blocked queries are advertising trackers, with another 25% analytics.

**"Which companies track me most?"**
The Trackers view ranks companies by how often their domains appear in your query log, whether blocked or allowed. Google, Meta, and Amazon tend to dominate.

**"What happened to my query volume over the past week?"**
The timeline chart shows queries and blocks over time, helping you spot changes in behaviour (a new device on the network, a website you started visiting, a new Pi-hole blocklist).

**"I want to investigate this specific domain"**
The query log shows every DNS request enriched with tracker metadata. Filter by category, company, client IP, or date range to drill into exactly what you want to understand.

## Relationship to Pi-hole

pihole-wtm is a **read-only companion** to Pi-hole. It does not:

- Modify Pi-hole's configuration, blocklists, or settings
- Interfere with Pi-hole's DNS resolution
- Require any changes to Pi-hole itself

It only reads query data, either directly from Pi-hole's SQLite database or via the Pi-hole HTTP API.

## Relationship to WhoTracksMe / TrackerDB

The tracker intelligence comes from [Ghostery's TrackerDB](https://github.com/ghostery/trackerdb), which is the open-source database underlying the [WhoTracksMe](https://whotracks.me) project and the Ghostery browser extension. It is released under the Creative Commons Attribution 4.0 licence and maintained actively by Ghostery.

TrackerDB maps domain patterns to tracker names, categories, and operating companies. pihole-wtm downloads the latest release of this database on startup and refreshes it periodically.

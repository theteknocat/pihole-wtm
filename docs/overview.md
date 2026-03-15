# Overview

## The Problem

Pi-hole is excellent at blocking trackers, ads, and malicious domains at the DNS level. Its dashboard gives you counts — total queries, blocked percentage, top blocked domains. What it doesn't tell you is *what kind* of surveillance infrastructure you're blocking, or *who* is behind it.

A blocked domain like `px.ads.linkedin.com` is just a string. Without context, you don't know that it's an advertising tracker operated by LinkedIn (Microsoft), that it appears on a significant fraction of the web, or that it falls into the "advertising" category of trackers.

## The Solution

pihole-wtm enriches your Pi-hole query history with tracker intelligence from multiple sources:

- [Ghostery's TrackerDB](https://github.com/ghostery/trackerdb) — the same dataset that powers the Ghostery browser extension, mapping domains to tracker names, categories, and operating companies
- [Disconnect.me tracking protection lists](https://github.com/disconnectme/disconnect-tracking-protection) — a complementary categorised domain database covering advertising, analytics, social, and cryptomining trackers
- RDAP (Registration Data Access Protocol) — for domains not covered by either database, provides registrant organisation names from domain registration records

For every relevant domain in your query log, we look up:

- **Tracker category** — advertising, analytics, fingerprinting, malware, telemetry?
- **Company** — which organisation operates this domain?
- **Country** — where is that company based?

This turns raw DNS log data into a meaningful picture of the tracking ecosystem you interact with daily.

## What Gets Stored

pihole-wtm does not store every DNS query — only the ones relevant to privacy and security:

- **All blocked queries** — anything Pi-hole blocked, regardless of whether it matches an enrichment source
- **Allowed queries that match a known tracker or threat source** — domains that Pi-hole permitted but that are identified as trackers, adtech, or malware by our enrichment databases

Routine legitimate traffic (CDN requests, OS updates, your own services) is discarded at sync time. The dashboard reflects the surveillance and threat landscape, not your full DNS activity.

## Target Audience

- Privacy-conscious home users who run Pi-hole and want to understand their data better
- Sysadmins managing Pi-hole for households or small organisations
- Privacy researchers interested in DNS-level tracker exposure
- Anyone curious about the commercial surveillance infrastructure embedded in everyday web browsing

## Use Cases

**"What kinds of trackers does Pi-hole block for me?"**
The dashboard breaks down your blocked queries by category — you might discover that 60% of your blocked queries are advertising trackers, with another 25% analytics.

**"Which companies track me most?"**
The dashboard ranks companies by how often their domains appear in your query log, whether blocked or allowed. Google, Meta, and Amazon tend to dominate.

**"What happened to my query volume over the past week?"**
The timeline chart shows queries and blocks over time, helping you spot changes in behaviour (a new device on the network, a website you started visiting, a new Pi-hole blocklist).

**"Something is slipping through my blocklist"**
The dashboard surfaces allowed queries that match known tracker databases — things Pi-hole is permitting that arguably shouldn't be.

**"I want to investigate this specific domain"**
The query log shows every stored DNS request enriched with tracker metadata. Filter by category, company, client IP, or date range to drill into exactly what you want to understand.

## Relationship to Pi-hole

pihole-wtm is a **read-only companion** to Pi-hole. It does not:

- Modify Pi-hole's configuration, blocklists, or settings
- Interfere with Pi-hole's DNS resolution
- Require any changes to Pi-hole itself

It reads query data via the Pi-hole v6 HTTP API, syncing new queries periodically into a local database. Pi-hole v6 is required.

## Relationship to TrackerDB

The primary tracker intelligence comes from [Ghostery's TrackerDB](https://github.com/ghostery/trackerdb), which is the open-source database underlying the [WhoTracksMe](https://whotracks.me) project and the Ghostery browser extension. It is released under the Creative Commons Attribution 4.0 licence and maintained actively by Ghostery.

pihole-wtm downloads the latest release of TrackerDB on startup and refreshes it periodically. Enrichment from additional sources (Disconnect.me, RDAP) supplements TrackerDB for domains it does not cover.

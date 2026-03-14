# Tracker Categories

pihole-wtm classifies domains using [Ghostery's TrackerDB](https://github.com/ghostery/trackerdb), which defines 11 tracker categories. This document describes each category, its privacy implications, and example trackers you might recognise.

These categories appear throughout the dashboard as colour-coded badges and are the primary dimension for filtering and charting your query history.

> **Note:** Category names used here are the canonical identifiers from the TrackerDB schema (e.g. `site_analytics`, not "analytics"). These are the values that appear in API responses and filters.

---

## advertising

**What it is:** Technologies that serve, target, or measure commercial advertisements. Includes ad servers, retargeting pixels, demand-side platforms (DSPs), and attribution trackers.

**Privacy implications:** Advertising trackers build detailed profiles of your browsing behaviour to serve targeted ads. They follow you across websites (cross-site tracking) to understand your interests, purchasing intent, and demographics. Many share data with hundreds of third-party data brokers.

**Examples:** Google Ads (`doubleclick.net`, `googlesyndication.com`), Meta Ads (`facebook.net`), The Trade Desk, Criteo, AppNexus, Amazon Advertising

---

## site_analytics

**What it is:** Tools that measure website traffic, user behaviour, and conversion rates. Includes session recording, heatmaps, A/B testing platforms, and audience analytics.

**Privacy implications:** While analytics trackers are often justified by site owners as essential for understanding their audience, they still collect detailed behavioural data — pages visited, time spent, clicks, scroll depth, and often user identity via login state. Many share data with advertising systems.

**Examples:** Google Analytics (`google-analytics.com`), Adobe Analytics, Mixpanel, Amplitude, Hotjar, Heap, Segment

---

## consent

**What it is:** Platforms that display cookie consent banners and record user consent choices. Required in the EU under GDPR and in other jurisdictions with similar laws.

**Privacy implications:** Consent management platforms (CMPs) are required by law but are also a significant source of tracking data themselves. They record granular consent choices and often share this data with advertising partners. The IAB's Transparency and Consent Framework (TCF) has faced regulatory scrutiny for enabling data collection under the guise of consent management.

**Examples:** OneTrust, Cookiebot, TrustArc, Quantcast Choice, Didomi, Sourcepoint

---

## customer_interaction

**What it is:** Live chat, customer support, and visitor engagement tools embedded on websites.

**Privacy implications:** These tools typically know your identity (if you've chatted), your browsing history on the site, and sometimes cross-site behaviour. Chat transcripts may be used for analytics and training purposes.

**Examples:** Intercom, Zendesk, Drift, HubSpot, Crisp, LiveChat, Freshdesk

---

## hosting

**What it is:** Content delivery networks (CDNs), cloud infrastructure, and hosting providers that serve website content.

**Privacy implications:** Lower privacy risk than advertising trackers, but CDN providers can observe traffic patterns across all sites they serve. Some CDN domains serve both content and tracker scripts, making blocking complex.

**Examples:** Cloudflare, Fastly, Akamai, Amazon CloudFront, Netlify, Vercel

---

## utilities

**What it is:** General-purpose developer tools and infrastructure — error tracking, performance monitoring, feature flagging, and similar services.

**Privacy implications:** Moderate. These services often process technical data about errors and performance rather than detailed personal profiles, but they do receive IP addresses, device information, and may include session data.

**Examples:** Sentry (`sentry.io`), Datadog, New Relic, LaunchDarkly, Optimizely, Bugsnag

---

## social_media

**What it is:** Social network widgets, share buttons, comment systems, and login integrations embedded on third-party sites.

**Privacy implications:** Even if you don't interact with them, social media embeds (like/share buttons, login widgets) report your visit back to the social network, allowing cross-site tracking tied to your social identity.

**Examples:** Facebook Like buttons, Twitter/X embeds, LinkedIn share buttons, Pinterest widgets, Disqus

---

## audio_video_player

**What it is:** Embedded media players and streaming infrastructure. Includes video hosting platforms embedded on third-party sites.

**Privacy implications:** Video players track which content you watch, for how long, and at what quality. Many share this data with advertising systems for interest-based targeting.

**Examples:** YouTube embeds (`youtube.com`, `youtu.be`), Vimeo, JW Player, Brightcove, Wistia

---

## extensions

**What it is:** Browser extension infrastructure and related tracking services.

**Privacy implications:** Can observe browsing behaviour directly within the browser context.

**Examples:** Various browser extension update and telemetry endpoints

---

## misc

**What it is:** Trackers that don't fit neatly into other categories — a catch-all for miscellaneous tracking infrastructure.

**Privacy implications:** Varies. Includes a mix of low-risk infrastructure and harder-to-classify tracking services.

---

## pornvertising

**What it is:** Advertising networks that operate specifically within adult content platforms.

**Privacy implications:** Similar to advertising trackers but specific to adult content sites. May involve particularly sensitive behavioural data.

---

## Unknown

Domains that do not appear in TrackerDB at all. This is not a TrackerDB category — it is pihole-wtm's label for unclassified domains. Unknown domains may be:

- Legitimate first-party domains serving actual website content
- Newer trackers not yet added to TrackerDB
- Internal network or local DNS names
- Privacy-respecting analytics or infrastructure

A high proportion of "Unknown" blocked domains typically indicates your Pi-hole blocklist is catching domains beyond those classified as trackers — which is usually a good thing.

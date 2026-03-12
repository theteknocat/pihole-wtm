# Tracker Categories

pihole-wtm classifies domains using [Ghostery's TrackerDB](https://github.com/ghostery/trackerdb), which defines 11 tracker categories. This document describes each category, its privacy implications, and example trackers you might recognise.

These categories appear throughout the dashboard as colour-coded badges and are the primary dimension for filtering and charting your query history.

---

## Advertising

**What it is:** Technologies that serve, target, or measure commercial advertisements. This includes ad servers, retargeting pixels, demand-side platforms (DSPs), and attribution trackers.

**Privacy implications:** Advertising trackers build detailed profiles of your browsing behaviour to serve targeted ads. They follow you across websites (cross-site tracking) to understand your interests, purchasing intent, and demographics. Many share data with hundreds of third-party data brokers.

**Examples:** Google Ads (`doubleclick.net`, `googlesyndication.com`), Meta Ads (`facebook.net`), The Trade Desk, Criteo, AppNexus, Amazon Advertising

**Common in:** Virtually every commercial website; highest density on news sites, e-commerce, and entertainment

---

## Analytics

**What it is:** Tools that measure website traffic, user behaviour, and conversion rates. Includes session recording, heatmaps, A/B testing platforms, and audience analytics.

**Privacy implications:** While analytics trackers are often justified by site owners as essential for understanding their audience, they still collect detailed behavioural data — pages visited, time spent, clicks, scroll depth, and often user identity via login state. Many share data with advertising systems.

**Examples:** Google Analytics (`google-analytics.com`), Adobe Analytics, Mixpanel, Amplitude, Hotjar, Heap, Segment

**Common in:** Almost all commercial websites; less common on privacy-focused sites

---

## Fingerprinting

**What it is:** Techniques that identify individual users by combining browser and device characteristics (screen size, installed fonts, GPU rendering, browser version, etc.) without using cookies. This creates a persistent identifier that survives cookie clearing.

**Privacy implications:** Fingerprinting is particularly invasive because it cannot be blocked by clearing cookies or using private browsing. It is used to track users across sessions, devices, and even incognito windows.

**Examples:** FingerprintJS, BlueCava, Threatmetrix (LexisNexis), some components of major ad networks

**Common in:** Financial services (for fraud detection), high-value e-commerce, some ad networks

---

## Consent Management

**What it is:** Platforms that display cookie consent banners and record user consent choices. Required in the EU under GDPR and in other jurisdictions with similar laws.

**Privacy implications:** Consent management platforms (CMPs) are required by law but are also a significant source of tracking data themselves. They record granular consent choices and often share this data with advertising partners. The IAB's Transparency and Consent Framework (TCF) has faced regulatory scrutiny for enabling data collection under the guise of consent management.

**Examples:** OneTrust, Cookiebot, TrustArc, Quantcast Choice, Didomi, Sourcepoint

**Common in:** European-facing websites; any site that displays a cookie banner

---

## Hosting / Site Infrastructure

**What it is:** Content delivery networks (CDNs), cloud infrastructure, and hosting providers that serve website content. Often the same provider serves both legitimate site content and third-party tracker scripts.

**Privacy implications:** Lower privacy risk than advertising trackers, but CDN providers can observe traffic patterns across all sites they serve. Some CDN domains serve both content and tracker scripts, making blocking complex.

**Examples:** Cloudflare, Fastly, Akamai, Amazon CloudFront, Netlify, Vercel

**Common in:** Nearly all websites; shared CDN domains mean blocking can break legitimate functionality

---

## Utilities

**What it is:** General-purpose developer tools and infrastructure — error tracking, performance monitoring, feature flagging, A/B testing infrastructure, and similar services.

**Privacy implications:** Moderate. These services often process technical data about errors and performance rather than detailed personal profiles, but they do receive IP addresses, device information, and may include session data.

**Examples:** Sentry (`sentry.io`), Datadog, New Relic, LaunchDarkly, Optimizely, Bugsnag

**Common in:** SaaS products, developer-facing tools, modern web applications

---

## Customer Interaction

**What it is:** Live chat, customer support, and visitor engagement tools embedded on websites.

**Privacy implications:** These tools typically know your identity (if you've chatted), your browsing history on the site, and sometimes cross-site behaviour. Chat transcripts may be used for analytics and training purposes.

**Examples:** Intercom, Zendesk, Drift, HubSpot, Crisp, LiveChat, Freshdesk

**Common in:** SaaS products, e-commerce, B2B websites

---

## Audio / Video Player

**What it is:** Embedded media players and streaming infrastructure. Includes video hosting platforms embedded on third-party sites.

**Privacy implications:** Video players track which content you watch, for how long, and at what quality. Many share this data with advertising systems for interest-based targeting.

**Examples:** YouTube embeds (`youtube.com`, `youtu.be`), Vimeo, JW Player, Brightcove, Wistia

**Common in:** News sites, marketing sites, any site with embedded video

---

## CDN (Tracker-Associated)

**What it is:** Content delivery network domains that are primarily or exclusively used to serve tracker scripts, as distinct from general hosting CDNs that serve both content and scripts.

**Privacy implications:** These CDNs exist specifically to distribute tracker code efficiently. Blocking them is generally safe as they serve no legitimate user-facing content.

**Examples:** Tracker-specific CDN endpoints operated by advertising networks

**Common in:** Heavy advertising sites

---

## Comments

**What it is:** Third-party comment systems embedded on websites.

**Privacy implications:** Comment systems track which articles you read (even if you don't comment), and social login options (Facebook, Google) allow cross-site tracking. Disqus in particular has faced criticism for its advertising data practices.

**Examples:** Disqus, Facebook Comments, Commento, Hyvor Talk

**Common in:** Blogs, news sites, content-heavy websites

---

## Essential

**What it is:** Infrastructure that is functionally necessary for websites to work — authentication services, payment processors, and core APIs. pihole-wtm flags these separately because blocking them may break websites.

**Privacy implications:** Lower privacy concern than advertising trackers, though these services do process personal data. Authentication providers receive login information; payment processors handle financial data.

**Examples:** Auth0, Stripe, PayPal, reCAPTCHA (`google.com/recaptcha`), Cloudflare bot protection

**Common in:** Login-required sites, e-commerce

---

## Unknown

Domains that do not appear in TrackerDB at all. This is not a TrackerDB category — it is pihole-wtm's label for unclassified domains. Unknown domains may be:

- Legitimate first-party domains serving actual website content
- Newer trackers not yet added to TrackerDB
- Internal network or local DNS names
- Privacy-respecting analytics or infrastructure

A high proportion of "Unknown" blocked domains typically indicates your Pi-hole blocklist is catching domains beyond those classified as trackers — which is usually a good thing.

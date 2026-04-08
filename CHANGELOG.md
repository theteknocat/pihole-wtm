# Changelog

## [1.4.0](https://github.com/theteknocat/pihole-wtm/compare/v1.3.1...v1.4.0) (2026-04-08)


### Features

* consistent dashboard functionality ([d709cd1](https://github.com/theteknocat/pihole-wtm/commit/d709cd13f064f5d34d9a3eaadb882fd3c847dc7f))


### Bug Fixes

* horizontal scrollbar on smaller screens ([567cf54](https://github.com/theteknocat/pihole-wtm/commit/567cf54009505284def82260ad2a450b122a55e3))
* time window nav mobile layout ([c2cd3b4](https://github.com/theteknocat/pihole-wtm/commit/c2cd3b43e20bcc6def64c6910cae30ba73adfc98))

## [1.3.1](https://github.com/theteknocat/pihole-wtm/compare/v1.3.0...v1.3.1) (2026-04-07)


### Bug Fixes

* make timeline charts non-stacking ([d2cc2f7](https://github.com/theteknocat/pihole-wtm/commit/d2cc2f769a1368198ba42c6775a6020b27960684))

## [1.3.0](https://github.com/theteknocat/pihole-wtm/compare/v1.2.0...v1.3.0) (2026-04-07)


### Features

* allow flagging individual names for re-enrichment ([28b4732](https://github.com/theteknocat/pihole-wtm/commit/28b4732f3921f0a2e5738b0463bb03108e50df30))
* fallback on whois for enrichment on rdap failure ([1479eac](https://github.com/theteknocat/pihole-wtm/commit/1479eaca08856dc43546e783799cfaf66ff221a3))


### Bug Fixes

* change whois fallback tests to return a tuple to match real output ([30623c7](https://github.com/theteknocat/pihole-wtm/commit/30623c7c3e8156e0f2a5ecb85292149883f81a88))
* remove mistakenly added ripple directive ([4030200](https://github.com/theteknocat/pihole-wtm/commit/4030200b17618df910338d775a9fed423aced283))
* tuple API mismatch caused WHOIS fallback to fail silently ([1b3ede2](https://github.com/theteknocat/pihole-wtm/commit/1b3ede2f3d278aea9eceeffc973555bceb164421))

## [1.2.0](https://github.com/theteknocat/pihole-wtm/compare/v1.1.1...v1.2.0) (2026-04-05)


### Features

* enhanced recent query tables ([f306e9d](https://github.com/theteknocat/pihole-wtm/commit/f306e9d2ec299e6815fabf517aa21f99c0410aea))


### Bug Fixes

* vertically centre utility buttons on mobile ([20c33cb](https://github.com/theteknocat/pihole-wtm/commit/20c33cb138ef7904f706b78a0905d0bd1571ce4f))

## [1.1.1](https://github.com/theteknocat/pihole-wtm/compare/v1.1.0...v1.1.1) (2026-04-04)


### Bug Fixes

* always build frontend on native amd64 to avoid QEMU hang ([5bdcd93](https://github.com/theteknocat/pihole-wtm/commit/5bdcd93fbbb2c82e82260254f061e80198b366a9))

## [1.1.0](https://github.com/theteknocat/pihole-wtm/compare/v1.0.2...v1.1.0) (2026-04-04)


### Features

* dialog to show client stats for a given domain from the domains report ([a3a50e5](https://github.com/theteknocat/pihole-wtm/commit/a3a50e59f3eda48d5057001bdacb55174d439398))

## [1.0.2](https://github.com/theteknocat/pihole-wtm/compare/v1.0.1...v1.0.2) (2026-04-04)


### Bug Fixes

* drop uvicorn standard extras for arm/v7 compatibility ([36b8451](https://github.com/theteknocat/pihole-wtm/commit/36b84512ddca1517d17943694924e74da787d5e0))

## [1.0.1](https://github.com/theteknocat/pihole-wtm/compare/v1.0.0...v1.0.1) (2026-04-04)


### Bug Fixes

* add 32-bit arm (arm7) to the list of build release platforms ([a84fafe](https://github.com/theteknocat/pihole-wtm/commit/a84fafe376534aa708b581a10a714f5d18c5dc83))

## [1.0.0](https://github.com/theteknocat/pihole-wtm/compare/v0.9.9...v1.0.0) (2026-04-04)


### ⚠ BREAKING CHANGES

* prepare v1.0.0 release

### Features

* add /api/stats/domains endpoint for domain-level drill-down ([557e6e4](https://github.com/theteknocat/pihole-wtm/commit/557e6e47d1c23d3355c649ffc2d5ab5fdb97cbd8))
* add domain report view with per-domain query breakdown ([9e49482](https://github.com/theteknocat/pihole-wtm/commit/9e494827696546da9a84ff1f5ffa98e4bacd663c))
* add interactive padding dataset to bar charts ([a9dcb89](https://github.com/theteknocat/pihole-wtm/commit/a9dcb891a17abb94ee8385e4aa9190722f5d53a1))
* build initial dashboard with tracker charts and query tables ([0b4d228](https://github.com/theteknocat/pihole-wtm/commit/0b4d2285411c9fd42f1d72397665d4d6e6f273e4))
* prepare v1.0.0 release ([5de32ed](https://github.com/theteknocat/pihole-wtm/commit/5de32ed7c0e99ec032b0748906a4635242ef67d5))
* wire drill-down navigation from dashboard to domain report ([6af5ee5](https://github.com/theteknocat/pihole-wtm/commit/6af5ee5aa7497d5aa331cff70a5497efb56cc022))


### Bug Fixes

* code review fixes across backend and frontend ([7b6d2b3](https://github.com/theteknocat/pihole-wtm/commit/7b6d2b3690db7e52fc7742fa1731630ee8120139))
* code review fixes for stats and queries endpoints ([7282299](https://github.com/theteknocat/pihole-wtm/commit/728229987f472ee48c3e7fc353bf39f74a66efce))
* exact-match-only gating for allowed queries; fix double lookup ([afd3575](https://github.com/theteknocat/pihole-wtm/commit/afd3575be0d81e12109c40789b61ad792d860417))
* harden backend security and correctness (code review pass) ([153ce17](https://github.com/theteknocat/pihole-wtm/commit/153ce172e525f26a28a7ac6ff0b8115af69c4232))
* store cors_origins as str to avoid pydantic-settings list parsing ([c6523b3](https://github.com/theteknocat/pihole-wtm/commit/c6523b3beb203115cf312bbaaf2699619b1ebea6))
* support comma-separated CORS_ORIGINS to avoid docker-compose YAML issue ([618514b](https://github.com/theteknocat/pihole-wtm/commit/618514b64290ba4d25bfb2a4164a61e593dcf6b9))

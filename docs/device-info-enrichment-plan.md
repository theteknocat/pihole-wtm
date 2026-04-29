# Plan: Device Info Enrichment + Icons

## Context

Client devices are currently identified only by IP address, with optional user-set names in `client_names`. The Pi-hole v6 API exposes `/api/network/devices` with MAC addresses, MAC vendor names, and hostnames. mDNS can additionally reveal advertised service types (printer, TV, etc.) from the backend container. The goal is to auto-populate device metadata (hostname, vendor, mDNS type) as a fallback display name and as the basis for device-type icons, while keeping user-set names as the highest-priority override.

---

## Approach

### 1. Rename `client_names` → `device_info` and add columns — Migration 5

The existing `client_names` table (`client_ip TEXT PRIMARY KEY`, `name TEXT NOT NULL`) becomes `device_info`. Since SQLite can't ALTER column constraints, the migration recreates the table:

```sql
-- Migration 5: rename client_names → device_info, make name nullable, add device columns
CREATE TABLE device_info (
    client_ip      TEXT PRIMARY KEY,
    name           TEXT,           -- user-set friendly name; NULL if not set
    hostname       TEXT,           -- from Pi-hole /api/network/devices
    mac_address    TEXT,
    mac_vendor     TEXT,
    mdns_name      TEXT,           -- hostname from mDNS
    mdns_services  TEXT,           -- JSON array of mDNS service types
    last_synced    INTEGER
);
INSERT INTO device_info (client_ip, name)
    SELECT client_ip, name FROM client_names;
DROP TABLE client_names;
```

All existing user-set names are preserved. Migration is safe with `IF NOT EXISTS` guard on `device_info`.

---

### 2. Backend: Pi-hole device sync

**`backend/app/services/pihole/api_client.py`** — add method:

```python
async def get_network_devices(self) -> list[dict[str, Any]]:
    data = await self._get("/api/network/devices")
    return data.get("devices", [])
```

Each device object contains `hwaddr`, `macVendor`, `interface`, and `ips` (list of `{ip, name}`).

---

### 3. Backend: mDNS scanner

**Prerequisite test (before writing scanner code):** install `zeroconf` in the ddev container and run a quick browse to confirm multicast UDP 5353 is reachable from ddev's bridge network:

```bash
ddev exec -d /var/www/html/backend .venv/bin/pip install zeroconf
ddev exec -d /var/www/html/backend .venv/bin/python -c "
from zeroconf import Zeroconf, ServiceBrowser
import time
zc = Zeroconf()
print('Zeroconf started, browsing 3s...')
time.sleep(3)
zc.close()
print('Done')
"
```

If multicast is blocked, we skip the mDNS feature and note it as a known limitation. If it works, proceed with:

**New file: `backend/app/services/mdns_scanner.py`**

Uses `zeroconf` (add to `pyproject.toml` dependencies). Browses for all service types on the local network and maps them to per-IP records. Falls back silently (logs a warning) if multicast is unavailable.

Key service-type mappings:

- `_ipp._tcp` / `_pdl-datastream._tcp` → printer
- `_airplay._tcp` / `_appletv._tcp` → Apple TV
- `_raop._tcp` → AirPlay speaker
- `_googlecast._tcp` → Chromecast

Stores service list as JSON in `device_info.mdns_services`, hostname in `device_info.mdns_name`.

---

### 4. Backend: `database.py` additions

**Rename all existing methods** from `*_client_name*` → `*_device_info*` / `*_name*` as appropriate:

- `get_device_info()` → `get_device_names()` (or keep as-is, internal only)
- `set_client_name(ip, name)` → updates only the `name` column in `device_info`
- `delete_client_name(ip)` → changed from DELETE row to `SET name = NULL` (preserves device info)

**New methods:**

- `upsert_device_info(client_ip, hostname, mac_address, mac_vendor)` — INSERT OR IGNORE + UPDATE device columns only, preserving user-set `name`
- `update_mdns_info(client_ip, mdns_name, mdns_services)` — partial update for mDNS results

**Update all 5 `LEFT JOIN client_names` query sites** to reference `device_info` with alias `di`, using COALESCE since `name` is now nullable:

```sql
LEFT JOIN device_info di ON q.client_ip = di.client_ip
```

Change `cn.name AS client_name` → `COALESCE(di.name, di.hostname, di.mac_vendor) AS client_name`

The 5 affected query sites are at approximately lines 378, 446, 898, 1057, 1245.

**Update `get_clients()`** to also return `mac_vendor`, `hostname`, `mdns_services` per client for icon rendering.

---

### 5. Backend: sync integration

**`backend/app/services/sync.py`** — add a device sync pass that runs:

- Once at startup (after first query sync completes)
- Every N cycles (e.g. every 10 cycles, same cadence as RDAP reenrich)

Pass fetches Pi-hole network devices → calls `upsert_device_info` for each IP in `device.ips`. Also triggers mDNS scan (async, timeout-bounded) → calls `update_mdns_info`.

---

### 6. Backend: API response update

**`backend/app/main.py`** — update `GET /api/clients` response model to include:

- `mac_vendor: str | None`
- `hostname: str | None`
- `mdns_services: list[str]`

No new endpoints needed — the existing clients endpoint carries everything the frontend needs.

---

### 7. Frontend: FontAwesome

Install `@fortawesome/fontawesome-free` (npm). Import CSS in `main.ts`. Provides `fa-brands fa-apple`, `fa-solid fa-print`, `fa-solid fa-tv`, etc.

---

### 8. Frontend: `DeviceIcon.vue` component

**New file: `frontend/src/components/layout/DeviceIcon.vue`**

Props: `macVendor: string | null`, `mdnsServices: string[]`

Icon resolution order:

1. mDNS service types → device function icon (printer, TV, speaker)
2. MAC vendor keyword → brand icon (Apple → fa-apple, Microsoft → fa-windows, Raspberry Pi → fa-raspberry-pi)
3. Fallback → `pi pi-mobile` (existing PrimeIcon)

---

### 9. Frontend: `api.ts` type update

Add to `ClientStat`:

```typescript
mac_vendor: string | null
hostname: string | null
mdns_services: string[]
```

---

### 10. Frontend: `ClientNameDialog.vue` update

When `hostname` or `mac_vendor` is present, show a `Suggested: <value>` hint below the name input field. Clicking it fills the input. This helps users quickly assign a meaningful name based on auto-detected info.

---

### 11. Frontend: `DevicesReportView` update

Add an icon column (or prepend icon to the name cell) using `DeviceIcon.vue`. Show `mac_vendor` as subtitle if no user name and no hostname is available.

---

## Critical Files

| File                                                  | Change                                                                                                    |
| ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| `backend/app/services/database.py`                    | Migration 5 (rename `client_names` → `device_info`, add columns), update all query sites + method renames |
| `backend/app/services/pihole/api_client.py`           | Add `get_network_devices()`                                                                               |
| `backend/app/services/sync.py`                        | Add device sync pass                                                                                      |
| `backend/app/services/mdns_scanner.py`                | **New** — zeroconf mDNS browser                                                                           |
| `backend/app/main.py`                                 | Update `/api/clients` response model                                                                      |
| `backend/pyproject.toml`                              | Add `zeroconf` dependency                                                                                 |
| `frontend/src/types/api.ts`                           | Add fields to `ClientStat`                                                                                |
| `frontend/src/components/layout/DeviceIcon.vue`       | **New** — icon component                                                                                  |
| `frontend/src/components/layout/ClientNameDialog.vue` | Add suggestion hint                                                                                       |
| `frontend/src/views/DevicesReportView.vue`            | Add icon column                                                                                           |
| `frontend/package.json`                               | Add `@fortawesome/fontawesome-free`                                                                       |

---

## Verification

1. Run `ddev exec -d /var/www/html/backend .venv/bin/pytest` — no regressions
2. Run `ddev exec -d /var/www/html/frontend npm run type-check` — no TS errors
3. Open the Devices report in the browser — confirm icons appear next to known vendors (Apple, ASUS, etc.)
4. Check that resolved names (hostname or vendor) appear for devices without user-set names
5. Open `ClientNameDialog` for a device with known vendor — confirm suggestion hint appears
6. Check backend logs for mDNS scan result (success or graceful fallback warning)

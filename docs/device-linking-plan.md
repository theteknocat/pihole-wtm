# Device Linking Feature

## Context

A physical device can appear under multiple client IPs (wired + wifi, dual interface, IP change over time). The goal is to let the user link those IPs into a named device group so they appear as a single row in the Devices Report with combined stats, and open a single DeviceStatsDialog showing tracker data for all member IPs together.

---

## Schema — Migration 4

Add to `_MIGRATIONS` in `backend/app/services/database.py`:

```sql
CREATE TABLE IF NOT EXISTS device_groups (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS device_group_members (
    group_id    INTEGER NOT NULL REFERENCES device_groups(id) ON DELETE CASCADE,
    client_ip   TEXT NOT NULL,
    PRIMARY KEY (group_id, client_ip)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dgm_unique_client ON device_group_members(client_ip);
CREATE INDEX IF NOT EXISTS idx_dgm_group ON device_group_members(group_id);
```

Key decisions:

- `ON DELETE CASCADE` so deleting a group automatically removes its members
- `UNIQUE` on `client_ip` enforces one group per IP at the DB level
- Individual device names remain in `client_names` unchanged — the group has its own separate name

---

## Backend — `database.py`

### New methods (add after client names section)

```python
async def get_device_groups(self) -> list[dict[str, Any]]
    # Returns [{id, name, members: [{client_ip, client_name}]}]
    # Two queries: SELECT from device_groups, then per-group LEFT JOIN client_names

async def get_device_group(self, group_id: int) -> dict[str, Any] | None

async def create_device_group(self, name: str, member_ips: list[str]) -> int
    # Returns new group id. Raises ValueError if < 2 IPs.

async def update_device_group(self, group_id: int, name: str, member_ips: list[str]) -> bool
    # Full replacement: UPDATE name + DELETE old members + INSERT new members in one transaction.

async def delete_device_group(self, group_id: int) -> bool
    # Deletes group; cascade handles members.
```

### Modify `fetch_tracker_stats`, `_fetch_tracker_breakdown`, `_fetch_tracker_timeline`

Change `client_ip: str | None` → `client_ips: list[str] | None` across all three. Replace the filter condition in each private method:

```python
# Before
if client_ip:
    conditions.append("q.client_ip = ?")
    params.append(client_ip)

# After
if client_ips:
    placeholders = ",".join("?" for _ in client_ips)
    conditions.append(f"q.client_ip IN ({placeholders})")
    params.extend(client_ips)
```

### Modify `fetch_domain_stats`

Same `client_ips: list[str] | None` pattern — replace `client_ip: str | None` and the `= ?` filter:

```python
# Before
client_ip: str | None = None
if client_ip is not None:
    conditions.append("q.client_ip = ?")
    params.append(client_ip)

# After
client_ips: list[str] | None = None
if client_ips:
    placeholders = ",".join("?" for _ in client_ips)
    conditions.append(f"q.client_ip IN ({placeholders})")
    params.extend(client_ips)
```

---

## Backend — `main.py`

### Modify `/api/stats/trackers`

```python
client_ip: list[str] = Query(default=[])   # FastAPI accepts repeated params
# Pass as: client_ips=client_ip or None
```

Single-IP callers (`?client_ip=x`) continue to work unchanged.

### Modify `/api/stats/domains`

Same change: `client_ip: str | None = Query(default=None)` → `client_ip: list[str] = Query(default=[])`. Pass as `client_ips=client_ip or None` to `fetch_domain_stats`.

### Add device groups CRUD

Use a `BaseModel` (pydantic) for the request body — import `BaseModel` from `pydantic`.

```python
class DeviceGroupRequest(BaseModel):
    name: str
    member_ips: list[str]

GET    /api/device-groups              → {groups: [...]}
POST   /api/device-groups              → {status, id}   (validates name ≤ 64, ≥ 2 IPs)
PUT    /api/device-groups/{group_id}   → {status}        (404 if not found)
DELETE /api/device-groups/{group_id}   → {status}        (404 if not found)
```

---

## Frontend — `types/api.ts`

Add:

```typescript
export interface DeviceGroupMember {
  client_ip: string
  client_name: string | null
}

export interface DeviceGroup {
  id: number
  name: string
  members: DeviceGroupMember[]
}
```

No `DeviceTableRow` union type needed in `api.ts` — keep that internal to the view.

---

## Frontend — `DeviceStatsDialog.vue`

Props change:

```typescript
// Before
clientIp: string
// After
clientIps: string[]   // single-device callers pass [ip]
```

Fetch URL change — build repeated `client_ip` params manually (windowStore.queryParams doesn't support arrays):

```typescript
const base = windowStore.queryParams({ include_timeline: 'true' })
const ipParams = props.clientIps.map(ip => `client_ip=${encodeURIComponent(ip)}`).join('&')
const res = await fetch(`/api/stats/trackers?${base}&${ipParams}`)
```

Header fallback: `clientName ?? clientIps.join(', ')`

onClick navigation: pass `clientIps` (single string or string array) directly in the router push query — Vue Router serialises an array as `?client_ip=a&client_ip=b`, which the updated domains report handles.

```typescript
const query: Record<string, string | string[]> = {}
query.client_ip = props.clientIps.length === 1 ? props.clientIps[0] : props.clientIps
if (selectedMode.value.value === 'category') query.category = item.key
else query.company = item.key
router.push({ path: '/domains-report', query })
```

---

## Frontend — `useReportData.ts` + `DomainsReportView.vue`

### `useReportData.ts`

Change `selectedClientIp` from `ref<string | null>` to `ref<string | string[] | null>`. Read from route query handling both cases:

```typescript
const selectedClientIp = ref<string | string[] | null>(
  (() => {
    const v = route.query.client_ip
    if (!v) return null
    if (Array.isArray(v)) return v.filter(Boolean) as string[]
    return v as string
  })()
)
```

`syncUrlParams`: change `query` type to `Record<string, string | string[]>`; assign `query.client_ip = selectedClientIp.value` (works for both string and string[]).

`fetchData` (domain mode): build `client_ip` params manually and concatenate, since `windowStore.queryParams` doesn't support arrays:

```typescript
const base = windowStore.queryParams({ category, company, domain, domain_exact })
const ips = selectedClientIp.value
  ? (Array.isArray(selectedClientIp.value) ? selectedClientIp.value : [selectedClientIp.value])
  : []
const ipPart = ips.map(ip => `client_ip=${encodeURIComponent(ip)}`).join('&')
const qs = [base, ipPart].filter(Boolean).join('&')
```

Route query watcher: normalise `q.client_ip` to `string | string[] | null` before comparing and assigning.

`resetFilters`: sets `selectedClientIp.value = null` — already works for both types.

### `DomainsReportView.vue`

Replace the `<Select>` for client filter with conditional rendering:

- When `Array.isArray(selectedClientIp)`: show a read-only chip — "X devices" with a `×` clear button that sets `selectedClientIp = null`
- Otherwise: show the existing `<Select>` dropdown unchanged

---

## Frontend — New `DeviceLinkDialog.vue`

`frontend/src/components/layout/DeviceLinkDialog.vue`

Props:

```typescript
anchorIp: string           // always pre-selected, checkbox disabled
anchorName: string | null
allClients: ClientStat[]   // source list for the picker
existingGroup: DeviceGroup | null   // non-null when editing an existing group
```

Emits: `close`, `saved`

UI:

- `InputText` for group name (pre-filled with `existingGroup?.name ?? anchorName ?? ''`)
- Scrollable list of available devices with checkboxes (devices already in a *different* group are excluded)
- Save disabled until name is non-empty and ≥ 2 IPs selected
- "Unlink Group" danger button (left-aligned in footer) shown only when `existingGroup !== null`
- POST `/api/device-groups` (create) or PUT `/api/device-groups/{id}` (update) or DELETE (unlink)
- Emits `saved` on success → parent calls `windowStore.triggerRefresh()` + re-fetches groups

---

## Frontend — `DevicesReportView.vue`

### New state

```typescript
const groups = ref<DeviceGroup[]>([])
const expandedRows = ref<Record<string, boolean>>({})
const linkingClient = ref<ClientStat | null>(null)
```

### New fetch

```typescript
async function fetchGroups() { GET /api/device-groups → groups.value }
onMounted(fetchGroups)
watch(() => windowStore.refreshKey, fetchGroups)
```

### Computed `ipToGroup` + `tableRows`

```typescript
const ipToGroup = computed(() => {
  const m = new Map<string, DeviceGroup>()
  for (const g of groups.value)
    for (const member of g.members) m.set(member.client_ip, g)
  return m
})

// Merges grouped IPs into one row; ungrouped pass through as-is
const tableRows = computed(() => {
  const seenGroups = new Set<number>()
  const result = []
  for (const stat of clientData.value?.clients ?? []) {
    const group = ipToGroup.value.get(stat.client_ip)
    if (group) {
      if (seenGroups.has(group.id)) continue
      seenGroups.add(group.id)
      const memberStats = clientData.value!.clients.filter(c =>
        group.members.some(m => m.client_ip === c.client_ip)
      )
      const qc = memberStats.reduce((s, c) => s + c.query_count, 0)
      const bc = memberStats.reduce((s, c) => s + c.blocked_count, 0)
      const ac = memberStats.reduce((s, c) => s + c.allowed_count, 0)
      result.push({ _type: 'group', group, client_name: group.name,
        query_count: qc, blocked_count: bc, allowed_count: ac,
        block_rate: qc ? Math.round(bc / qc * 1000) / 10 : 0,
        member_stats: memberStats, _key: `group-${group.id}` })
    } else {
      result.push({ _type: 'single', ...stat, _key: `single-${stat.client_ip}` })
    }
  }
  return result
})
```

### DataTable changes

- `data-key="_key"` on DataTable
- `v-model:expandedRows="expandedRows"` on DataTable
- Add expander `Column` (show only for group rows)
- Device column body: group rows show group name + member count + link icon button; single rows keep existing pencil + link icon button
- `#expansion` slot: nested DataTable of `row.member_stats` with pencil edit per member
- DataTable binding: `:value="tableRows"` (replaces `clientData.clients`)

### Dialog wiring

```html
<!-- DeviceStatsDialog — group -->
<DeviceStatsDialog
  v-if="inspectingGroup"
  :client-ips="inspectingGroup.group.members.map(m => m.client_ip)"
  :client-name="inspectingGroup.group.name"
  @close="inspectingGroup = null"
/>

<!-- DeviceStatsDialog — single (change client-ip to client-ips) -->
<DeviceStatsDialog
  v-if="inspectingClient"
  :client-ips="[inspectingClient.client_ip]"
  :client-name="inspectingClient.client_name"
  @close="inspectingClient = null"
/>

<DeviceLinkDialog
  v-if="linkingClient"
  :anchor-ip="linkingClient.client_ip"
  :anchor-name="linkingClient.client_name"
  :all-clients="clientData?.clients ?? []"
  :existing-group="ipToGroup.get(linkingClient.client_ip) ?? null"
  @close="linkingClient = null"
  @saved="onGroupSaved"
/>
```

`onGroupSaved`: set `linkingClient = null`, call `windowStore.triggerRefresh()` (which re-runs both `useReportData` fetch and `fetchGroups`).

---

## Tests

### `backend/tests/test_database.py` — new tests

- `test_create_and_get_device_groups` — creates, reads back name + members
- `test_update_device_group` — replaces name and member list
- `test_delete_device_group_cascades` — members table empty after delete
- `test_fetch_tracker_stats_multi_ip` — two IPs → combined total_queries
- `test_fetch_tracker_stats_single_ip_still_works` — regression: single-element list

### `backend/tests/test_api_endpoints.py` — new tests

- `test_get_device_groups_empty`
- `test_create_device_group`
- `test_create_group_requires_two_members` (expects 422)
- `test_delete_device_group_not_found` (expects 404)
- `test_stats_trackers_multi_ip` — `?client_ip=a&client_ip=b` → combined total
- `test_stats_domains_multi_ip` — `?client_ip=a&client_ip=b` → only domains from those two clients

### `frontend/src/tests/DeviceLinkDialog.test.ts` — new file

Follow `ClientBreakdownDialog.test.ts` pattern. Test: pre-selection, save disabled < 2 IPs, POST on create, PUT on update, DELETE on unlink, `saved` emitted, error display.

---

## Implementation Order

1. `database.py` — migration 4 (schema)
2. `database.py` — device group CRUD methods
3. `database.py` — `fetch_tracker_stats` / sub-methods: `client_ip` → `client_ips`
4. `database.py` — `fetch_domain_stats`: `client_ip` → `client_ips`
5. `test_database.py` — new tests
6. `main.py` — multi-IP trackers + domains params + device groups CRUD routes
7. `test_api_endpoints.py` — new tests
8. Run backend checks (ruff, mypy, pytest)
9. `types/api.ts` — `DeviceGroup`, `DeviceGroupMember`
10. `DeviceStatsDialog.vue` — `clientIps: string[]`, fetch URL, header fallback, onClick (pass array)
11. `useReportData.ts` — `selectedClientIp` → `string | string[] | null`, multi-IP fetch, URL sync
12. `DomainsReportView.vue` — conditional chip vs. dropdown for client filter
13. `DeviceLinkDialog.vue` — new component
14. `DevicesReportView.vue` — groups fetch, `tableRows`, expansion slot, link button, dialog wiring
15. `DeviceLinkDialog.test.ts` — new test file
16. Run frontend checks (lint, type-check, test)

---

## Verification

- Run `ddev exec -d /var/www/html/backend .venv/bin/pytest` — all existing + new tests pass
- Run `ddev exec -d /var/www/html/frontend npm run lint && npm run type-check && npm run test`
- Manual: open Devices Report, click link icon on a device, link it to another, verify group row appears with combined stats, expand to see both members, open DeviceStatsDialog for the group
- Manual: from DeviceStatsDialog (group), click a category bar — verify domains report opens with multi-IP chip filter active and shows only that group's domains

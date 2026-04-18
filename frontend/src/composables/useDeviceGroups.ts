/**
 * useDeviceGroups — fetch device groups and merge ClientStat rows accordingly.
 *
 * Accepts a reactive list of ClientStat objects and returns:
 *   fetchGroups — async function to (re)fetch; call from onMounted + refreshKey watcher
 *   ipToGroup   — Map<client_ip, DeviceGroup> for quick lookups
 *   tableRows   — merged rows: grouped IPs collapsed into one GroupRow, others as SingleRow
 */
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { apiFetch } from '@/utils/api'
import type { ClientStat, DeviceGroup } from '@/types/api'

export type GroupRow = {
  _type: 'group'
  _key: string
  group: DeviceGroup
  client_name: string
  query_count: number
  blocked_count: number
  allowed_count: number
  block_rate: number
  member_stats: ClientStat[]
}

export type SingleRow = ClientStat & { _type: 'single'; _key: string }
export type TableRow = GroupRow | SingleRow

export function useDeviceGroups(clients: Ref<ClientStat[]>) {
  const groups = ref<DeviceGroup[]>([])

  async function fetchGroups() {
    try {
      const res = await apiFetch('/api/device-groups')
      if (res.ok) {
        const json = await res.json()
        groups.value = json.groups ?? []
      }
    } catch {
      // Non-fatal; groups just won't be shown
    }
  }

  const ipToGroup = computed(() => {
    const m = new Map<string, DeviceGroup>()
    for (const g of groups.value) {
      for (const member of g.members) m.set(member.client_ip, g)
    }
    return m
  })

  const tableRows = computed<TableRow[]>(() => {
    const seenGroups = new Set<number>()
    const result: TableRow[] = []

    for (const stat of clients.value) {
      const group = ipToGroup.value.get(stat.client_ip)
      if (group) {
        if (seenGroups.has(group.id)) continue
        seenGroups.add(group.id)
        const memberStats = clients.value.filter(c =>
          group.members.some(m => m.client_ip === c.client_ip)
        )
        // Only show a group row when 2+ members are present in this dataset.
        // If only one member appears (e.g. filtered domain breakdown), render it
        // as a normal single row so the group label doesn't mislead the user.
        if (memberStats.length < 2) {
          const sole = memberStats[0] ?? stat
          result.push({ _type: 'single', _key: `single-${sole.client_ip}`, ...sole })
          continue
        }
        const qc = memberStats.reduce((s, c) => s + c.query_count, 0)
        const bc = memberStats.reduce((s, c) => s + c.blocked_count, 0)
        const ac = memberStats.reduce((s, c) => s + c.allowed_count, 0)
        result.push({
          _type: 'group',
          _key: `group-${group.id}`,
          group,
          client_name: group.name,
          query_count: qc,
          blocked_count: bc,
          allowed_count: ac,
          block_rate: qc ? Math.round(bc / qc * 1000) / 10 : 0,
          member_stats: memberStats,
        })
      } else {
        result.push({ _type: 'single', _key: `single-${stat.client_ip}`, ...stat })
      }
    }
    return result
  })

  return { fetchGroups, ipToGroup, tableRows }
}

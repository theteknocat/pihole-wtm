import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useWindowStore } from '@/stores/window'
import { apiFetch } from '@/utils/api'

/**
 * Shared health state — fetched periodically and on demand.
 *
 * Module-level refs so all consumers share the same data (same pattern
 * as useAuth). The composable also feeds data range info into the window
 * store so period options stay in sync with available data.
 */

export interface SourceStatus {
  name: string
  label: string
  loaded: boolean
  domain_count: number
}

export interface HealthData {
  status: string
  pihole_api_url: string | null
  version: string
  sources: SourceStatus[]
  last_synced_at: number | null
  stored_queries: number
  sync_active: boolean
  sync_source: 'env' | 'session' | null
}

const health = ref<HealthData | null>(null)
const error = ref(false)
const syncAgo = ref('never')

let tickTimer: ReturnType<typeof setInterval> | null = null
let mountCount = 0

function updateSyncAgo() {
  const ts = health.value?.last_synced_at
  if (!ts) { syncAgo.value = 'never'; return }
  const ago = Math.round((Date.now() / 1000) - ts)
  if (ago < 60) syncAgo.value = `${ago}s ago`
  else if (ago < 3600) syncAgo.value = `${Math.floor(ago / 60)}m ago`
  else syncAgo.value = `${Math.floor(ago / 3600)}h ago`
}

async function fetchHealth() {
  const windowStore = useWindowStore()
  try {
    const res = await apiFetch('/api/health')
    if (!res.ok) throw new Error()
    // The oldest and newest available timestamps are included with
    // the health data response for simplicity. While not part of
    // health data, this is an existing request that returns info
    // from the queries table already (the total queries) so its
    // easy to also include the date range. Otherwise we'd need
    // a whole other little helper just to fetch that and stuff it
    // into the window store, which is just extra code and overhead.
    const { oldest_ts, newest_ts, ...healthData } = await res.json()
    health.value = healthData
    error.value = false
    windowStore.setDataRange(oldest_ts, newest_ts)
    updateSyncAgo()
  } catch {
    error.value = true
  }
}

export function useHealth() {
  const windowStore = useWindowStore()

  // Auto-refresh health on the shared refresh tick
  watch(() => windowStore.refreshKey, fetchHealth)

  // Manage the "Xs ago" tick timer — start on first mount, stop when all unmount
  onMounted(() => {
    mountCount++
    if (mountCount === 1) {
      fetchHealth()
      tickTimer = setInterval(updateSyncAgo, 5_000)
    }
  })

  onUnmounted(() => {
    mountCount--
    if (mountCount === 0 && tickTimer) {
      clearInterval(tickTimer)
      tickTimer = null
    }
  })

  return { health, error, syncAgo, fetchHealth }
}

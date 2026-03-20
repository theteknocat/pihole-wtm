<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { apiFetch } from '@/utils/api'

interface SourceStatus {
  name: string
  label: string
  loaded: boolean
  domain_count: number
}

interface HealthData {
  status: string
  pihole_api_url: string | null
  version: string
  sources: SourceStatus[]
  last_synced_at: number | null
  stored_queries: number
}

const health = ref<HealthData | null>(null)
const pihole = ref<{ connected: boolean; version?: string } | null>(null)
const error = ref(false)
const fetching = ref(false)
let hasLoaded = false

let timer: ReturnType<typeof setTimeout> | null = null
let alive = true

async function fetchStatus() {
  fetching.value = true
  try {
    const res = await apiFetch('/api/health')
    if (!res.ok) throw new Error()
    health.value = await res.json()
    error.value = false
    updateSyncAgo()
  } catch {
    error.value = true
  }

  try {
    const res = await apiFetch('/api/pihole/test')
    if (res.ok) {
      pihole.value = await res.json()
    } else {
      pihole.value = { connected: false }
    }
  } catch {
    pihole.value = { connected: false }
  }

  fetching.value = false
  hasLoaded = true

  // Schedule next fetch after completion, so drift doesn't push us past the sync interval
  if (alive) timer = setTimeout(fetchStatus, 55_000)
}

// Reactive sync time display — ticks every 5s so "Xs ago" stays current
const syncAgo = ref('never')
let tickTimer: ReturnType<typeof setInterval> | null = null

function updateSyncAgo() {
  const ts = health.value?.last_synced_at
  if (!ts) { syncAgo.value = 'never'; return }
  const ago = Math.round((Date.now() / 1000) - ts)
  if (ago < 60) syncAgo.value = `${ago}s ago`
  else if (ago < 3600) syncAgo.value = `${Math.floor(ago / 60)}m ago`
  else syncAgo.value = `${Math.floor(ago / 3600)}h ago`
}

onMounted(() => {
  fetchStatus()
  tickTimer = setInterval(updateSyncAgo, 5_000)
})

onUnmounted(() => {
  alive = false
  if (timer) clearTimeout(timer)
  if (tickTimer) clearInterval(tickTimer)
})
</script>

<template>
  <footer
    class="shrink-0 border-t border-gray-200 dark:border-gray-800 px-4 py-1.5 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 font-mono"
  >
    <template v-if="error">
      <span class="text-red-400 flex items-center gap-1">
        <i class="pi pi-times-circle" />Backend unreachable
      </span>
    </template>
    <template v-else-if="health">
      <!-- Version -->
      <span>v{{ health.version }}</span>

      <span class="text-gray-300 dark:text-gray-600">|</span>

      <!-- Pi-hole status -->
      <span class="flex items-center gap-1">
        <i
          :class="pihole?.connected
            ? 'pi pi-check-circle text-green-500 dark:text-green-400'
            : 'pi pi-times-circle text-red-400'"
        />
        Pi-hole{{ pihole?.version ? ` ${pihole.version}` : '' }}
      </span>

      <span class="text-gray-300 dark:text-gray-600">|</span>

      <!-- Sources -->
      <template v-for="(source, i) in health.sources" :key="source.name">
        <span v-if="i > 0" class="text-gray-300 dark:text-gray-600">|</span>
        <span
          class="flex items-center gap-1"
          :title="source.loaded ? `${source.domain_count.toLocaleString()} domains` : 'Not loaded'"
        >
        <i
          :class="source.loaded
            ? 'pi pi-check-circle text-green-500 dark:text-green-400'
            : 'pi pi-times-circle text-red-400'"
        />
        {{ source.label }}
      </span>
      </template>

      <span class="text-gray-300 dark:text-gray-600">|</span>

      <!-- Sync status -->
      <span>Last sync {{ syncAgo }}</span>

      <span class="text-gray-300 dark:text-gray-600">|</span>

      <!-- Stored queries -->
      <span>{{ health.stored_queries.toLocaleString() }} queries</span>

      <!-- Health check refresh indicator -->
      <i v-if="fetching && hasLoaded" class="pi pi-spin pi-spinner ml-auto" />
    </template>
    <template v-else>
      <span class="text-gray-400">Loading...</span>
    </template>
  </footer>
</template>

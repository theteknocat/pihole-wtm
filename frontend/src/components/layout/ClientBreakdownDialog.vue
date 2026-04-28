<script setup lang="ts">
/**
 * ClientBreakdownDialog — modal showing per-device query breakdown for a
 * domain, category, or company.
 *
 * Shows a horizontal bar chart (one bar per device/group) followed by a
 * stacked timeline. Clicking a bar opens DeviceStatsDialog for that device.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import PvChart from 'primevue/chart'
import ProgressSpinner from 'primevue/progressspinner'
import DeviceStatsDialog from '@/components/layout/DeviceStatsDialog.vue'
import TrackerTimelineChart from '@/components/timeline/TrackerTimelineChart.vue'
import { useWindowStore } from '@/stores/window'
import { useDeviceGroups } from '@/composables/useDeviceGroups'
import { useTrackerBarChart } from '@/composables/useTrackerBarChart'
import { formatCategory } from '@/utils/format'
import type { ClientStats, ClientFilter, TrackerTimelineSeries } from '@/types/api'

const props = defineProps<{
  filter: ClientFilter
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const router = useRouter()
const windowStore = useWindowStore()
const visible = ref(true)
const stats = ref<ClientStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const title = computed(() => {
  switch (props.filter.type) {
    case 'category': return formatCategory(props.filter.value)
    default: return props.filter.value
  }
})

const icon = computed(() => {
  switch (props.filter.type) {
    case 'domain': return 'pi pi-globe'
    case 'category': return 'pi pi-tags'
    default: return 'pi pi-building'
  }
})

// ---- Device groups ----------------------------------------------------------

const clients = computed(() => stats.value?.clients ?? [])
const { fetchGroups, ipToGroup, tableRows } = useDeviceGroups(clients)

// ---- Bar chart --------------------------------------------------------------

interface DeviceChartItem {
  name: string
  clientIps: string[]
  clientName: string | null
  query_count: number
  blocked_count: number
  allowed_count: number
}

const chartItems = computed<DeviceChartItem[]>(() =>
  tableRows.value.map(row => {
    if (row._type === 'group') {
      return {
        name: row.group.name,
        clientIps: row.group.members.map(m => m.client_ip),
        clientName: row.group.name,
        query_count: row.query_count,
        blocked_count: row.blocked_count,
        allowed_count: row.allowed_count,
      }
    }
    return {
      name: row.client_name ?? row.client_ip,
      clientIps: [row.client_ip],
      clientName: row.client_name,
      query_count: row.query_count,
      blocked_count: row.blocked_count,
      allowed_count: row.allowed_count,
    }
  })
)

const totalQueries = computed(() =>
  chartItems.value.reduce((s, c) => s + c.query_count, 0)
)

const { isDark, chartRef, chartHeight, chartData, chartOptions: baseOptions } = useTrackerBarChart({
  items: chartItems,
  totalTrackerQueries: totalQueries,
  label: c => c.name,
  tooltipTitle: c => `${c.name} — ${c.query_count.toLocaleString()} queries`,
  rowHeight: 38,
})

// ---- Device stats dialog (opens on bar click) -------------------------------

const inspectingDevice = ref<{ clientIps: string[]; clientName: string | null } | null>(null)

const chartOptions = computed(() => ({
  ...baseOptions.value,
  onClick: (_: unknown, elements: { index: number }[]) => {
    if (!elements.length) return
    const item = chartItems.value[elements[0].index]
    inspectingDevice.value = { clientIps: item.clientIps, clientName: item.clientName }
  },
  onHover: (event: { native: MouseEvent | null }, elements: { index: number }[]) => {
    if (!event.native?.target) return
    const el = event.native.target as HTMLElement
    el.style.cursor = elements.length ? 'pointer' : 'default'
  },
}))

// ---- Timeline ---------------------------------------------------------------

const timelineSeries = computed<TrackerTimelineSeries[]>(() => {
  const timeline = stats.value?.by_client_timeline
  if (!timeline?.length) return []

  // Aggregate per-IP series into per-device/group series using the group map
  const seriesMap = new Map<string, { label: string; counts: number[] }>()
  for (const entry of timeline) {
    const group = ipToGroup.value.get(entry.client_ip)
    const key = group ? `group-${group.id}` : entry.client_ip
    const label = group ? group.name : (entry.client_name ?? entry.client_ip)
    const existing = seriesMap.get(key)
    if (existing) {
      for (let i = 0; i < entry.counts.length; i++) {
        existing.counts[i] = (existing.counts[i] ?? 0) + entry.counts[i]
      }
    } else {
      seriesMap.set(key, { label, counts: [...entry.counts] })
    }
  }

  return [...seriesMap.values()].map(s => ({ label: s.label, counts: s.counts }))
})

const bucketTimestamps = computed(() => stats.value?.bucket_timestamps ?? [])
const bucketSeconds = computed(() => stats.value?.bucket_seconds ?? 3600)

// ---- Data fetch -------------------------------------------------------------

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const qs = windowStore.queryParams({
      [props.filter.type]: props.filter.value,
      include_timeline: 'true',
    })
    const res = await fetch(`/api/stats/clients?${qs}`)
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    stats.value = await res.json()
  } catch {
    error.value = 'Failed to load device breakdown.'
  } finally {
    loading.value = false
  }
}

function viewFullReport() {
  visible.value = false
  router.push({
    path: '/domains-report',
    query: { [props.filter.type]: props.filter.value },
  })
}

function onHide() {
  emit('close')
}

onMounted(async () => {
  await Promise.all([fetchStats(), fetchGroups()])
})
watch(() => windowStore.refreshKey, () => {
  fetchStats()
  fetchGroups()
})
</script>

<template>
  <Dialog
    v-model:visible="visible"
    maximizable
    modal
    :closable="true"
    :draggable="false"
    :style="{ width: '90vw' }"
    @hide="onHide"
  >
    <template #header>
      <div class="font-semibold">
        <span class="text-lg"><i :class="icon" /> {{ title }} — Device Breakdown</span>
        <span class="text-sm text-gray-500 dark:text-gray-400">
          (past {{ windowStore.availablePeriods.find(o => o.value === windowStore.hours)?.label ?? `${windowStore.hours}h` }})
        </span>
      </div>
    </template>

    <!-- Subtitle + report link -->
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-base font-semibold text-gray-700 dark:text-gray-300">
        <template v-if="stats">
          {{ totalQueries.toLocaleString() }}
        </template>
        <template v-else>No</template>
        Queries
      </h3>
      <Button
        v-if="filter.type !== 'domain'"
        :label="'See all ' + title + ' Domains'"
        icon="pi pi-external-link"
        severity="secondary"
        text
        size="small"
        @click="viewFullReport"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading && !stats" class="flex flex-col items-center justify-center py-16 gap-4 text-gray-500 dark:text-gray-400">
      <ProgressSpinner />
      <p>Loading…</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center py-16">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <template v-if="stats">
      <!-- Device bar chart -->
      <PvChart
        ref="chartRef"
        type="bar"
        :data="chartData"
        :options="chartOptions"
        :key="isDark ? 'dark' : 'light'"
        :style="{ height: `${chartHeight}px` }"
      />

      <!-- Timeline -->
      <template v-if="bucketTimestamps.length > 0">
        <h3 class="text-base font-semibold text-gray-700 dark:text-gray-300 mt-8 mb-3">
          Timeline
        </h3>
        <TrackerTimelineChart
          :series="timelineSeries"
          :bucket-timestamps="bucketTimestamps"
          :bucket-seconds="bucketSeconds"
        />
      </template>
    </template>
  </Dialog>

  <!-- Device stats dialog — opens on bar click -->
  <DeviceStatsDialog
    v-if="inspectingDevice"
    :client-ips="inspectingDevice.clientIps"
    :client-name="inspectingDevice.clientName"
    @close="inspectingDevice = null"
    @navigate="visible = false"
  />
</template>

<script setup lang="ts">
/**
 * DeviceStatsDialog — maximizable modal showing tracker stats for a single device.
 *
 * Two charts are shown:
 *  1. Horizontal bar breakdown (categories or companies) — same as before.
 *  2. Stacked bar timeline (categories or companies over time) — new.
 *
 * Both are driven by the same Categories / Companies toggle. Data for both
 * arrives in a single fetch via include_timeline=true.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import PvChart from 'primevue/chart'
import SelectButton from 'primevue/selectbutton'
import ProgressSpinner from 'primevue/progressspinner'
import { useWindowStore } from '@/stores/window'
import { useTrackerBarChart } from '@/composables/useTrackerBarChart'
import { formatCategory } from '@/utils/format'
import TrackerTimelineChart from '@/components/timeline/TrackerTimelineChart.vue'
import type { TrackerStats, CompanyStat, TrackerTimelineSeries } from '@/types/api'

interface ChartItem {
  name: string
  key: string  // raw value for URL filter (category slug or company name)
  query_count: number
  blocked_count: number
  allowed_count: number
}

const TOP_COMPANIES = 10

const props = defineProps<{
  clientIps: string[]
  clientName: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'navigate'): void
}>()

const router = useRouter()
const windowStore = useWindowStore()
const visible = ref(true)
const stats = ref<TrackerStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// Chart toggle
const chartModeOptions = [
  { label: 'Categories', value: 'category' as const },
  { label: 'Companies', value: 'company' as const },
]
const selectedMode = ref(chartModeOptions[0])

// Aggregate companies across categories — same logic as DashboardView
const allCompanies = computed<CompanyStat[]>(() => {
  if (!stats.value) return []
  const map = new Map<string, CompanyStat>()
  for (const cat of stats.value.by_category) {
    for (const co of cat.companies) {
      const existing = map.get(co.company_name)
      if (existing) {
        existing.query_count += co.query_count
        existing.blocked_count += co.blocked_count
        existing.allowed_count += co.allowed_count
      } else {
        map.set(co.company_name, { ...co })
      }
    }
  }
  return [...map.values()]
})

// Normalize both data shapes into a common ChartItem array.
// Top-15 companies are shown individually; the rest are collapsed into "Other".
// The composable watches this ref and updates the chart in place.
const chartItems = computed<ChartItem[]>(() => {
  if (!stats.value) return []
  if (selectedMode.value.value === 'category') {
    return [...stats.value.by_category]
      .sort((a, b) => b.query_count - a.query_count)
      .map(c => ({ name: formatCategory(c.category), key: c.category, query_count: c.query_count, blocked_count: c.blocked_count, allowed_count: c.allowed_count }))
  }
  const sorted = [...allCompanies.value].sort((a, b) => b.query_count - a.query_count)
  const top = sorted.slice(0, TOP_COMPANIES)
  const rest = sorted.slice(TOP_COMPANIES)
  const items = top.map(c => ({
    name: c.company_name,
    key: c.company_name,
    query_count: c.query_count,
    blocked_count: c.blocked_count,
    allowed_count: c.allowed_count,
  }))
  if (rest.length > 0) {
    items.push({
      name: 'Other',
      key: '__other__',
      query_count: rest.reduce((s, c) => s + c.query_count, 0),
      blocked_count: rest.reduce((s, c) => s + c.blocked_count, 0),
      allowed_count: rest.reduce((s, c) => s + c.allowed_count, 0),
    })
  }
  return items
})

const trackerQueries = computed(() => stats.value?.tracker_queries ?? 0)

const { isDark, chartRef, chartHeight, chartData, chartOptions: baseOptions } = useTrackerBarChart({
  items: chartItems,
  totalTrackerQueries: trackerQueries,
  label: c => c.name,
  tooltipTitle: c => `${c.name} — ${c.query_count.toLocaleString()} queries`,
  rowHeight: 38,
})

const chartOptions = computed(() => ({
  ...baseOptions.value,
  onClick: (_: unknown, elements: { index: number }[]) => {
    if (!elements.length) return
    const item = chartItems.value[elements[0].index]
    if (item.key === '__other__') return
    const query: Record<string, string | string[]> = {}
    query.client_ip = props.clientIps.length === 1 ? props.clientIps[0] : props.clientIps
    if (selectedMode.value.value === 'category') {
      query.category = item.key
    } else {
      query.company = item.key
    }
    visible.value = false
    router.push({ path: '/domains-report', query })
  },
  onHover: (event: { native: MouseEvent | null }, elements: { index: number }[]) => {
    if (!event.native?.target) return
    const el = event.native.target as HTMLElement
    if (!elements.length) {
      el.style.cursor = 'default'
      return
    }
    const item = chartItems.value[elements[0].index]
    el.style.cursor = item.key === '__other__' ? 'default' : 'pointer'
  },
}))

// Timeline series derived from the stats payload for the active mode
const timelineSeries = computed<TrackerTimelineSeries[]>(() => {
  if (!stats.value) return []
  if (selectedMode.value.value === 'category') {
    return (stats.value.by_category_timeline ?? []).map(s => ({
      label: formatCategory(s.category),
      counts: s.counts,
    }))
  }
  return (stats.value.by_company_timeline ?? []).map(s => ({
    label: s.company_name,
    counts: s.counts,
  }))
})

const bucketTimestamps = computed(() => stats.value?.bucket_timestamps ?? [])
const bucketSeconds = computed(() => stats.value?.bucket_seconds ?? 3600)

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const base = windowStore.queryParams({ include_timeline: 'true' })
    const ipParams = props.clientIps.map(ip => `client_ip=${encodeURIComponent(ip)}`).join('&')
    const res = await fetch(`/api/stats/trackers?${base}&${ipParams}`)
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    stats.value = await res.json()
  } catch {
    error.value = 'Failed to load device stats.'
  } finally {
    loading.value = false
  }
}

const domainsReportQuery = computed<Record<string, string | string[]>>(() => {
  const query: Record<string, string | string[]> = {}
  query.client_ip = props.clientIps.length === 1 ? props.clientIps[0] : props.clientIps
  return query
})

const domainsReportHref = computed(() =>
  router.resolve({ path: '/domains-report', query: domainsReportQuery.value }).href
)

function viewDomainsReport(event: MouseEvent) {
  if (event.ctrlKey || event.metaKey || event.shiftKey) return
  event.preventDefault()
  emit('navigate')
  visible.value = false
  router.push({ path: '/domains-report', query: domainsReportQuery.value })
}

function onHide() {
  emit('close')
}

onMounted(fetchStats)
watch(() => windowStore.refreshKey, fetchStats)
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
      <div class="flex flex-col items-start gap-2 w-full pr-2 md:flex-row md:items-center md:justify-between">
        <div class="font-semibold">
          <span class="text-lg"><i class="pi pi-mobile" /> {{ clientName ?? clientIps.join(', ') }} — Tracker Breakdown</span>
          <span class="text-sm text-gray-500 dark:text-gray-400">
            (past {{ windowStore.availablePeriods.find(o => o.value === windowStore.hours)?.label ?? `${windowStore.hours}h` }})
          </span>
          <div v-if="clientIps.length > 1" class="text-base text-gray-600 dark:text-gray-400">
            <i class="pi pi-link"/> {{ clientIps.length }} devices
          </div>
        </div>
        <SelectButton
          v-model="selectedMode"
          :options="chartModeOptions"
          option-label="label"
          :allow-empty="false"
        />
      </div>
    </template>

    <!-- Subtitle + domains report link -->
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-base font-semibold text-gray-700 dark:text-gray-300">
        <template v-if="stats">
          {{ stats.tracker_queries.toLocaleString() }}
        </template>
        <template v-else>
          No
        </template>
        Queries
      </h3>
      <Button
        as="a"
        :href="domainsReportHref"
        label="View Domains Report"
        icon="pi pi-external-link"
        severity="secondary"
        text
        size="small"
        class="domains-report-link"
        @click="viewDomainsReport"
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
      <!-- Breakdown bar chart -->
      <PvChart
        ref="chartRef"
        type="bar"
        :data="chartData"
        :options="chartOptions"
        :key="isDark ? 'dark' : 'light'"
        :style="{ height: `${chartHeight}px` }"
      />

      <!-- Timeline stacked bar chart -->
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
</template>

<style scoped>
:deep(.domains-report-link):hover {
  text-decoration: none;
}
</style>

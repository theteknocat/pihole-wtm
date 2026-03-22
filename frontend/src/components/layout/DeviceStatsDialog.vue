<script setup lang="ts">
/**
 * DeviceStatsDialog — near-fullscreen modal showing tracker stats for a single device.
 *
 * Uses a single Chart.js instance with useTrackerBarChart. Toggling between
 * categories and companies swaps the data fed to the composable, which updates
 * the chart in place for smooth animated transitions.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Dialog from 'primevue/dialog'
import PvChart from 'primevue/chart'
import SelectButton from 'primevue/selectbutton'
import ProgressSpinner from 'primevue/progressspinner'
import { useWindowStore } from '@/stores/window'
import { useTrackerBarChart } from '@/composables/useTrackerBarChart'
import { formatCategory } from '@/utils/format'
import type { TrackerStats, CompanyStat } from '@/types/api'

interface ChartItem {
  name: string
  key: string  // raw value for URL filter (category slug or company name)
  query_count: number
  blocked_count: number
  allowed_count: number
}

const props = defineProps<{
  clientIp: string
  clientName: string | null
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

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
// The composable watches this ref and updates the chart in place.
const chartItems = computed<ChartItem[]>(() => {
  if (!stats.value) return []
  if (selectedMode.value.value === 'category') {
    return [...stats.value.by_category]
      .sort((a, b) => b.query_count - a.query_count)
      .map(c => ({ name: formatCategory(c.category), key: c.category, query_count: c.query_count, blocked_count: c.blocked_count, allowed_count: c.allowed_count }))
  }
  return [...allCompanies.value]
    .sort((a, b) => b.query_count - a.query_count)
    .slice(0, 15)
    .map(c => ({ name: c.company_name, key: c.company_name, query_count: c.query_count, blocked_count: c.blocked_count, allowed_count: c.allowed_count }))
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
    const query: Record<string, string> = { client_ip: props.clientIp }
    if (selectedMode.value.value === 'category') {
      query.category = item.key
    } else {
      query.company = item.key
    }
    visible.value = false
    router.push({ path: '/domains-report', query })
  },
  onHover: (event: { native: MouseEvent | null }, elements: unknown[]) => {
    if (event.native?.target)
      (event.native.target as HTMLElement).style.cursor = elements.length ? 'pointer' : 'default'
  },
}))

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const qs = windowStore.queryParams({ client_ip: props.clientIp })
    const res = await fetch(`/api/stats/trackers?${qs}`)
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    stats.value = await res.json()
  } catch {
    error.value = 'Failed to load device stats.'
  } finally {
    loading.value = false
  }
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
    modal
    :closable="true"
    position="top"
    :draggable="false"
    :style="{ width: '90vw', maxWidth: '1100px' }"
    @hide="onHide"
  >
    <template #header>
      <div class="flex flex-col items-start gap-2 w-full pr-2 md:flex-row md:items-center md:justify-between">
        <span class="font-semibold text-lg">{{ clientName ?? clientIp }} — Tracker Breakdown</span>
        <SelectButton
          v-model="selectedMode"
          :options="chartModeOptions"
          option-label="label"
          :allow-empty="false"
        />
      </div>
    </template>

    <!-- Subtitle -->
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
      {{ windowStore.availablePeriods.find(o => o.value === windowStore.hours)?.label ?? `${windowStore.hours}h` }} window
      <template v-if="stats"> — {{ stats.tracker_queries.toLocaleString() }} tracker queries</template>
    </p>

    <!-- Loading -->
    <div v-if="loading && !stats" class="flex flex-col items-center justify-center py-16 gap-4 text-gray-500 dark:text-gray-400">
      <ProgressSpinner />
      <p>Loading…</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center py-16">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Chart -->
    <PvChart
      v-if="stats"
      ref="chartRef"
      type="bar"
      :data="chartData"
      :options="chartOptions"
      :key="isDark ? 'dark' : 'light'"
      :style="{ height: `${chartHeight}px` }"
    />
  </Dialog>
</template>

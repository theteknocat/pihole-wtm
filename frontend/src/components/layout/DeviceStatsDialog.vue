<script setup lang="ts">
/**
 * DeviceStatsDialog — near-fullscreen modal showing tracker stats for a single device.
 *
 * Reuses the existing CategoryBarChart and CompanyBarChart components with data
 * fetched from /api/stats/trackers filtered by client_ip. A toggle switches
 * between the two chart views.
 */
import { ref, computed, onMounted, watch } from 'vue'
import Dialog from 'primevue/dialog'
import SelectButton from 'primevue/selectbutton'
import ProgressSpinner from 'primevue/progressspinner'
import CategoryBarChart from '@/components/dashboard/CategoryBarChart.vue'
import CompanyBarChart from '@/components/dashboard/CompanyBarChart.vue'
import { useWindowStore } from '@/stores/window'
import type { TrackerStats, CompanyStat } from '@/types/api'

const props = defineProps<{
  clientIp: string
  clientName: string | null
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const windowStore = useWindowStore()
const visible = ref(true)
const stats = ref<TrackerStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// Chart toggle
const chartOptions = [
  { label: 'Categories', value: 'category' as const },
  { label: 'Companies', value: 'company' as const },
]
const selectedChart = ref(chartOptions[0])

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

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams({
      hours: String(windowStore.hours),
      client_ip: props.clientIp,
    })
    const res = await fetch(`/api/stats/trackers?${params}`)
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
    :style="{ width: '90vw', maxWidth: '1100px' }"
    :content-style="{ minHeight: '400px' }"
    @hide="onHide"
  >
    <template #header>
      <div class="flex items-center justify-between w-full pr-2">
        <span class="font-semibold text-lg">{{ clientName ?? clientIp }} — Tracker Breakdown</span>
        <SelectButton
          v-model="selectedChart"
          :options="chartOptions"
          option-label="label"
          :allow-empty="false"
        />
      </div>
    </template>

    <!-- Subtitle -->
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
      {{ windowStore.hours <= 24 ? '24h' : '7d' }} window
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

    <!-- Charts -->
    <template v-if="stats">
      <CategoryBarChart
        v-if="selectedChart.value === 'category'"
        :data="stats.by_category"
        :total-tracker-queries="stats.tracker_queries"
      />
      <CompanyBarChart
        v-else
        :data="allCompanies"
        :total-tracker-queries="stats.tracker_queries"
      />
    </template>
  </Dialog>
</template>

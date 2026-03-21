<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Card from 'primevue/card'
import Skeleton from 'primevue/skeleton'
import SelectButton from 'primevue/selectbutton'
import TimelineChart from '@/components/timeline/TimelineChart.vue'
import DeviceTimelineChart from '@/components/timeline/DeviceTimelineChart.vue'
import { useWindowStore } from '@/stores/window'
import { useScrolled } from '@/composables/useScrolled'
import { apiFetch } from '@/utils/api'
import type { TimelineStats, ClientTimelineStats } from '@/types/api'

const windowStore = useWindowStore()
const scrolled = useScrolled()

const windowOptions = [
  { label: '24h', value: 24 },
  { label: '7d', value: 168 },
]
const selectedWindow = computed({
  get: () => windowOptions.find(o => o.value === windowStore.hours) ?? windowOptions[0],
  set: (v) => { windowStore.hours = v.value },
})

const timeline = ref<TimelineStats | null>(null)
const clientTimeline = ref<ClientTimelineStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function fetchTimeline() {
  loading.value = true
  error.value = null
  try {
    const [timelineRes, clientRes] = await Promise.all([
      apiFetch(`/api/stats/timeline?hours=${windowStore.hours}`),
      apiFetch(`/api/stats/timeline/clients?hours=${windowStore.hours}`),
    ])
    if (!timelineRes.ok || !clientRes.ok) throw new Error('Server error')
    timeline.value = await timelineRes.json()
    clientTimeline.value = await clientRes.json()
  } catch {
    error.value = 'Failed to load timeline data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

const totalQueries = computed(() => {
  if (!timeline.value) return 0
  return timeline.value.buckets.reduce((sum, b) => sum + b.total, 0)
})

const totalBlocked = computed(() => {
  if (!timeline.value) return 0
  return timeline.value.buckets.reduce((sum, b) => sum + b.blocked, 0)
})

const blockRate = computed(() => {
  if (totalQueries.value === 0) return '0.0'
  return ((totalBlocked.value / totalQueries.value) * 100).toFixed(1)
})

onMounted(fetchTimeline)
watch(() => windowStore.hours, fetchTimeline)
watch(() => windowStore.refreshKey, fetchTimeline)
</script>

<template>
  <div class="p-6 space-y-6">

    <!-- Header row -->
    <div class="flex items-center justify-between sticky-header" :class="{ scrolled }">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Query Timeline</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          Tracker query volume over the last {{ selectedWindow.label }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <SelectButton
          v-model="selectedWindow"
          :options="windowOptions"
          option-label="label"
          :allow-empty="false"
          :size="scrolled ? 'small' : undefined"
        />
      </div>
    </div>

    <!-- Auto-refresh error (shown over existing data) -->
    <div v-if="error && timeline" class="text-sm text-red-500 text-right -mb-4">{{ error }}</div>

    <!-- Loading skeletons -->
    <template v-if="loading && !timeline">
      <div class="grid grid-cols-3 gap-4">
        <Card v-for="i in 3" :key="i">
          <template #content>
            <div class="text-center space-y-2">
              <Skeleton width="4rem" height="1.8rem" class="mx-auto" />
              <Skeleton width="6rem" height="0.9rem" class="mx-auto" />
            </div>
          </template>
        </Card>
      </div>
      <Card>
        <template #title><Skeleton width="8rem" height="1.2rem" /></template>
        <template #content>
          <Skeleton width="100%" height="16rem" />
        </template>
      </Card>
    </template>

    <!-- Error -->
    <div v-else-if="error && !timeline" class="flex items-center justify-center py-24">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Timeline content -->
    <template v-if="timeline">

      <!-- Summary stats -->
      <div class="grid grid-cols-3 gap-4">
        <Card>
          <template #content>
            <div class="text-center">
              <p class="text-2xl font-semibold text-gray-900 dark:text-gray-100">{{ totalQueries.toLocaleString() }}</p>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Total Queries</p>
            </div>
          </template>
        </Card>
        <Card>
          <template #content>
            <div class="text-center">
              <p class="text-2xl font-semibold text-red-500">{{ totalBlocked.toLocaleString() }}</p>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Blocked</p>
            </div>
          </template>
        </Card>
        <Card>
          <template #content>
            <div class="text-center">
              <p class="text-2xl font-semibold text-gray-900 dark:text-gray-100">{{ blockRate }}%</p>
              <p class="text-sm text-gray-500 dark:text-gray-400 mt-1">Block Rate</p>
            </div>
          </template>
        </Card>
      </div>

      <!-- Chart -->
      <Card>
        <template #title>Query Volume</template>
        <template #subtitle>
          {{ selectedWindow.value === 24 ? 'Hourly' : '6-hour' }} buckets — {{ selectedWindow.label }}
        </template>
        <template #content>
          <p v-if="timeline.buckets.length === 0" class="py-8 text-center text-gray-400 dark:text-gray-500">No query data for this time window</p>
          <TimelineChart
            v-else
            :buckets="timeline.buckets"
            :bucket-seconds="timeline.bucket_seconds"
          />
        </template>
      </Card>

      <!-- Device activity chart -->
      <Card v-if="clientTimeline && clientTimeline.clients.length > 0">
        <template #title>Device Activity</template>
        <template #subtitle>
          Query volume by device — {{ selectedWindow.label }}
        </template>
        <template #content>
          <DeviceTimelineChart
            :clients="clientTimeline.clients"
            :bucket-seconds="clientTimeline.bucket_seconds"
          />
        </template>
      </Card>

    </template>
  </div>
</template>

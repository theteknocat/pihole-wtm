<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Card from 'primevue/card'
import Skeleton from 'primevue/skeleton'
import TimelineChart from '@/components/timeline/TimelineChart.vue'
import DeviceTimelineChart from '@/components/timeline/DeviceTimelineChart.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { useWindowStore } from '@/stores/window'
import { apiFetch } from '@/utils/api'
import type { TimelineStats, ClientTimelineStats } from '@/types/api'

const windowStore = useWindowStore()

const timeline = ref<TimelineStats | null>(null)
const clientTimeline = ref<ClientTimelineStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function fetchTimeline() {
  loading.value = true
  error.value = null
  try {
    const qs = windowStore.queryParams()
    const [timelineRes, clientRes] = await Promise.all([
      apiFetch(`/api/stats/timeline?${qs}`),
      apiFetch(`/api/stats/timeline/clients?${qs}`),
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

/** Human-readable bucket label based on the bucket size returned by the backend */
const bucketLabel = computed(() => {
  if (!timeline.value) return ''
  const secs = timeline.value.bucket_seconds
  if (secs <= 3600) return 'Hourly'
  if (secs <= 6 * 3600) return '6-hour'
  if (secs <= 24 * 3600) return 'Daily'
  return `${Math.round(secs / 86400)}-day`
})

onMounted(fetchTimeline)
watch(() => windowStore.hours, fetchTimeline)
watch(() => windowStore.endTs, fetchTimeline)
watch(() => windowStore.refreshKey, fetchTimeline)
</script>

<template>
  <div class="p-4 md:p-6 space-y-6">

    <PageHeader
      icon="pi pi-chart-line"
      title="Query Timeline"
    />

    <!-- Auto-refresh error (shown over existing data) -->
    <div v-if="error && timeline" class="text-sm text-red-500 text-right -mb-4">{{ error }}</div>

    <!-- Loading skeletons -->
    <template v-if="loading && !timeline">
      <Card>
        <template #content>
          <div class="flex items-center gap-6">
            <Skeleton shape="circle" size="6rem" class="shrink-0" />
            <div class="flex-1 space-y-3">
              <div class="space-y-1">
                <Skeleton width="8rem" height="1.8rem" />
                <Skeleton width="5rem" height="0.9rem" />
              </div>
              <Skeleton width="100%" height="0.5rem" />
              <div class="space-y-1">
                <Skeleton width="6rem" height="1.5rem" />
                <Skeleton width="4rem" height="0.9rem" />
              </div>
            </div>
          </div>
        </template>
      </Card>
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
      <Card>
        <template #content>
          <div class="flex flex-wrap items-center justify-center gap-6">
            <!-- Total queries + blocked bar -->
            <div class="flex flex-col gap-2 text-center">
              <div>
                <p class="text-xl font-semibold text-red-500">{{ totalBlocked.toLocaleString() }} <span class="text-xs font-light text-gray-700 dark:text-gray-300">blocked</span></p>
              </div>
              <div class="h-0 w-full rounded-full border-b border-b-gray-700 dark:border-b-gray-400" />
              <div>
                <p class="text-xl font-semibold text-gray-900 dark:text-gray-300">{{ totalQueries.toLocaleString() }} <span class="text-xs font-light text-gray-700 dark:text-gray-300">total</span></p>
              </div>
            </div>
            <!-- Block rate ring -->
            <div class="shrink-0 flex flex-col items-center gap-1">
              <div class="relative" style="width: 96px; height: 96px">
                <svg width="96" height="96" viewBox="0 0 100 100" class="-rotate-90">
                  <circle cx="50" cy="50" r="40" fill="none" stroke-width="10" class="stroke-gray-200 dark:stroke-gray-700" />
                  <circle
                    cx="50" cy="50" r="40" fill="none" stroke-width="10"
                    stroke-linecap="round"
                    class="stroke-red-500 transition-all duration-500"
                    :stroke-dasharray="251.33"
                    :stroke-dashoffset="251.33 * (1 - Number(blockRate) / 100)"
                  />
                </svg>
                <div class="absolute inset-0 flex items-center justify-center">
                  <span class="text-lg font-semibold text-gray-900 dark:text-gray-100">{{ blockRate }}%</span>
                </div>
              </div>
            </div>
          </div>
        </template>
      </Card>

      <!-- Chart -->
      <Card>
        <template #title>{{ bucketLabel }} Volume</template>
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
        <template #title>Device Volume</template>
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

<script setup lang="ts">
/**
 * DeviceTimelineChart — stacked area chart showing per-device query volume.
 *
 * Top devices (up to MAX_DEVICES) each get a colour from a categorical palette.
 * Remaining devices are grouped into a grey "Other" series. Uses the same
 * direct Chart.js mutation pattern as TimelineChart for smooth transitions.
 */
import { ref, computed, watch, shallowRef } from 'vue'
import PvChart from 'primevue/chart'
import { useDark } from '@vueuse/core'
import type { ClientTimelineEntry } from '@/types/api'

const MAX_DEVICES = 10

// Categorical palette — 10 visually distinct colours that work on both
// light and dark backgrounds. Ordered for maximum contrast between neighbours.
const PALETTE = [
  'rgba(59, 130, 246, 0.85)',   // blue
  'rgba(249, 115, 22, 0.85)',   // orange
  'rgba(139, 92, 246, 0.85)',   // violet
  'rgba(236, 72, 153, 0.85)',   // pink
  'rgba(20, 184, 166, 0.85)',   // teal
  'rgba(245, 158, 11, 0.85)',   // amber
  'rgba(99, 102, 241, 0.85)',   // indigo
  'rgba(16, 185, 129, 0.85)',   // emerald
  'rgba(244, 63, 94, 0.85)',    // rose
  'rgba(168, 85, 247, 0.85)',   // purple
]

const PALETTE_FILL = PALETTE.map(c => c.replace('0.85)', '0.05)'))
const OTHER_COLOR = 'rgba(156, 163, 175, 0.85)'  // gray-400
const OTHER_FILL = 'rgba(156, 163, 175, 0.05)'

const props = defineProps<{
  clients: ClientTimelineEntry[]
  bucketTimestamps: number[]
  bucketSeconds: number
}>()

const isDark = useDark()
const chartRef = ref<InstanceType<typeof PvChart> | null>(null)

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString(undefined, { weekday: 'short' }) + ' ' + time
}

function deviceLabel(c: ClientTimelineEntry): string {
  return c.client_name ?? c.client_ip
}

/** Build the "Other" series by summing all clients beyond the top N. */
function buildOtherBuckets(clients: ClientTimelineEntry[]): number[] {
  if (clients.length <= MAX_DEVICES) return []
  const rest = clients.slice(MAX_DEVICES)
  const len = rest[0]?.counts.length ?? 0
  const sums = new Array<number>(len).fill(0)
  for (const c of rest) {
    for (let i = 0; i < len; i++) {
      sums[i] += c.counts[i] ?? 0
    }
  }
  return sums
}

function buildDatasets(clients: ClientTimelineEntry[]) {
  const top = clients.slice(0, MAX_DEVICES)
  const datasets = []

  const otherData = buildOtherBuckets(clients)
  if (otherData.length > 0) {
    datasets.push({
      label: 'Other',
      data: otherData,
      borderColor: OTHER_COLOR,
      backgroundColor: OTHER_FILL,
      fill: 'origin',
      borderWidth: 2,
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
    })
  }

  for (let i = 0; i < top.length; i++) {
    const c = top[i]
    datasets.push({
      label: deviceLabel(c),
      data: c.counts,
      borderColor: PALETTE[i % PALETTE.length],
      backgroundColor: PALETTE_FILL[i % PALETTE_FILL.length],
      fill: 'origin',
      borderWidth: 2,
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
    })
  }

  return datasets
}

const chartData = shallowRef({
  labels: props.bucketTimestamps.map(formatTime),
  datasets: buildDatasets(props.clients),
})

watch(() => props.clients, (clients) => {
  const instance = chartRef.value?.getChart()
  if (!instance) return

  const newDatasets = buildDatasets(clients)
  instance.data.labels = props.bucketTimestamps.map(formatTime)

  // Resize datasets array to match
  while (instance.data.datasets.length > newDatasets.length) {
    instance.data.datasets.pop()
  }
  for (let i = 0; i < newDatasets.length; i++) {
    if (i < instance.data.datasets.length) {
      Object.assign(instance.data.datasets[i], newDatasets[i])
    } else {
      instance.data.datasets.push(newDatasets[i])
    }
  }
  instance.update()
})

const chartOptions = computed(() => {
  const textColor = isDark.value ? '#e5e7eb' : '#374151'
  const gridColor = isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: { color: textColor },
      },
      tooltip: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        itemSort: (a: any, b: any) => b.raw - a.raw,
        callbacks: {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          label: (ctx: any) => {
            const count = ctx.parsed.y
            if (count === 0) return null
            return ` ${ctx.dataset.label}: ${count.toLocaleString()}`
          },
        },
      },
    },
    scales: {
      x: {
        ticks: {
          color: textColor,
          maxRotation: 45,
          autoSkip: true,
          maxTicksLimit: 12,
        },
        grid: { color: gridColor },
      },
      y: {
        beginAtZero: true,
        ticks: { color: textColor },
        grid: { color: gridColor },
      },
    },
  }
})
</script>

<template>
  <PvChart
    ref="chartRef"
    type="line"
    :data="chartData"
    :options="chartOptions"
    :key="isDark ? 'dark' : 'light'"
    style="height: 400px"
  />
</template>

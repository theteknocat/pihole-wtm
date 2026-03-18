<script setup lang="ts">
/**
 * Timeline line/area chart showing blocked and allowed query volume over time.
 *
 * On data refresh, we update the underlying Chart.js instance directly rather
 * than letting PrimeVue's Chart component destroy and recreate it. This gives
 * smooth value-to-value transitions instead of a jarring redraw from zero.
 * The `:key` on the component still forces a full recreate on dark mode toggle,
 * which is the one case where we actually want a fresh render (colours change).
 */
import { ref, computed, watch, shallowRef } from 'vue'
import Chart from 'primevue/chart'
import { useDark } from '@vueuse/core'
import type { TimelineBucket } from '@/types/api'

const props = defineProps<{
  buckets: TimelineBucket[]
  bucketSeconds: number
}>()

const isDark = useDark()
const chartRef = ref<InstanceType<typeof Chart> | null>(null)

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString(undefined, { weekday: 'short' }) + ' ' + time
}

function buildDatasets(buckets: TimelineBucket[]) {
  return [
    {
      label: 'Blocked',
      data: buckets.map(b => b.blocked),
      borderColor: 'rgba(239, 68, 68, 0.9)',
      backgroundColor: 'rgba(239, 68, 68, 0.15)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
    },
    {
      label: 'Allowed',
      data: buckets.map(b => b.allowed),
      borderColor: 'rgba(34, 197, 94, 0.9)',
      backgroundColor: 'rgba(34, 197, 94, 0.15)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
    },
  ]
}

// shallowRef so PrimeVue's deep watcher doesn't see internal mutations.
// Set once for initial render; subsequent updates go through Chart.js directly.
const chartData = shallowRef({
  labels: props.buckets.map(b => formatTime(b.timestamp)),
  datasets: buildDatasets(props.buckets),
})

// On data refresh, mutate the Chart.js instance directly so it animates
// smoothly between old and new values instead of redrawing from zero.
watch(() => props.buckets, (buckets) => {
  const instance = chartRef.value?.getChart()
  if (!instance) return

  instance.data.labels = buckets.map(b => formatTime(b.timestamp))
  instance.data.datasets[0].data = buckets.map(b => b.blocked)
  instance.data.datasets[1].data = buckets.map(b => b.allowed)
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
        callbacks: {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          label: (ctx: any) => {
            const count = ctx.parsed.y
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
  <Chart
    ref="chartRef"
    type="line"
    :data="chartData"
    :options="chartOptions"
    :key="isDark ? 'dark' : 'light'"
    style="height: 400px"
  />
</template>

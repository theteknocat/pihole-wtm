<script setup lang="ts">
import { computed } from 'vue'
import Chart from 'primevue/chart'
import { useDark } from '@vueuse/core'
import type { TimelineBucket } from '@/types/api'

const props = defineProps<{
  buckets: TimelineBucket[]
  bucketSeconds: number
}>()

const isDark = useDark()

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  if (props.bucketSeconds >= 6 * 3600) {
    // 6-hour buckets: show day + time
    return d.toLocaleDateString(undefined, { weekday: 'short' }) + ' ' +
      d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  }
  // Hourly buckets: just show time
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

const chartData = computed(() => ({
  labels: props.buckets.map(b => formatTime(b.timestamp)),
  datasets: [
    {
      label: 'Blocked',
      data: props.buckets.map(b => b.blocked),
      borderColor: 'rgba(239, 68, 68, 0.9)',
      backgroundColor: 'rgba(239, 68, 68, 0.15)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
    },
    {
      label: 'Allowed',
      data: props.buckets.map(b => b.allowed),
      borderColor: 'rgba(34, 197, 94, 0.9)',
      backgroundColor: 'rgba(34, 197, 94, 0.15)',
      fill: true,
      tension: 0.3,
      pointRadius: 0,
      pointHitRadius: 8,
    },
  ],
}))

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
    type="line"
    :data="chartData"
    :options="chartOptions"
    :key="isDark ? 'dark' : 'light'"
    style="height: 400px"
  />
</template>

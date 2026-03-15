<script setup lang="ts">
import { computed } from 'vue'
import { useDark } from '@vueuse/core'
import Chart from 'primevue/chart'
import type { CompanyStat } from '@/types/api'

const props = defineProps<{
  data: CompanyStat[]
  totalTrackerQueries: number
}>()

const isDark = useDark()

const top = computed(() =>
  [...props.data].sort((a, b) => b.query_count - a.query_count).slice(0, 15)
)

const pct = (n: number) =>
  props.totalTrackerQueries > 0 ? (n / props.totalTrackerQueries) * 100 : 0

const chartData = computed(() => ({
  labels: top.value.map(c => c.company_name),
  datasets: [
    {
      label: 'Blocked',
      data: top.value.map(c => c.blocked_count),
      backgroundColor: 'rgba(239, 68, 68, 0.85)',
    },
    {
      label: 'Allowed',
      data: top.value.map(c => c.allowed_count),
      backgroundColor: 'rgba(34, 197, 94, 0.85)',
    },
  ],
}))

const chartOptions = computed(() => {
  const textColor = isDark.value ? '#e5e7eb' : '#374151'
  const gridColor = isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'
  return {
    indexAxis: 'y' as const,
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom' as const, labels: { color: textColor } },
      tooltip: {
        callbacks: {
          label: (ctx: any) => {
            const count = ctx.parsed.x
            const p = pct(count).toFixed(1)
            return ` ${ctx.dataset.label}: ${count.toLocaleString()} (${p}% of tracker queries)`
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        ticks: { color: textColor },
        grid: { color: gridColor },
      },
      y: { stacked: true, ticks: { color: textColor }, grid: { color: gridColor } },
    },
  }
})
</script>

<template>
  <Chart
    type="bar"
    :data="chartData"
    :options="chartOptions"
    :key="isDark ? 'dark' : 'light'"
    class="h-72"
  />
</template>

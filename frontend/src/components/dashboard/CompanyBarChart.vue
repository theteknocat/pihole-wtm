<script setup lang="ts">
import { computed } from 'vue'
import { useDark } from '@vueuse/core'
import Chart from 'primevue/chart'
import type { CompanyStat } from '@/types/api'
import { niceMax } from '@/utils/chart'

const props = defineProps<{
  data: CompanyStat[]
  totalTrackerQueries: number
}>()

const emit = defineEmits<{ (e: 'select-company', company: string): void }>()

const isDark = useDark()

const top = computed(() =>
  [...props.data].sort((a, b) => b.query_count - a.query_count).slice(0, 15)
)

const chartHeight = computed(() => Math.max(288, top.value.length * 36))


const axisMax = computed(() => niceMax(Math.max(...top.value.map(c => c.query_count), 1)))

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
    {
      label: '_padding',
      data: top.value.map(c => axisMax.value - c.query_count),
      backgroundColor: isDark.value ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)',
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
    onClick: (_: unknown, elements: { index: number }[]) => {
      if (elements.length) emit('select-company', top.value[elements[0].index].company_name)
    },
    onHover: (event: { native: MouseEvent | null }, elements: unknown[]) => {
      if (event.native?.target)
        (event.native.target as HTMLElement).style.cursor = elements.length ? 'pointer' : 'default'
    },
    plugins: {
      legend: {
        position: 'bottom' as const,
        labels: { color: textColor, filter: (item: any) => item.text !== '_padding' },
      },
      tooltip: {
        callbacks: {
          label: (ctx: any) => {
            if (ctx.dataset.label === '_padding') {
              const total = top.value[ctx.dataIndex].query_count
              return ` Total: ${total.toLocaleString()} queries`
            }
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
        max: axisMax.value,
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
    :style="{ height: `${chartHeight}px` }"
  />
</template>

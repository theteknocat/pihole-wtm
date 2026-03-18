<script setup lang="ts">
import { computed, toRef } from 'vue'
import Chart from 'primevue/chart'
import type { CompanyStat } from '@/types/api'
import { useTrackerBarChart } from '@/composables/useTrackerBarChart'

const props = defineProps<{
  data: CompanyStat[]
  totalTrackerQueries: number
}>()

const emit = defineEmits<{ (e: 'select-company', company: string): void }>()

const top = computed(() =>
  [...props.data].sort((a, b) => b.query_count - a.query_count).slice(0, 15)
)

const { isDark, chartHeight, chartData, chartOptions: baseOptions } = useTrackerBarChart({
  items: top,
  totalTrackerQueries: toRef(props, 'totalTrackerQueries'),
  label: c => c.company_name,
  tooltipTitle: c => `${c.company_name} — ${c.query_count.toLocaleString()} queries`,
  rowHeight: 36,
})

const chartOptions = computed(() => ({
  ...baseOptions.value,
  onClick: (_: unknown, elements: { index: number }[]) => {
    if (elements.length) emit('select-company', top.value[elements[0].index].company_name)
  },
  onHover: (event: { native: MouseEvent | null }, elements: unknown[]) => {
    if (event.native?.target)
      (event.native.target as HTMLElement).style.cursor = elements.length ? 'pointer' : 'default'
  },
}))
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

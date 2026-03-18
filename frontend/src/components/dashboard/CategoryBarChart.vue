<script setup lang="ts">
import { computed, toRef } from 'vue'
import Chart from 'primevue/chart'
import type { CategoryStat } from '@/types/api'
import { formatCategory } from '@/utils/format'
import { useTrackerBarChart } from '@/composables/useTrackerBarChart'

const props = defineProps<{
  data: CategoryStat[]
  totalTrackerQueries: number
}>()

const emit = defineEmits<{ (e: 'select-category', category: string): void }>()

const sorted = computed(() =>
  [...props.data].sort((a, b) => b.query_count - a.query_count)
)

const { isDark, chartRef, chartHeight, chartData, chartOptions: baseOptions } = useTrackerBarChart({
  items: sorted,
  totalTrackerQueries: toRef(props, 'totalTrackerQueries'),
  label: c => formatCategory(c.category),
  tooltipTitle: c => `${formatCategory(c.category)} — ${c.query_count.toLocaleString()} queries`,
  rowHeight: 40,
})

const chartOptions = computed(() => ({
  ...baseOptions.value,
  onClick: (_: unknown, elements: { index: number }[]) => {
    if (elements.length) emit('select-category', sorted.value[elements[0].index].category)
  },
  onHover: (event: { native: MouseEvent | null }, elements: unknown[]) => {
    if (event.native?.target)
      (event.native.target as HTMLElement).style.cursor = elements.length ? 'pointer' : 'default'
  },
}))
</script>

<template>
  <Chart
    ref="chartRef"
    type="bar"
    :data="chartData"
    :options="chartOptions"
    :key="isDark ? 'dark' : 'light'"
    :style="{ height: `${chartHeight}px` }"
  />
</template>

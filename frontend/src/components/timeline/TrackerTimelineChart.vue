<script setup lang="ts">
/**
 * TrackerTimelineChart — stacked bar or line/area chart showing tracker query
 * volume by category or company over time.
 *
 * Accepts all series from the backend. The top MAX_SERIES by total count get
 * individual colours from PALETTE; any remainder is collapsed into a grey
 * "Other" series. Uses the same direct Chart.js mutation pattern as
 * DeviceTimelineChart for smooth transitions on data refresh.
 *
 * A Bar/Line toggle lets the user switch between a stacked bar chart and a
 * line/area chart. chartData is rebuilt synchronously (flush:'sync') before
 * PrimeVue's async watcher fires, so the recreated instance always gets
 * type-appropriate datasets.
 */
import { ref, computed, watch, shallowRef } from 'vue'
import PvChart from 'primevue/chart'
import SelectButton from 'primevue/selectbutton'
import { useDark } from '@vueuse/core'
import type { TrackerTimelineSeries } from '@/types/api'

type ChartType = 'bar' | 'line'

const MAX_SERIES = 10

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
const OTHER_COLOR = 'rgba(156, 163, 175, 0.85)'  // gray-400

const chartTypeOptions: { label: string; value: ChartType }[] = [
  { label: 'Bar', value: 'bar' },
  { label: 'Line', value: 'line' },
]
const selectedChartType = ref<ChartType>('bar')

const props = defineProps<{
  series: TrackerTimelineSeries[]
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

/** Sort series by total descending, split into top-N and the rest. */
function splitSeries(series: TrackerTimelineSeries[]) {
  const sorted = [...series].sort(
    (a, b) => b.counts.reduce((s, n) => s + n, 0) - a.counts.reduce((s, n) => s + n, 0),
  )
  return { top: sorted.slice(0, MAX_SERIES), rest: sorted.slice(MAX_SERIES) }
}

function buildOtherCounts(rest: TrackerTimelineSeries[]): number[] {
  if (!rest.length) return []
  const len = rest[0].counts.length
  const sums = new Array<number>(len).fill(0)
  for (const s of rest) {
    for (let i = 0; i < len; i++) sums[i] += s.counts[i] ?? 0
  }
  return sums
}

function lineDataset(label: string, data: number[], color: string) {
  return {
    label,
    data,
    borderColor: color.replace('0.85', '0.9'),
    backgroundColor: color.replace('0.85', '0.1'),
    fill: 'origin',
    tension: 0.3,
    pointRadius: 0,
    pointHitRadius: 8,
    borderWidth: 2,
  }
}

function buildDatasets(series: TrackerTimelineSeries[], type: ChartType) {
  const { top, rest } = splitSeries(series)
  const datasets = []

  // Other goes first so it sits at the bottom of the stack (bar) / back of render (line)
  const otherCounts = buildOtherCounts(rest)
  if (otherCounts.length > 0 && otherCounts.some(n => n > 0)) {
    if (type === 'bar') {
      datasets.push({
        label: 'Other',
        data: otherCounts,
        backgroundColor: OTHER_COLOR,
        borderColor: OTHER_COLOR,
        borderWidth: 0,
      })
    } else {
      datasets.push(lineDataset('Other', otherCounts, OTHER_COLOR))
    }
  }

  for (let i = 0; i < top.length; i++) {
    const color = PALETTE[i % PALETTE.length]
    if (type === 'bar') {
      datasets.push({
        label: top[i].label,
        data: top[i].counts,
        backgroundColor: color,
        borderColor: color,
        borderWidth: 0,
      })
    } else {
      datasets.push(lineDataset(top[i].label, top[i].counts, color))
    }
  }

  return datasets
}

const chartData = shallowRef({
  labels: props.bucketTimestamps.map(formatTime),
  datasets: buildDatasets(props.series, 'bar'),
})

// Rebuild datasets synchronously so they're ready before PrimeVue's async
// watcher fires to reinit the Chart.js instance for the new type.
watch(selectedChartType, (type) => {
  chartData.value = {
    labels: props.bucketTimestamps.map(formatTime),
    datasets: buildDatasets(props.series, type),
  }
}, { flush: 'sync' })

watch(
  () => [props.series, props.bucketTimestamps] as const,
  ([series, timestamps]) => {
    const type = selectedChartType.value
    const instance = chartRef.value?.getChart()
    if (!instance) {
      chartData.value = {
        labels: timestamps.map(formatTime),
        datasets: buildDatasets(series, type),
      }
      return
    }

    const newDatasets = buildDatasets(series, type)
    instance.data.labels = timestamps.map(formatTime)

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
  },
)

const chartOptions = computed(() => {
  const textColor = isDark.value ? '#e5e7eb' : '#374151'
  const gridColor = isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'
  const isBar = selectedChartType.value === 'bar'
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
        stacked: isBar,
        ticks: {
          color: textColor,
          maxRotation: 45,
          autoSkip: true,
          maxTicksLimit: 12,
        },
        grid: { color: gridColor },
      },
      y: {
        stacked: isBar,
        beginAtZero: true,
        ticks: { color: textColor },
        grid: { color: gridColor },
      },
    },
  }
})
</script>

<template>
  <div>
    <div class="flex justify-end mb-2">
      <SelectButton
        v-model="selectedChartType"
        :options="chartTypeOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
      />
    </div>
    <PvChart
      ref="chartRef"
      :type="selectedChartType"
      :data="chartData"
      :options="chartOptions"
      :key="isDark ? 'dark' : 'light'"
      style="height: 400px"
    />
  </div>
</template>

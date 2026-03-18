import { computed, ref, shallowRef, watch, type Ref } from 'vue'
import { useDark } from '@vueuse/core'
import type Chart from 'primevue/chart'

interface BarStat {
  query_count: number
  blocked_count: number
  allowed_count: number
}

interface TrackerBarChartConfig<T extends BarStat> {
  /** Sorted/filtered data to display. */
  items: Ref<T[]>
  /** Total tracker queries for percentage calculation. */
  totalTrackerQueries: Ref<number>
  /** Extract the display label for a row. */
  label: (item: T) => string
  /** Extract the tooltip title for a row. */
  tooltipTitle: (item: T) => string
  /** Pixels per row for dynamic chart height. */
  rowHeight?: number
  /** Minimum chart height in pixels. */
  minHeight?: number
}

export function useTrackerBarChart<T extends BarStat>(config: TrackerBarChartConfig<T>) {
  const isDark = useDark()

  const {
    items,
    totalTrackerQueries,
    label,
    tooltipTitle,
    rowHeight = 38,
    minHeight = 288,
  } = config

  const chartHeight = computed(() => Math.max(minHeight, items.value.length * rowHeight))

  const pct = (n: number) =>
    totalTrackerQueries.value > 0 ? (n / totalTrackerQueries.value) * 100 : 0

  // Template ref — components bind this to the PrimeVue Chart via ref="chartRef"
  const chartRef = ref<InstanceType<typeof Chart> | null>(null)

  // shallowRef so PrimeVue's deep watcher doesn't see internal mutations.
  // Set once for initial render; subsequent updates go through Chart.js directly.
  const chartData = shallowRef({
    labels: items.value.map(label),
    datasets: [
      {
        label: 'Blocked',
        data: items.value.map(c => c.blocked_count),
        backgroundColor: 'rgba(239, 68, 68, 0.85)',
      },
      {
        label: 'Allowed',
        data: items.value.map(c => c.allowed_count),
        backgroundColor: 'rgba(34, 197, 94, 0.85)',
      },
    ],
  })

  // On data refresh, mutate the Chart.js instance directly for smooth transitions.
  // Falls back to replacing the shallowRef if the instance isn't ready yet
  // (e.g. during initial render before the canvas is mounted).
  watch(items, (newItems) => {
    const instance = chartRef.value?.getChart()
    if (instance) {
      instance.data.labels = newItems.map(label)
      instance.data.datasets[0].data = newItems.map(c => c.blocked_count)
      instance.data.datasets[1].data = newItems.map(c => c.allowed_count)
      instance.update()
    } else {
      // No chart instance yet — update the shallowRef for initial render
      chartData.value = {
        labels: newItems.map(label),
        datasets: [
          { ...chartData.value.datasets[0], data: newItems.map(c => c.blocked_count) },
          { ...chartData.value.datasets[1], data: newItems.map(c => c.allowed_count) },
        ],
      }
    }
  })

  const chartOptions = computed(() => {
    const textColor = isDark.value ? '#e5e7eb' : '#374151'
    const gridColor = isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'
    return {
      indexAxis: 'y' as const,
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index' as const,
        axis: 'y' as const,
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
            title: (tipItems: any[]) => {
              if (!tipItems.length) return ''
              return tooltipTitle(items.value[tipItems[0].dataIndex])
            },
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            label: (ctx: any) => {
              const count = ctx.parsed.x
              if (count === 0) return null
              const p = pct(count).toFixed(1)
              return ` ${ctx.dataset.label}: ${count.toLocaleString()} (${p}%)`
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

  return { isDark, chartRef, chartHeight, chartData, chartOptions }
}

import { computed, type Ref } from 'vue'
import { useDark } from '@vueuse/core'

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

  const chartData = computed(() => ({
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
  }))

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

  return { isDark, chartHeight, chartData, chartOptions }
}

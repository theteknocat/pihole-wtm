import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'

const AUTO_REFRESH_SECONDS = 30

/** Period options offered in the UI. Values are in hours. */
export const PERIOD_OPTIONS = [
  { label: '24h', value: 24 },
  { label: '7d', value: 168 },
  { label: '30d', value: 720 },
  { label: '90d', value: 2160 },
] as const

export const useWindowStore = defineStore('window', () => {
  const hours = ref(24)
  const refreshKey = ref(0)

  // null = "now" (live window), number = fixed end timestamp (historical)
  const endTs = ref<number | null>(null)

  // Data range from the health endpoint — set by AppFooter or wherever health is fetched
  const oldestTs = ref<number | null>(null)
  const newestTs = ref<number | null>(null)

  const stored = localStorage.getItem('reportGroupBy')
  const reportGroupBy = ref<'domain' | 'client'>(
    stored === 'client' ? 'client' : 'domain'
  )
  let intervalId: ReturnType<typeof setInterval> | null = null

  /** Whether the user is viewing a historical (non-live) window */
  const isHistorical = computed(() => endTs.value !== null)

  /** The effective end timestamp (defaults to now when live) */
  const effectiveEndTs = computed(() => endTs.value ?? Date.now() / 1000)

  /** Start timestamp of the current window */
  const fromTs = computed(() => effectiveEndTs.value - hours.value * 3600)

  /** Available period options based on how much data we actually have */
  const availablePeriods = computed(() => {
    if (oldestTs.value == null || newestTs.value == null) {
      // No data info yet — show first two options by default
      return PERIOD_OPTIONS.slice(0, 2)
    }
    const dataSpanHours = (newestTs.value - oldestTs.value) / 3600
    return PERIOD_OPTIONS.filter(opt => {
      // Show a period if data covers at least 25% of it
      return dataSpanHours >= opt.value * 0.25
    })
  })

  /** Whether navigating back is possible (there's older data to see) */
  const canGoPrev = computed(() => {
    if (oldestTs.value == null) return false
    return fromTs.value > oldestTs.value
  })

  /** Whether navigating forward is possible (not already at the latest) */
  const canGoNext = computed(() => endTs.value !== null)

  function triggerRefresh() { refreshKey.value = 1 - refreshKey.value }

  function startAutoRefresh() {
    if (intervalId) return
    intervalId = setInterval(triggerRefresh, AUTO_REFRESH_SECONDS * 1000)
  }

  function stopAutoRefresh() {
    if (intervalId) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  /** Navigate backward by the current window size */
  function goPrev() {
    endTs.value = fromTs.value
  }

  /** Navigate forward by the current window size */
  function goNext() {
    if (endTs.value === null) return
    const newEnd = endTs.value + hours.value * 3600
    const now = Date.now() / 1000
    // If the new end is at or past now, snap back to live mode
    if (newEnd >= now) {
      endTs.value = null
    } else {
      endTs.value = newEnd
    }
  }

  /** Jump back to live (latest) view */
  function goLatest() {
    endTs.value = null
  }

  /** Update data range info (call when health data is fetched) */
  function setDataRange(oldest: number | null, newest: number | null) {
    oldestTs.value = oldest
    newestTs.value = newest
  }

  watch(reportGroupBy, (v) => localStorage.setItem('reportGroupBy', v))

  // Start immediately — runs for the lifetime of the app
  startAutoRefresh()

  /** Build a query string fragment like "hours=24" or "hours=24&end_ts=1234" */
  function queryParams(extra?: Record<string, string | number | boolean | null | undefined>): string {
    const params = new URLSearchParams()
    params.set('hours', String(hours.value))
    if (endTs.value !== null) params.set('end_ts', String(endTs.value))
    if (extra) {
      for (const [k, v] of Object.entries(extra)) {
        if (v != null && v !== '') params.set(k, String(v))
      }
    }
    return params.toString()
  }

  return {
    hours, refreshKey, endTs, reportGroupBy,
    oldestTs, newestTs,
    isHistorical, effectiveEndTs, fromTs,
    availablePeriods, canGoPrev, canGoNext,
    triggerRefresh, startAutoRefresh, stopAutoRefresh,
    goPrev, goNext, goLatest, setDataRange, queryParams,
  }
})

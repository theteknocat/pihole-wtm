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

  // How many periods back from the latest data (0 = live)
  const periodsBack = ref(0)

  // Data range from the health endpoint — set by wherever health is fetched
  const oldestTs = ref<number | null>(null)
  const newestTs = ref<number | null>(null)

  let intervalId: ReturnType<typeof setInterval> | null = null

  /** Whether the user is viewing a historical (non-live) window */
  const isHistorical = computed(() => periodsBack.value > 0)

  /** The effective end timestamp — derived from newestTs and periodsBack */
  const effectiveEndTs = computed(() => {
    const base = newestTs.value ?? Date.now() / 1000
    return base - periodsBack.value * hours.value * 3600
  })

  /** Start timestamp of the current window */
  const fromTs = computed(() => effectiveEndTs.value - hours.value * 3600)

  /**
   * The end_ts value for API queries — null when live (let backend use now),
   * or the computed end timestamp when viewing a historical window.
   */
  const endTs = computed(() => isHistorical.value ? effectiveEndTs.value : null)

  /** Available period options based on how much data we actually have */
  const availablePeriods = computed(() => {
    if (oldestTs.value == null || newestTs.value == null) {
      // No data info yet — show first two options by default
      return PERIOD_OPTIONS.slice(0, 2)
    }
    const dataSpanHours = (newestTs.value - oldestTs.value) / 3600
    const filtered = PERIOD_OPTIONS.filter(opt => {
      // Show a period if data covers at least 25% of it
      return dataSpanHours >= opt.value * 0.25
    })
    // Always include at least the smallest period
    return filtered.length > 0 ? filtered : [PERIOD_OPTIONS[0]]
  })

  /** Whether navigating back is possible (there's older data to see) */
  const canGoPrev = computed(() => {
    if (oldestTs.value == null) return false
    return fromTs.value > oldestTs.value
  })

  /** Whether navigating forward is possible (not already at the latest) */
  const canGoNext = computed(() => periodsBack.value > 0)

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

  /** Navigate backward by one period */
  function goPrev() {
    periodsBack.value++
  }

  /** Navigate forward by one period */
  function goNext() {
    if (periodsBack.value > 0) periodsBack.value--
  }

  /** Jump to the oldest available data */
  function goOldest() {
    if (oldestTs.value == null || newestTs.value == null) return
    const totalSpan = newestTs.value - oldestTs.value
    const periodSeconds = hours.value * 3600
    periodsBack.value = Math.floor(totalSpan / periodSeconds)
  }

  /** Jump back to live (latest) view */
  function goLatest() {
    periodsBack.value = 0
  }

  /** Update data range info (call when health data is fetched) */
  function setDataRange(oldest: number | null, newest: number | null) {
    oldestTs.value = oldest
    newestTs.value = newest
  }

  // Reset to live when changing period — "1 period back" means something
  // completely different at 24h vs 7d
  watch(hours, () => { periodsBack.value = 0 })

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
    hours, refreshKey, endTs,
    oldestTs, newestTs,
    isHistorical, effectiveEndTs, fromTs,
    availablePeriods, canGoPrev, canGoNext,
    triggerRefresh, startAutoRefresh, stopAutoRefresh,
    goPrev, goNext, goOldest, goLatest, setDataRange, queryParams,
  }
})

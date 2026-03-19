import { ref, watch } from 'vue'
import { defineStore } from 'pinia'

const AUTO_REFRESH_SECONDS = 30

export const useWindowStore = defineStore('window', () => {
  const hours = ref(24)
  const refreshKey = ref(0)
  const stored = localStorage.getItem('reportGroupBy')
  const reportGroupBy = ref<'domain' | 'client'>(
    stored === 'client' ? 'client' : 'domain'
  )
  let intervalId: ReturnType<typeof setInterval> | null = null

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

  watch(reportGroupBy, (v) => localStorage.setItem('reportGroupBy', v))

  // Start immediately — runs for the lifetime of the app
  startAutoRefresh()

  return { hours, refreshKey, reportGroupBy, triggerRefresh, startAutoRefresh, stopAutoRefresh }
})

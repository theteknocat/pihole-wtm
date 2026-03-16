import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useWindowStore = defineStore('window', () => {
  const hours = ref(24)
  const refreshKey = ref(0)

  function triggerRefresh() { refreshKey.value++ }

  return { hours, refreshKey, triggerRefresh }
})

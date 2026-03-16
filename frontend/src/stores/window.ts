import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useWindowStore = defineStore('window', () => {
  const hours = ref(24)
  return { hours }
})

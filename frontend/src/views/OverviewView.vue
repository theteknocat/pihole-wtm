<script setup lang="ts">
import { ref, onMounted } from 'vue'

const health = ref<{ status: string; pihole_mode: string; version: string } | null>(null)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    const res = await fetch('/api/health')
    health.value = await res.json()
  } catch (e) {
    error.value = 'Could not reach backend'
  }
})
</script>

<template>
  <div class="flex flex-col items-center justify-center min-h-screen gap-6">
    <h1 class="text-4xl font-bold tracking-tight">pihole-wtm</h1>
    <p class="text-gray-400 text-lg">Pi-hole enriched with tracker intelligence</p>

    <div v-if="health" class="bg-gray-900 border border-gray-700 rounded-xl p-6 text-sm font-mono space-y-1">
      <p><span class="text-green-400">status:</span> {{ health.status }}</p>
      <p><span class="text-blue-400">pihole_mode:</span> {{ health.pihole_mode }}</p>
      <p><span class="text-purple-400">version:</span> {{ health.version }}</p>
    </div>

    <p v-else-if="error" class="text-red-400">{{ error }}</p>
    <p v-else class="text-gray-500">Connecting to backend...</p>
  </div>
</template>

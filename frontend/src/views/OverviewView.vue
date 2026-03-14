<script setup lang="ts">
import { ref, onMounted } from 'vue'

const health = ref<{ status: string; pihole_api_url: string; version: string } | null>(null)
const pihole = ref<{ connected: boolean; version?: string; error?: string } | null>(null)
const backendError = ref<string | null>(null)

onMounted(async () => {
  try {
    const res = await fetch('/api/health')
    health.value = await res.json()
  } catch {
    backendError.value = 'Could not reach backend'
  }

  try {
    const res = await fetch('/api/pihole/test')
    pihole.value = await res.json()
  } catch {
    pihole.value = { connected: false, error: 'Could not reach Pi-hole' }
  }
})
</script>

<template>
  <div class="flex flex-col items-center justify-center min-h-screen gap-6">
    <h1 class="text-4xl font-bold tracking-tight">pihole-wtm</h1>
    <p class="text-gray-400 text-lg">Pi-hole enriched with tracker intelligence</p>

    <div v-if="health || backendError" class="bg-gray-900 border border-gray-700 rounded-xl p-6 text-sm font-mono space-y-2 min-w-64">
      <p v-if="backendError" class="text-red-400">{{ backendError }}</p>
      <template v-else-if="health">
        <p><span class="text-green-400">backend:</span> {{ health.status }}</p>
        <p><span class="text-purple-400">version:</span> {{ health.version }}</p>
      </template>

      <hr class="border-gray-700" />

      <p v-if="!pihole" class="text-gray-500">Checking Pi-hole...</p>
      <template v-else>
        <p>
          <span class="text-blue-400">pi-hole:</span>
          <span :class="pihole.connected ? 'text-green-400' : 'text-red-400'">
            {{ pihole.connected ? ' connected' : ' disconnected' }}
          </span>
        </p>
        <p v-if="pihole.connected && pihole.version">
          <span class="text-blue-400">pi-hole version:</span> {{ pihole.version }}
        </p>
        <p v-if="pihole.error" class="text-red-400 text-xs">{{ pihole.error }}</p>
      </template>
    </div>

    <p v-else class="text-gray-500">Connecting...</p>
  </div>
</template>

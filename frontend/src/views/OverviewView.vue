<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'

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
  <div class="flex flex-col items-center justify-center h-full gap-6 p-6">
    <div class="text-center">
      <h1 class="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100">pihole-wtm</h1>
      <p class="text-gray-500 dark:text-gray-400 text-lg mt-2">Pi-hole enriched with tracker intelligence</p>
    </div>

    <Card class="w-80" :pt="{ root: { class: 'border border-gray-200 dark:border-transparent' } }">
      <template #content>
        <div class="font-mono text-sm space-y-2">
          <p v-if="backendError" class="text-red-400">{{ backendError }}</p>
          <template v-else-if="health">
            <p><span class="text-green-600 dark:text-green-400">backend:</span> {{ health.status }}</p>
            <p><span class="text-purple-600 dark:text-purple-400">version:</span> {{ health.version }}</p>
          </template>
          <p v-else class="text-gray-500">Connecting...</p>

          <hr class="border-gray-200 dark:border-gray-700 my-2" />

          <p v-if="!pihole" class="text-gray-500">Checking Pi-hole...</p>
          <template v-else>
            <p>
              <span class="text-blue-600 dark:text-blue-400">pi-hole:</span>
              <span :class="pihole.connected ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'">
                {{ pihole.connected ? ' connected' : ' disconnected' }}
              </span>
            </p>
            <p v-if="pihole.connected && pihole.version">
              <span class="text-blue-600 dark:text-blue-400">pi-hole version:</span> {{ pihole.version }}
            </p>
            <p v-if="pihole.error" class="text-red-600 dark:text-red-400 text-xs">{{ pihole.error }}</p>
          </template>
        </div>
      </template>
    </Card>

    <Button
      v-if="pihole?.connected"
      label="Open Dashboard"
      icon="pi pi-arrow-right"
      iconPos="right"
      as="router-link"
      to="/dashboard"
    />
  </div>
</template>

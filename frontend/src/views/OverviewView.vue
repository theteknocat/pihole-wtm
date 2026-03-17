<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'

interface SourceStatus {
  name: string
  label: string
  loaded: boolean
  domain_count: number
  category_count?: number
}

interface HealthResponse {
  status: string
  pihole_api_url: string
  version: string
  sources: SourceStatus[]
}

const health = ref<HealthResponse | null>(null)
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
            <div class="flex items-center justify-between">
              <span class="text-purple-600 dark:text-purple-400">Version</span>
              <span class="text-gray-500 dark:text-gray-400">{{ health.version }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-green-600 dark:text-green-400">Backend</span>
              <i class="pi pi-check-circle text-green-600 dark:text-green-400" />
            </div>
          </template>
          <p v-else class="text-gray-500">Connecting...</p>

          <hr class="border-gray-200 dark:border-gray-700 my-2" />

          <p v-if="!pihole" class="text-gray-500">Checking Pi-hole...</p>
          <template v-else>
            <div class="flex items-center justify-between">
              <span class="text-blue-600 dark:text-blue-400">Pi-hole</span>
              <i
                v-if="pihole.connected"
                class="pi pi-check-circle text-green-600 dark:text-green-400"
              />
              <i
                v-else
                v-tooltip.left="pihole.error || 'Cannot reach Pi-hole API'"
                class="pi pi-times-circle text-red-600 dark:text-red-400 cursor-help"
              />
            </div>
            <div v-if="pihole.connected && pihole.version" class="flex items-center justify-between">
              <span class="text-blue-600 dark:text-blue-400">Pi-hole version</span>
              <span class="text-gray-500 dark:text-gray-400">{{ pihole.version }}</span>
            </div>
          </template>

          <template v-if="health?.sources?.length">
            <hr class="border-gray-200 dark:border-gray-700 my-2" />

            <div v-for="source in health.sources" :key="source.name" class="space-y-0.5">
              <div class="flex items-center justify-between">
                <span class="text-amber-600 dark:text-amber-400">{{ source.label }}</span>
                <i
                  v-if="source.loaded"
                  class="pi pi-check-circle text-green-600 dark:text-green-400"
                />
                <i
                  v-else
                  v-tooltip.left="'Source data failed to load'"
                  class="pi pi-times-circle text-red-600 dark:text-red-400 cursor-help"
                />
              </div>
              <p v-if="source.loaded" class="text-gray-500 dark:text-gray-400 text-xs pl-2">
                {{ source.domain_count.toLocaleString() }} domains<span v-if="source.category_count">, {{ source.category_count }} categories</span>
              </p>
            </div>
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

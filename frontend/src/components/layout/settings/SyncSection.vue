<script setup lang="ts">
import { ref, onMounted } from 'vue'
import InputNumber from 'primevue/inputnumber'
import ProgressSpinner from 'primevue/progressspinner'
import { apiFetch } from '@/utils/api'

const emit = defineEmits<{ (e: 'saved'): void }>()

const loading = ref(true)
const syncInterval = ref(60)
const dataRetention = ref(7)

async function saveSetting(key: string, value: number | null) {
  if (value === null) return
  try {
    const res = await apiFetch(`/api/settings/${key}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value }),
    })
    if (!res.ok) throw new Error()
    emit('saved')
  } catch {
    // silent — header could show error too, but keeping it simple for now
  }
}

onMounted(async () => {
  try {
    const res = await apiFetch('/api/settings')
    if (!res.ok) throw new Error()
    const data = await res.json()
    syncInterval.value = data.sync_interval_seconds
    dataRetention.value = data.data_retention_days
  } catch {
    // defaults are fine
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div v-if="loading" class="flex items-center justify-center py-12">
      <ProgressSpinner style="width: 32px; height: 32px" />
    </div>

    <div v-else class="space-y-5">

      <p class="text-xs text-gray-500 dark:text-gray-400">
        Controls how often data is fetched from Pi-hole and how long it is kept.
      </p>

      <!-- Sync interval -->
      <div>
        <label class="text-sm text-gray-700 dark:text-gray-300 mb-1 block">Sync interval</label>
        <InputNumber
          v-model="syncInterval"
          :min="10"
          :max="3600"
          suffix=" seconds"
          class="w-full"
          size="small"
          @update:model-value="saveSetting('sync_interval_seconds', $event)"
        />
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
          How often Pi-hole is polled for new queries. Lower values mean more up-to-date data. (10–3600s)
        </p>
      </div>

      <!-- Data retention -->
      <div>
        <label class="text-sm text-gray-700 dark:text-gray-300 mb-1 block">Data retention</label>
        <InputNumber
          v-model="dataRetention"
          :min="1"
          :max="365"
          suffix=" days"
          class="w-full"
          size="small"
          @update:model-value="saveSetting('data_retention_days', $event)"
        />
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Queries older than this are automatically purged each sync cycle. (1–365 days)
        </p>
      </div>

    </div>
  </div>
</template>

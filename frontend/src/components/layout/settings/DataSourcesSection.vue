<script setup lang="ts">
import { ref, onMounted } from 'vue'
import InputNumber from 'primevue/inputnumber'
import ProgressSpinner from 'primevue/progressspinner'
import { apiFetch } from '@/utils/api'

const emit = defineEmits<{ (e: 'saved'): void }>()

const loading = ref(true)
const trackerdbInterval = ref(24)
const disconnectInterval = ref(24)

// Debounced auto-save
let saveTimer: ReturnType<typeof setTimeout> | null = null

function scheduleSave(key: string, value: number | null) {
  if (saveTimer) clearTimeout(saveTimer)
  if (value === null) return
  saveTimer = setTimeout(() => {
    saveSetting(key, value)
  }, 500)
}

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
    // silent
  }
}

onMounted(async () => {
  try {
    const res = await apiFetch('/api/settings')
    if (!res.ok) throw new Error()
    const data = await res.json()
    trackerdbInterval.value = data.trackerdb_update_interval_hours
    disconnectInterval.value = data.disconnect_update_interval_hours
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
        How often tracker databases are refreshed from their upstream sources. Set to 0 to disable automatic updates.
      </p>

      <!-- TrackerDB interval -->
      <div>
        <label class="text-sm text-gray-700 dark:text-gray-300 mb-1 block">TrackerDB (Ghostery)</label>
        <InputNumber
          v-model="trackerdbInterval"
          :min="0"
          :max="720"
          :step="12"
          suffix=" hours"
          class="w-full"
          size="small"
          showButtons
          buttonLayout="horizontal"
          @update:model-value="scheduleSave('trackerdb_update_interval_hours', $event)"
        >
          <template #incrementicon>
              <span class="pi pi-plus" />
          </template>
          <template #decrementicon>
              <span class="pi pi-minus" />
          </template>
        </InputNumber>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Checks GitHub for new releases. 0 = never update automatically. (0–720h)
        </p>
      </div>

      <!-- Disconnect.me interval -->
      <div>
        <label class="text-sm text-gray-700 dark:text-gray-300 mb-1 block">Disconnect.me</label>
        <InputNumber
          v-model="disconnectInterval"
          :min="0"
          :max="720"
          :step="12"
          suffix=" hours"
          class="w-full"
          size="small"
          showButtons
          buttonLayout="horizontal"
          @update:model-value="scheduleSave('disconnect_update_interval_hours', $event)"
        >
          <template #incrementicon>
              <span class="pi pi-plus" />
          </template>
          <template #decrementicon>
              <span class="pi pi-minus" />
          </template>
        </InputNumber>
        <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Re-downloads tracking protection lists from GitHub. 0 = never. (0–720h)
        </p>
      </div>

    </div>
  </div>
</template>

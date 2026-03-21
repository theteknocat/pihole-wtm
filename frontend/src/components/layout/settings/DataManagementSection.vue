<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import { useWindowStore } from '@/stores/window'
import { apiFetch } from '@/utils/api'

const windowStore = useWindowStore()

// Re-enrich
const reenriching = ref(false)
const reenrichMessage = ref<string | null>(null)

async function doReenrich() {
  reenriching.value = true
  reenrichMessage.value = null
  try {
    const res = await apiFetch('/api/admin/reenrich', { method: 'POST' })
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    const data = await res.json()
    reenrichMessage.value = data.flagged > 0
      ? `${data.flagged} domains queued — will refresh over the next few sync cycles.`
      : 'No domains need re-enrichment.'
    if (data.flagged > 0) windowStore.triggerRefresh()
    setTimeout(() => { reenrichMessage.value = null }, 12000)
  } catch {
    reenrichMessage.value = 'Re-enrichment failed. Please try again.'
  } finally {
    reenriching.value = false
  }
}

// Reset
const resetState = ref<'idle' | 'confirm'>('idle')
const resetting = ref(false)
const resetError = ref<string | null>(null)

async function doReset() {
  resetting.value = true
  resetError.value = null
  try {
    const res = await apiFetch('/api/admin/reset', { method: 'POST' })
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    windowStore.triggerRefresh()
    resetState.value = 'idle'
  } catch {
    resetError.value = 'Reset failed. Please try again.'
    resetState.value = 'idle'
  } finally {
    resetting.value = false
  }
}
</script>

<template>
  <div class="space-y-5">

    <p class="text-xs text-gray-500 dark:text-gray-400">
      Actions for managing stored query data and enrichment results.
    </p>

    <!-- Re-enrich -->
    <div>
      <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Re-enrich Domains</h3>
      <Button
        class="w-full"
        label="Re-enrich"
        icon="pi pi-sync"
        severity="secondary"
        size="small"
        outlined
        :loading="reenriching"
        @click="doReenrich"
      />
      <p v-if="reenrichMessage" class="text-xs mt-2" :class="reenrichMessage.includes('failed') ? 'text-red-500' : 'text-green-600 dark:text-green-400'">
        {{ reenrichMessage }}
      </p>
      <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
        Re-processes domains that used heuristic guesses or failed RDAP lookups.
      </p>
    </div>

    <!-- Reset -->
    <div>
      <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Reset Data</h3>
      <div class="flex gap-1">
        <template v-if="resetState === 'idle'">
          <Button
            class="w-full"
            label="Reset All Data"
            icon="pi pi-trash"
            severity="danger"
            size="small"
            outlined
            @click="resetState = 'confirm'"
          />
        </template>
        <template v-else>
          <Button
            class="flex-1"
            label="Cancel"
            icon="pi pi-times"
            severity="secondary"
            size="small"
            outlined
            :disabled="resetting"
            @click="resetState = 'idle'"
          />
          <Button
            class="flex-1"
            label="Confirm"
            icon="pi pi-trash"
            severity="danger"
            size="small"
            outlined
            :loading="resetting"
            @click="doReset"
          />
        </template>
      </div>
      <p v-if="resetState === 'confirm'" class="text-xs text-amber-500 mt-2">
        Are you sure? All query data will be removed and will take time to rebuild.
      </p>
      <p v-if="resetError" class="text-xs text-red-500 mt-2">{{ resetError }}</p>
      <p class="text-xs text-gray-400 dark:text-gray-500 mt-1">
        Clears all stored queries and domains. Data will resync on the next cycle.
      </p>
    </div>

  </div>
</template>

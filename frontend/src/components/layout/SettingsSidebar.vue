<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import ConfigDialog from './ConfigDialog.vue'
import { useWindowStore } from '@/stores/window'
import { apiFetch } from '@/utils/api'

const emit = defineEmits<{ (e: 'close'): void }>()
const configOpen = ref(false)
const windowStore = useWindowStore()

// Drive enter/exit animations from a single boolean.
// We set it true after mount (so the browser sees the initial off-screen state
// and can transition to on-screen), and false when closing (so the exit
// animation plays before we actually unmount via the parent's v-if).
const visible = ref(false)
onMounted(() => requestAnimationFrame(() => { visible.value = true }))

function close() {
  visible.value = false
  setTimeout(() => emit('close'), 200)
}

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
    close()
  } catch {
    resetError.value = 'Reset failed. Please try again.'
    resetState.value = 'idle'
  } finally {
    resetting.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-40">

    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/20 dark:bg-black/40 transition-opacity duration-200"
      :class="visible ? 'opacity-100' : 'opacity-0'"
      @click="close"
    />

    <!-- Panel -->
    <aside
      class="absolute top-0 right-0 h-full w-72 bg-white dark:bg-stone-900 border-l border-gray-200 dark:border-gray-800 shadow-xl flex flex-col transition-transform duration-200 ease-out"
      :class="visible ? 'translate-x-0' : 'translate-x-full'"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">Settings</span>
        <Button icon="pi pi-times" severity="secondary" text rounded size="small" @click="close" />
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-auto p-4">

        <p class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3">Tracker Sources</p>

        <div>
          <Button
            class="w-full"
            label="Configure Sources"
            icon="pi pi-sliders-h"
            severity="secondary"
            size="small"
            outlined
            @click="configOpen = true"
          />
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Choose which categories, companies, and domains to display.
        </p>

        <p class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mt-6 mb-3">Enrichment</p>

        <div>
          <Button
            class="w-full"
            label="Re-enrich Domains"
            icon="pi pi-sync"
            severity="secondary"
            size="small"
            outlined
            :loading="reenriching"
            @click="doReenrich"
          />
        </div>
        <p v-if="reenrichMessage" class="text-xs mt-2" :class="reenrichMessage.includes('failed') ? 'text-red-500' : 'text-green-600 dark:text-green-400'">
          {{ reenrichMessage }}
        </p>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Re-processes domains that used heuristic guesses or failed RDAP lookups. Existing query data is kept.
        </p>

        <p class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mt-6 mb-3">Query Data</p>

        <div class="flex gap-1">
          <template v-if="resetState === 'idle'">
            <Button
              class="flex-1"
              label="Reset Data"
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
              label="Reset"
              icon="pi pi-trash"
              severity="danger"
              size="small"
              outlined
              :loading="resetting"
              @click="doReset"
            />
          </template>
        </div>
        <p v-if="resetState == 'confirm'" class="text-xs my-2">Are you sure? All data will be removed and it may take some time to rebuild.</p>
        <p v-if="resetError" class="text-xs text-red-500 my-2">{{ resetError }}</p>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-2">
          Clears all stored queries and domains. Data will resync on the next cycle.
        </p>

      </div>
    </aside>

    <ConfigDialog v-if="configOpen" @close="configOpen = false" />
  </div>
</template>

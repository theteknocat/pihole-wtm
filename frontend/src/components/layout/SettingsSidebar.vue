<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import { useWindowStore } from '@/stores/window'

const emit = defineEmits<{ (e: 'close'): void }>()
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

const resetState = ref<'idle' | 'confirm'>('idle')
const resetting = ref(false)

async function doReset() {
  resetting.value = true
  try {
    await fetch('/api/admin/reset', { method: 'POST' })
    windowStore.triggerRefresh()
    close()
  } finally {
    resetting.value = false
    resetState.value = 'idle'
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

        <p class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-3">Data</p>

        <div class="flex items-start justify-between gap-3">
          <div>
            <p class="text-sm font-medium text-gray-900 dark:text-gray-100">Reset sync data</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Clears all stored queries and domains. Data will resync on the next cycle.
            </p>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <template v-if="resetState === 'idle'">
              <Button
                label="Reset"
                severity="danger"
                size="small"
                text
                @click="resetState = 'confirm'"
              />
            </template>
            <template v-else>
              <Button
                label="Cancel"
                severity="secondary"
                size="small"
                text
                :disabled="resetting"
                @click="resetState = 'idle'"
              />
              <Button
                label="Confirm"
                severity="danger"
                size="small"
                :loading="resetting"
                @click="doReset"
              />
            </template>
          </div>
        </div>

      </div>
    </aside>

  </div>
</template>

<script setup lang="ts">
/**
 * ClientNameDialog — modal for setting a friendly name for a client IP address.
 *
 * Opens pre-filled with any existing name. The user can set/update the name, or
 * clear it to remove the mapping. Uses PrimeVue Dialog + InputText.
 */
import { ref } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'

const props = defineProps<{
  clientIp: string
  currentName: string | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', name: string | null): void
}>()

const visible = ref(true)
const name = ref(props.currentName ?? '')
const saving = ref(false)
const error = ref<string | null>(null)

function onHide() {
  emit('close')
}

async function save() {
  saving.value = true
  error.value = null
  const trimmed = name.value.trim()

  try {
    let res: Response
    if (trimmed) {
      res = await fetch(`/api/clients/${encodeURIComponent(props.clientIp)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed }),
      })
    } else {
      // Empty name = remove mapping
      res = await fetch(`/api/clients/${encodeURIComponent(props.clientIp)}`, {
        method: 'DELETE',
      })
    }
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    emit('saved', trimmed || null)
    visible.value = false
  } catch {
    error.value = 'Failed to save. Is the backend reachable?'
  } finally {
    saving.value = false
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') save()
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    header="Set Device Name"
    modal
    :draggable="false"
    :closable="true"
    :style="{ width: 'min(24rem, 90vw)' }"
    @hide="onHide"
  >
    <div class="space-y-4">
      <div>
        <label class="text-sm text-gray-500 dark:text-gray-400 block mb-1">IP Address</label>
        <span class="font-mono text-sm">{{ clientIp }}</span>
      </div>

      <div>
        <label class="text-sm text-gray-500 dark:text-gray-400 block mb-1" for="client-name-input">
          Friendly Name
        </label>
        <InputText
          id="client-name-input"
          v-model="name"
          placeholder="e.g. Living Room TV"
          class="w-full"
          :maxlength="64"
          autofocus
          @keydown="onKeydown"
        />
        <p class="text-xs text-gray-400 mt-1">Leave empty to remove the name.</p>
      </div>

      <p v-if="error" class="text-sm text-red-500">{{ error }}</p>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button label="Cancel" severity="secondary" text @click="visible = false" />
        <Button label="Save" :loading="saving" @click="save" />
      </div>
    </template>
  </Dialog>
</template>

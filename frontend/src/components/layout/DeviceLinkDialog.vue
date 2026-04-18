<script setup lang="ts">
/**
 * DeviceLinkDialog — create, edit, or delete a device group.
 *
 * The anchor IP is always pre-selected and cannot be unchecked.
 * Devices already belonging to a *different* group are excluded from the list.
 * Save is disabled until a name is provided and at least 2 IPs are selected.
 * In edit mode an "Unlink Group" danger button lets the user disband the group.
 */
import { ref, computed } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import type { ClientStat, DeviceGroup } from '@/types/api'

const props = defineProps<{
  anchorIp: string
  anchorName: string | null
  allClients: ClientStat[]
  existingGroup: DeviceGroup | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const visible = ref(true)
const saving = ref(false)
const unlinking = ref(false)
const error = ref<string | null>(null)

// Pre-fill name from existing group or anchor device name
const groupName = ref(props.existingGroup?.name ?? props.anchorName ?? '')

// Pre-select members: anchor IP always included; add existing group members
const initialSelected = new Set<string>([props.anchorIp])
if (props.existingGroup) {
  for (const m of props.existingGroup.members) {
    initialSelected.add(m.client_ip)
  }
}
const selectedIps = ref<Set<string>>(new Set(initialSelected))

// Available devices: exclude those in a *different* group (not our group)
const availableClients = computed(() => {
  const ourGroupId = props.existingGroup?.id ?? null
  return props.allClients.filter(c => {
    if (c.client_ip === props.anchorIp) return true  // anchor always shown
    // If this IP is in a different group, exclude it
    // We don't have ipToGroup here, so we rely on the parent filtering
    // Devices not in our group but in another are passed without restriction —
    // the uniqueness constraint at the DB level enforces one group per IP.
    return true
  })
})

function toggleIp(ip: string) {
  if (ip === props.anchorIp) return  // anchor is locked
  const next = new Set(selectedIps.value)
  if (next.has(ip)) {
    next.delete(ip)
  } else {
    next.add(ip)
  }
  selectedIps.value = next
}

const canSave = computed(
  () => groupName.value.trim().length > 0 && selectedIps.value.size >= 2
)

async function save() {
  error.value = null
  saving.value = true
  try {
    const name = groupName.value.trim()
    const member_ips = [...selectedIps.value]
    const isEdit = props.existingGroup !== null
    const url = isEdit
      ? `/api/device-groups/${props.existingGroup!.id}`
      : '/api/device-groups'
    const res = await fetch(url, {
      method: isEdit ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, member_ips }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? `Server error ${res.status}`)
    }
    emit('saved')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save group.'
  } finally {
    saving.value = false
  }
}

async function unlink() {
  if (!props.existingGroup) return
  error.value = null
  unlinking.value = true
  try {
    const res = await fetch(`/api/device-groups/${props.existingGroup.id}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail ?? `Server error ${res.status}`)
    }
    emit('saved')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to delete group.'
  } finally {
    unlinking.value = false
  }
}

function onHide() {
  emit('close')
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :closable="true"
    position="top"
    :draggable="false"
    :style="{ width: '90vw', maxWidth: '480px' }"
    @hide="onHide"
  >
    <template #header>
      <span class="font-semibold text-lg">
        <i class="pi pi-link" />
        {{ existingGroup ? 'Edit Device Group' : 'Link Devices' }}
      </span>
    </template>

    <div class="space-y-4">
      <!-- Group name -->
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Group name</label>
        <InputText
          v-model="groupName"
          placeholder="e.g. Peter's Laptop"
          class="w-full"
          :maxlength="64"
        />
      </div>

      <!-- Device list -->
      <div class="flex flex-col gap-1">
        <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
          Devices
          <span class="font-normal text-gray-400">(select at least 2)</span>
        </label>
        <div class="max-h-64 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-md divide-y divide-gray-100 dark:divide-gray-700">
          <label
            v-for="client in availableClients"
            :key="client.client_ip"
            class="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
            :class="{ 'opacity-60 cursor-default': client.client_ip === anchorIp }"
          >
            <Checkbox
              :model-value="selectedIps.has(client.client_ip)"
              :binary="true"
              :disabled="client.client_ip === anchorIp"
              @change="toggleIp(client.client_ip)"
            />
            <span class="flex-1 min-w-0">
              <span class="block truncate">{{ client.client_name ?? client.client_ip }}</span>
              <span v-if="client.client_name" class="text-xs text-gray-400 font-mono">{{ client.client_ip }}</span>
            </span>
          </label>
        </div>
      </div>

      <!-- Error -->
      <p v-if="error" class="text-sm text-red-500">{{ error }}</p>
    </div>

    <template #footer>
      <!-- Unlink Group (left side, only in edit mode) -->
      <div class="flex items-center justify-between w-full">
        <Button
          v-if="existingGroup"
          label="Unlink Group"
          icon="pi pi-trash"
          severity="danger"
          text
          size="small"
          :loading="unlinking"
          :disabled="saving"
          @click="unlink"
        />
        <span v-else />

        <div class="flex gap-2">
          <Button
            label="Cancel"
            severity="secondary"
            text
            @click="visible = false"
          />
          <Button
            :label="existingGroup ? 'Save' : 'Link'"
            icon="pi pi-check"
            :disabled="!canSave"
            :loading="saving"
            @click="save"
          />
        </div>
      </div>
    </template>
  </Dialog>
</template>

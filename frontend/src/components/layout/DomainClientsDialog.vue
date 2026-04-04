<script setup lang="ts">
/**
 * DomainClientsDialog — modal showing per-device query breakdown for a single domain.
 *
 * Displays a table of devices that queried the domain within the current time
 * window, with allowed and blocked counts for each. Clicking a device name
 * navigates to the Devices Report filtered to that device.
 */
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Dialog from 'primevue/dialog'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import ClientNameDialog from '@/components/layout/ClientNameDialog.vue'
import { useWindowStore } from '@/stores/window'
import type { ClientStats, ClientStat } from '@/types/api'

const props = defineProps<{
  domain: string
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const router = useRouter()
const windowStore = useWindowStore()
const visible = ref(true)
const stats = ref<ClientStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const editingClient = ref<ClientStat | null>(null)

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const qs = windowStore.queryParams({ domain: props.domain })
    const res = await fetch(`/api/stats/clients?${qs}`)
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    stats.value = await res.json()
  } catch {
    error.value = 'Failed to load device breakdown.'
  } finally {
    loading.value = false
  }
}

function onClientSaved(client: ClientStat, newName: string | null) {
  client.client_name = newName
  editingClient.value = null
  windowStore.triggerRefresh()
}

function inspectDevice(clientIp: string) {
  visible.value = false
  router.push({ path: '/domains-report', query: { client_ip: clientIp } })
}

function onHide() {
  emit('close')
}

onMounted(fetchStats)
watch(() => windowStore.refreshKey, fetchStats)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :closable="true"
    position="top"
    :draggable="false"
    :style="{ width: '90vw', maxWidth: '700px' }"
    @hide="onHide"
  >
    <template #header>
      <span class="font-semibold text-lg font-mono">{{ domain }}</span>
    </template>

    <!-- Subtitle -->
    <p class="text-sm text-gray-500 dark:text-gray-400 mb-4">
      {{ windowStore.availablePeriods.find(o => o.value === windowStore.hours)?.label ?? `${windowStore.hours}h` }} window
      — device breakdown
    </p>

    <!-- Loading -->
    <div v-if="loading && !stats" class="flex flex-col items-center justify-center py-16 gap-4 text-gray-500 dark:text-gray-400">
      <ProgressSpinner />
      <p>Loading…</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="flex items-center justify-center py-16">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Table -->
    <DataTable
      v-if="stats"
      :value="stats.clients"
      sort-field="query_count"
      :sort-order="-1"
      striped-rows
      class="text-sm"
    >
      <template #empty>
        <p class="empty-state">No devices found for this domain</p>
      </template>
      <Column field="client_ip" header="Device" style="min-width: 10rem">
        <template #body="{ data: row }">
          <div class="flex items-center gap-2">
            <Button
              icon="pi pi-pencil"
              severity="secondary"
              text
              rounded
              size="small"
              class="!w-6 !h-6"
              title="Edit device name"
              aria-label="Edit device name"
              @click="editingClient = row"
            />
            <span class="block">
              <a
                href="#device-details"
                @click.prevent="inspectDevice(row.client_ip)"
              >{{ row.client_name ?? row.client_ip }}</a>
              <span v-if="row.client_name" class="text-xs block text-gray-400 font-mono">{{ row.client_ip }}</span>
            </span>
          </div>
        </template>
      </Column>
      <Column field="allowed_count" header="Allowed" sortable style="text-align: right">
        <template #body="{ data: row }">
          <span class="text-allowed">{{ row.allowed_count.toLocaleString() }}</span>
        </template>
      </Column>
      <Column field="blocked_count" header="Blocked" sortable style="text-align: right">
        <template #body="{ data: row }">
          <span class="text-blocked">{{ row.blocked_count.toLocaleString() }}</span>
        </template>
      </Column>
      <Column field="query_count" header="Total" sortable style="text-align: right" />
    </DataTable>
  </Dialog>

  <ClientNameDialog
    v-if="editingClient"
    :client-ip="editingClient.client_ip"
    :current-name="editingClient.client_name"
    @close="editingClient = null"
    @saved="onClientSaved(editingClient!, $event)"
  />
</template>

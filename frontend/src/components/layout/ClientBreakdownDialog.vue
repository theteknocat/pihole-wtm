<script setup lang="ts">
/**
 * ClientBreakdownDialog — modal showing per-device query breakdown for a
 * domain, category, or company.
 *
 * Devices that belong to a linked group appear as a single merged row with
 * combined stats. The individual member names and IPs are shown inline below
 * the group name. Clicking any device or group name opens DeviceStatsDialog
 * on top rather than navigating away. For category/company filters a
 * "View Domains Report" link lets the user jump straight to the full filtered
 * report.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Dialog from 'primevue/dialog'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import ClientNameDialog from '@/components/layout/ClientNameDialog.vue'
import DeviceStatsDialog from '@/components/layout/DeviceStatsDialog.vue'
import { useWindowStore } from '@/stores/window'
import { useDeviceGroups } from '@/composables/useDeviceGroups'
import type { TableRow } from '@/composables/useDeviceGroups'
import { formatCategory } from '@/utils/format'
import type { ClientStats, ClientStat, ClientFilter } from '@/types/api'

const props = defineProps<{
  filter: ClientFilter
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const router = useRouter()
const windowStore = useWindowStore()
const visible = ref(true)
const stats = ref<ClientStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const editingClient = ref<ClientStat | null>(null)

const title = computed(() => {
  switch (props.filter.type) {
    case 'category': return formatCategory(props.filter.value)
    default: return props.filter.value
  }
})

const icon = computed(() => {
  switch (props.filter.type) {
    case 'domain': return 'pi pi-globe'
    case 'category': return 'pi pi-tags'
    default: return 'pi pi-building'
  }
})

// ---- Device groups ----------------------------------------------------------

const clients = computed(() => stats.value?.clients ?? [])
const { fetchGroups, tableRows } = useDeviceGroups(clients)

// ---- Device stats dialog (opens on top of this dialog) ----------------------

const inspectingDevice = ref<{ clientIps: string[]; clientName: string | null } | null>(null)

function openDeviceStats(clientIps: string[], clientName: string | null) {
  inspectingDevice.value = { clientIps, clientName }
}

function inspectRow(row: TableRow) {
  if (row._type === 'group') {
    openDeviceStats(row.group.members.map(m => m.client_ip), row.group.name)
  } else {
    openDeviceStats([row.client_ip], row.client_name)
  }
}

// ---- Data fetch -------------------------------------------------------------

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const qs = windowStore.queryParams({ [props.filter.type]: props.filter.value })
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

function viewFullReport() {
  visible.value = false
  router.push({
    path: '/domains-report',
    query: { [props.filter.type]: props.filter.value },
  })
}

function onHide() {
  emit('close')
}

onMounted(async () => {
  await Promise.all([fetchStats(), fetchGroups()])
})
watch(() => windowStore.refreshKey, () => {
  fetchStats()
  fetchGroups()
})
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
      <span class="font-semibold text-lg"><i :class="icon" /> {{ title }} — Device Breakdown</span>
    </template>

    <!-- Subtitle + report link -->
    <div class="flex items-center justify-between mb-4">
      <p class="text-sm text-gray-500 dark:text-gray-400">
        Past {{ windowStore.availablePeriods.find(o => o.value === windowStore.hours)?.label ?? `${windowStore.hours}h` }}
      </p>
      <Button
        v-if="filter.type !== 'domain'"
        :label="'See all ' + title + ' Domains'"
        icon="pi pi-external-link"
        severity="secondary"
        text
        size="small"
        @click="viewFullReport"
      />
    </div>

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
      :value="tableRows"
      data-key="_key"
      sort-field="query_count"
      :sort-order="-1"
      striped-rows
      class="text-sm"
    >
      <template #empty>
        <p class="empty-state">No devices found</p>
      </template>
      <Column header="Device" style="min-width: 10rem">
        <template #body="{ data: row }">
          <!-- Group row: link icon + group name + member list -->
          <div v-if="row._type === 'group'" class="flex items-center gap-2">
            <span class="flex items-center justify-center flex-shrink-0 text-gray-400" style="width: 1.5rem; height: 1.5rem">
              <i class="pi pi-link text-sm" />
            </span>
            <span class="block">
              <a
                href="#device-stats"
                v-tooltip.top="'Tracker breakdown'"
                @click.prevent="inspectRow(row)"
              >{{ row.group.name }}</a>
              <span
                v-for="member in row.member_stats"
                :key="member.client_ip"
                class="text-xs flex gap-1 text-gray-400"
              >
                <span>{{ member.client_name ?? member.client_ip }}</span>
                <span v-if="member.client_name" class="font-mono">{{ member.client_ip }}</span>
              </span>
            </span>
          </div>

          <!-- Single row: pencil + name -->
          <div v-else class="flex items-center gap-2">
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
                href="#device-stats"
                v-tooltip.top="'Tracker breakdown'"
                @click.prevent="inspectRow(row)"
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

  <!-- Device stats dialog — opens on top of this dialog -->
  <DeviceStatsDialog
    v-if="inspectingDevice"
    :client-ips="inspectingDevice.clientIps"
    :client-name="inspectingDevice.clientName"
    @close="inspectingDevice = null"
    @navigate="visible = false"
  />
</template>

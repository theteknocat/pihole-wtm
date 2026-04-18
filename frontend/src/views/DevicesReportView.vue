<script setup lang="ts">
/**
 * DevicesReportView — query breakdown grouped by client device.
 *
 * Filters: category, company. Includes inline name editing and
 * device stats inspection via dialogs. Grouped devices (linked by
 * the user) appear as a single expandable row with combined stats.
 * Expanding a group reveals a nested table whose columns are aligned
 * with the parent table via matching fixed column widths.
 */
import { ref, computed, onMounted, watch } from 'vue'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import ClientNameDialog from '@/components/layout/ClientNameDialog.vue'
import DeviceStatsDialog from '@/components/layout/DeviceStatsDialog.vue'
import DeviceLinkDialog from '@/components/layout/DeviceLinkDialog.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { formatCategory } from '@/utils/format'
import { useReportData } from '@/composables/useReportData'
import { useDeviceGroups } from '@/composables/useDeviceGroups'
import type { GroupRow } from '@/composables/useDeviceGroups'
import { useWindowStore } from '@/stores/window'
import type { ClientStats, ClientStat } from '@/types/api'

const windowStore = useWindowStore()

const {
  data, loading, error, hasFilters,
  selectedCategory, selectedCompany,
  categoryOptions, companyOptions,
  resetFilters,
} = useReportData('client')

const clientData = computed(() => data.value as ClientStats | null)

// ---- Device groups ----------------------------------------------------------

const clients = computed(() => clientData.value?.clients ?? [])
const { fetchGroups, ipToGroup, tableRows } = useDeviceGroups(clients)

onMounted(fetchGroups)
watch(() => windowStore.refreshKey, fetchGroups)

// ---- Expansion --------------------------------------------------------------

const expandedRows = ref<Record<string, boolean>>({})

function toggleRow(key: string) {
  const next = { ...expandedRows.value }
  if (next[key]) {
    delete next[key]
  } else {
    next[key] = true
  }
  expandedRows.value = next
}

// ---- Dialogs ----------------------------------------------------------------

const editingClient = ref<ClientStat | null>(null)
const inspectingClient = ref<ClientStat | null>(null)
const inspectingGroup = ref<GroupRow | null>(null)
const linkingClient = ref<ClientStat | null>(null)

function onClientSaved(client: ClientStat, newName: string | null) {
  client.client_name = newName
  editingClient.value = null
  windowStore.triggerRefresh()
}

function onGroupSaved() {
  linkingClient.value = null
  windowStore.triggerRefresh()
}
</script>

<template>
  <div class="p-4 md:p-6 space-y-6">
    <PageHeader
      icon="pi pi-mobile"
      title="Devices Report"
    />

    <!-- Filters -->
    <div class="flex items-start gap-3 flex-wrap">
      <Select
        v-model="selectedCategory"
        :options="categoryOptions"
        placeholder="All categories"
        filter
        showClear
        class="w-full md:w-64"
      >
        <template #value="{ value }">
          {{ value ? formatCategory(value) : 'All categories' }}
        </template>
        <template #option="{ option }">
          {{ formatCategory(option) }}
        </template>
      </Select>

      <Select
        v-model="selectedCompany"
        :options="companyOptions"
        placeholder="All companies"
        filter
        showClear
        class="w-full md:w-64"
      />

      <Button
        v-if="hasFilters"
        label="Reset all"
        icon="pi pi-filter-slash"
        severity="secondary"
        text
        size="small"
        @click="resetFilters"
      />
    </div>

    <!-- Refresh error -->
    <div v-if="error && clientData" class="error-banner">{{ error }}</div>

    <!-- Loading skeleton -->
    <Card v-if="loading && !clientData">
      <template #content>
        <div class="space-y-4">
          <div v-for="i in 8" :key="i" class="flex gap-4">
            <Skeleton width="14rem" height="1.2rem" />
            <Skeleton width="6rem" height="1.2rem" />
            <Skeleton width="6rem" height="1.2rem" />
            <Skeleton width="4rem" height="1.2rem" />
          </div>
        </div>
      </template>
    </Card>

    <!-- Error -->
    <div v-else-if="error && !clientData" class="flex items-center justify-center py-24">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Client table -->
    <Card v-if="clientData">
      <template #content>
        <DataTable
          :value="tableRows"
          v-model:expandedRows="expandedRows"
          data-key="_key"
          :rows="50"
          paginator
          :rows-per-page-options="[25, 50, 100]"
          sort-field="query_count"
          :sort-order="-1"
          striped-rows
          class="text-sm"
        >
          <template #empty>
            <p class="empty-state">
              {{ hasFilters ? 'No devices match your filters' : 'No device data for this time window' }}
            </p>
          </template>

          <!-- Expander/link column:
               groups → chevron to expand/collapse
               singles → link button to create a group
               Both actions are vertically aligned. -->
          <Column style="width: 3rem; padding-right: 0">
            <template #body="{ data: row }">
              <Button
                v-if="row._type === 'group'"
                :icon="expandedRows[row._key] ? 'pi pi-chevron-down' : 'pi pi-chevron-right'"
                severity="contrast"
                variant="text"
                rounded
                size="small"
                class="!p-2"
                :aria-label="expandedRows[row._key] ? 'Collapse' : 'Expand'"
                @click="toggleRow(row._key)"
              />
              <Button
                v-else
                icon="pi pi-link"
                severity="secondary"
                variant="text"
                rounded
                size="small"
                class="!p-2"
                aria-label="Link devices"
                v-tooltip.top="'Link devices into a group'"
                @click="linkingClient = row"
              />
            </template>
          </Column>

          <!-- Device column (flexible — absorbs remaining width).
               Pencil buttons for all rows are vertically aligned. -->
          <Column field="client_name" header="Device" sortable>
            <template #body="{ data: row }">
              <!-- Group row: pencil opens group editor; link icon labels the member count -->
              <div v-if="row._type === 'group'" class="flex items-center gap-2">
                <Button
                  icon="pi pi-pencil"
                  severity="secondary"
                  variant="text"
                  rounded
                  size="small"
                  class="!p-2"
                  aria-label="Edit device group"
                  v-tooltip.top="'Edit device group'"
                  @click="linkingClient = row.member_stats[0] ?? null"
                />
                <span class="block">
                  <a
                    href="#group-details"
                    v-tooltip.top="'Tracker breakdown'"
                    @click.prevent="inspectingGroup = row"
                  >{{ row.group.name }}</a>
                  <span class="text-xs flex items-center gap-1 text-gray-400">
                    <i class="pi pi-link" />
                    {{ row.group.members.length }} devices
                  </span>
                </span>
              </div>

              <!-- Single row: pencil opens name editor -->
              <div v-else class="flex items-center gap-2">
                <Button
                  icon="pi pi-pencil"
                  severity="secondary"
                  variant="text"
                  rounded
                  size="small"
                  class="!p-2"
                  aria-label="Edit device name"
                  v-tooltip.top="'Edit device name'"
                  @click="editingClient = row"
                />
                <span class="block">
                  <a
                    href="#client-details"
                    v-tooltip.top="'Tracker breakdown'"
                    @click.prevent="inspectingClient = row"
                  >{{ row.client_name ?? row.client_ip }}</a>
                  <span v-if="row.client_name" class="text-xs block text-gray-400 font-mono">{{ row.client_ip }}</span>
                </span>
              </div>
            </template>
          </Column>

          <Column field="query_count" header="Total" sortable style="width: 5.5rem; text-align: right" />

          <Column field="blocked_count" header="Blocked" sortable style="width: 6.5rem">
            <template #body="{ data: row }">
              <span class="text-blocked">{{ row.blocked_count.toLocaleString() }}</span>
            </template>
          </Column>

          <Column field="allowed_count" header="Allowed" sortable style="width: 6.5rem">
            <template #body="{ data: row }">
              <span class="text-allowed">{{ row.allowed_count.toLocaleString() }}</span>
            </template>
          </Column>

          <Column field="block_rate" header="Block rate" sortable style="width: 6.5rem">
            <template #body="{ data: row }">
              {{ row.block_rate }}%
            </template>
          </Column>

          <!-- Expansion: nested table with matching column widths, no headers -->
          <template #expansion="{ data: row }">
            <table v-if="row._type === 'group'" class="member-table">
              <colgroup>
                <!-- Must match parent Column widths exactly -->
                <col style="width: 3rem" />    <!-- expander spacer -->
                <col />                         <!-- device (flexible) -->
                <col style="width: 5.5rem" />  <!-- total -->
                <col style="width: 6.5rem" />  <!-- blocked -->
                <col style="width: 6.5rem" />  <!-- allowed -->
                <col style="width: 6.5rem" />  <!-- block rate -->
              </colgroup>
              <tbody>
                <tr v-for="member in row.member_stats" :key="member.client_ip">
                  <td></td>
                  <td>
                    <div class="flex items-center gap-2">
                      <Button
                        icon="pi pi-pencil"
                        severity="secondary"
                        variant="text"
                        rounded
                        size="small"
                        class="!p-2"
                        aria-label="Edit device name"
                        v-tooltip.top="'Edit device name'"
                        @click="editingClient = member"
                      />
                      <span class="block">
                        <a
                          href="#client-details"
                          v-tooltip.top="'Tracker breakdown'"
                          @click.prevent="inspectingClient = member"
                        >{{ member.client_name ?? member.client_ip }}</a>
                        <span v-if="member.client_name" class="text-xs block text-gray-400 font-mono">{{ member.client_ip }}</span>
                      </span>
                    </div>
                  </td>
                  <td style="text-align: right">{{ member.query_count.toLocaleString() }}</td>
                  <td><span class="text-blocked">{{ member.blocked_count.toLocaleString() }}</span></td>
                  <td><span class="text-allowed">{{ member.allowed_count.toLocaleString() }}</span></td>
                  <td>{{ member.block_rate }}%</td>
                </tr>
              </tbody>
            </table>
          </template>
        </DataTable>
      </template>
    </Card>

    <!-- Client name edit dialog -->
    <ClientNameDialog
      v-if="editingClient"
      :client-ip="editingClient.client_ip"
      :current-name="editingClient.client_name"
      @close="editingClient = null"
      @saved="(name) => onClientSaved(editingClient!, name)"
    />

    <!-- Device stats dialog — group -->
    <DeviceStatsDialog
      v-if="inspectingGroup"
      :client-ips="inspectingGroup.group.members.map(m => m.client_ip)"
      :client-name="inspectingGroup.group.name"
      @close="inspectingGroup = null"
    />

    <!-- Device stats dialog — single -->
    <DeviceStatsDialog
      v-if="inspectingClient"
      :client-ips="[inspectingClient.client_ip]"
      :client-name="inspectingClient.client_name"
      @close="inspectingClient = null"
    />

    <!-- Device link dialog -->
    <DeviceLinkDialog
      v-if="linkingClient"
      :anchor-ip="linkingClient.client_ip"
      :anchor-name="linkingClient.client_name"
      :all-clients="clientData?.clients ?? []"
      :existing-group="ipToGroup.get(linkingClient.client_ip) ?? null"
      @close="linkingClient = null"
      @saved="onGroupSaved"
    />
  </div>
</template>

<style scoped>
/* Fixed table layout so explicit Column widths are honoured exactly,
   which is required for the nested member table to align its columns. */
:deep(.p-datatable-table) {
  table-layout: fixed;
}

/* Zero out the expansion cell's padding so the inner table sits flush
   with the parent table's left edge and matches its full width. */
:deep(.p-datatable-row-expansion > td) {
  padding: 0;
}

/* PrimeVue stripes even rows via nth-child. The expansion <tr> is always
   the next sibling after its parent, so it's always at the opposite parity.
   Invert the rule for expansion rows so they match the parent row's stripe. */
:deep(.p-datatable-striped .p-datatable-row-expansion:nth-child(even)) {
  background: transparent;
}
:deep(.p-datatable-striped .p-datatable-row-expansion:nth-child(odd)) {
  background: var(--p-datatable-row-striped-background);
}

/* Member table: inherit full width, use same fixed layout, no borders. */
.member-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
}

/* Cells: match parent horizontal padding (1rem), reduce vertical,
   slight size reduction and opacity to read as subordinate rows. */
.member-table td {
  padding: 0.3rem 1rem;
  font-size: 0.8125rem;
  opacity: 0.85;
}
</style>

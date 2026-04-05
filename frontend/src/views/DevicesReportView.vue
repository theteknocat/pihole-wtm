<script setup lang="ts">
/**
 * DevicesReportView — query breakdown grouped by client device.
 *
 * Filters: category, company. Includes inline name editing and
 * device stats inspection via dialogs.
 */
import { ref, computed } from 'vue'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import ClientNameDialog from '@/components/layout/ClientNameDialog.vue'
import DeviceStatsDialog from '@/components/layout/DeviceStatsDialog.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { formatCategory } from '@/utils/format'
import { useReportData } from '@/composables/useReportData'
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

const editingClient = ref<ClientStat | null>(null)
const inspectingClient = ref<ClientStat | null>(null)

function onClientSaved(client: ClientStat, newName: string | null) {
  client.client_name = newName
  editingClient.value = null
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
          :value="clientData.clients"
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
          <Column field="client_name" header="Device" sortable style="min-width: 14rem">
            <template #body="{ data: row }">
              <div class="flex items-center gap-2">
                <Button
                  icon="pi pi-pencil"
                  severity="contrast"
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
          <Column field="query_count" header="Total" sortable style="text-align: right" />
          <Column field="blocked_count" header="Blocked" sortable>
            <template #body="{ data: row }">
              <span class="text-blocked">
                {{ row.blocked_count.toLocaleString() }}
              </span>
            </template>
          </Column>
          <Column field="allowed_count" header="Allowed" sortable>
            <template #body="{ data: row }">
              <span class="text-allowed">
                {{ row.allowed_count.toLocaleString() }}
              </span>
            </template>
          </Column>
          <Column field="block_rate" header="Block rate" sortable>
            <template #body="{ data: row }">
              {{ row.block_rate }}%
            </template>
          </Column>
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

    <!-- Device stats dialog -->
    <DeviceStatsDialog
      v-if="inspectingClient"
      :client-ip="inspectingClient.client_ip"
      :client-name="inspectingClient.client_name"
      @close="inspectingClient = null"
    />
  </div>
</template>

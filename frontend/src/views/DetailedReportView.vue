<script setup lang="ts">
/**
 * DetailedReportView — query breakdown grouped by domain or by client device.
 *
 * A toggle switches between domain grouping (with category/company filters)
 * and client grouping (with inline name editing via a pencil button).
 * The grouping selection is stored in the window store so it persists
 * across navigation. Filters are synced to URL query params.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import ProgressSpinner from 'primevue/progressspinner'
import Button from 'primevue/button'
import ClientNameDialog from '@/components/layout/ClientNameDialog.vue'
import DeviceStatsDialog from '@/components/layout/DeviceStatsDialog.vue'
import { useWindowStore } from '@/stores/window'
import { formatCategory } from '@/utils/format'
import type { DomainStats, ClientStats, ClientStat } from '@/types/api'

const route = useRoute()
const router = useRouter()
const windowStore = useWindowStore()

// Time window toggle
const windowOptions = [
  { label: '24h', value: 24 },
  { label: '7d', value: 168 },
]
const selectedWindow = computed({
  get: () => windowOptions.find(o => o.value === windowStore.hours) ?? windowOptions[0],
  set: (v) => { windowStore.hours = v.value },
})

// Group-by toggle — persisted in store
const groupByOptions = [
  { label: 'Domains', value: 'domain' as const },
  { label: 'Devices', value: 'client' as const },
]
const selectedGroupBy = computed({
  get: () => groupByOptions.find(o => o.value === windowStore.reportGroupBy) ?? groupByOptions[0],
  set: (v) => { windowStore.reportGroupBy = v.value },
})

// Domain mode: filter state — initialised from URL query params
const selectedCategory = ref<string | null>((route.query.category as string) ?? null)
const selectedCompany = ref<string | null>((route.query.company as string) ?? null)
const selectedClientIp = ref<string | null>((route.query.client_ip as string) ?? null)
const categoryOptions = ref<string[]>([])
const companyOptions = ref<string[]>([])

interface ClientOption {
  client_ip: string
  client_name: string | null
  query_count: number
}
const clientOptions = ref<ClientOption[]>([])

const hasFilters = computed(() =>
  selectedCategory.value != null || selectedCompany.value != null ||
  (windowStore.reportGroupBy === 'domain' && selectedClientIp.value != null)
)

// Data state
const domainData = ref<DomainStats | null>(null)
const clientData = ref<ClientStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// Client name editing and device stats inspection
const editingClient = ref<ClientStat | null>(null)
const inspectingClient = ref<ClientStat | null>(null)

function syncUrlParams() {
  const query: Record<string, string> = {}
  if (selectedCategory.value) query.category = selectedCategory.value
  if (selectedCompany.value) query.company = selectedCompany.value
  if (selectedClientIp.value) query.client_ip = selectedClientIp.value
  router.replace({ path: '/detailed-report', query })
}

async function fetchOptions() {
  try {
    const [configRes, clientsRes] = await Promise.all([
      fetch('/api/config/options'),
      fetch('/api/clients'),
    ])
    const configJson = await configRes.json()
    categoryOptions.value = configJson.categories ?? []
    companyOptions.value = configJson.companies ?? []
    const clientsJson = await clientsRes.json()
    clientOptions.value = clientsJson.clients ?? []
  } catch (e) {
    console.warn('Failed to fetch filter options:', e)
  }
}

async function fetchData() {
  loading.value = true
  error.value = null
  try {
    if (windowStore.reportGroupBy === 'client') {
      const params = new URLSearchParams({ hours: String(windowStore.hours) })
      if (selectedCategory.value) params.set('category', selectedCategory.value)
      if (selectedCompany.value) params.set('company', selectedCompany.value)
      const res = await fetch(`/api/stats/clients?${params}`)
      clientData.value = await res.json()
    } else {
      const params = new URLSearchParams({ hours: String(windowStore.hours) })
      if (selectedCategory.value) params.set('category', selectedCategory.value)
      if (selectedCompany.value) params.set('company', selectedCompany.value)
      if (selectedClientIp.value) params.set('client_ip', selectedClientIp.value)
      const res = await fetch(`/api/stats/domains?${params}`)
      domainData.value = await res.json()
    }
  } catch {
    error.value = 'Failed to load data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  selectedCategory.value = null
  selectedCompany.value = null
  selectedClientIp.value = null
}

function onClientSaved(client: ClientStat, newName: string | null) {
  // Update the local data immediately so the table reflects the change
  client.client_name = newName
  editingClient.value = null
  windowStore.triggerRefresh()
}

const hasData = computed(() =>
  windowStore.reportGroupBy === 'client' ? clientData.value != null : domainData.value != null
)

onMounted(async () => {
  await fetchOptions()
  await fetchData()
})

watch(() => windowStore.hours, fetchData)
watch(() => windowStore.refreshKey, () => {
  if (!editingClient.value) {
    fetchOptions()
    fetchData()
  }
})
watch(() => windowStore.reportGroupBy, fetchData)
watch([selectedCategory, selectedCompany, selectedClientIp], () => {
  syncUrlParams()
  fetchData()
})

// Sync refs when the route query changes externally (e.g. navigation from a modal)
watch(() => route.query, (q) => {
  const cat = (q.category as string) ?? null
  const co = (q.company as string) ?? null
  const ip = (q.client_ip as string) ?? null
  if (cat !== selectedCategory.value) selectedCategory.value = cat
  if (co !== selectedCompany.value) selectedCompany.value = co
  if (ip !== selectedClientIp.value) selectedClientIp.value = ip
})
</script>

<template>
  <div class="p-6 space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">
          {{ windowStore.reportGroupBy === 'client' ? 'Device Report' : 'Domain Report' }}
        </h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          {{ windowStore.reportGroupBy === 'client' ? 'Devices' : 'Domains' }}
          grouped by query count
        </p>
      </div>
      <div class="flex items-center gap-2">
        <SelectButton
          v-model="selectedGroupBy"
          :options="groupByOptions"
          option-label="label"
          :allow-empty="false"
        />
        <SelectButton
          v-model="selectedWindow"
          :options="windowOptions"
          option-label="label"
          :allow-empty="false"
        />
        <Button
          icon="pi pi-refresh"
          severity="secondary"
          text
          rounded
          :loading="loading"
          aria-label="Refresh"
          @click="fetchData()"
        />
      </div>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-3 flex-wrap">
      <Select
        v-model="selectedCategory"
        :options="categoryOptions"
        placeholder="All categories"
        filter
        showClear
        class="w-64"
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
        class="w-64"
      />

      <Select
        v-if="windowStore.reportGroupBy === 'domain'"
        v-model="selectedClientIp"
        :options="clientOptions"
        option-value="client_ip"
        :option-label="(c: ClientOption) => c.client_name ?? c.client_ip"
        placeholder="All devices"
        filter
        showClear
        class="w-64"
      >
        <template #value="{ value }">
          {{ value ? (clientOptions.find(c => c.client_ip === value)?.client_name ?? value) : 'All devices' }}
        </template>
        <template #option="{ option }">
          <span class="block">
            {{ option.client_name ?? option.client_ip }}
            <span v-if="option.client_name" class="text-xs block text-gray-400 font-mono">{{ option.client_ip }}</span>
          </span>
        </template>
      </Select>

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

    <!-- Refresh error (shown over existing data) -->
    <div v-if="error && hasData" class="text-sm text-red-500 text-right -mb-4">{{ error }}</div>

    <!-- Loading -->
    <div v-if="loading && !hasData" class="flex flex-col items-center justify-center py-24 gap-4 text-gray-500 dark:text-gray-400">
      <ProgressSpinner />
      <p>Loading…</p>
    </div>

    <!-- Error -->
    <div v-else-if="error && !hasData" class="flex items-center justify-center py-24">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Domain table -->
    <Card v-if="windowStore.reportGroupBy === 'domain' && domainData">
      <template #content>
        <DataTable
          :value="domainData!.domains"
          :rows="50"
          paginator
          :rows-per-page-options="[25, 50, 100]"
          sort-field="query_count"
          :sort-order="-1"
          striped-rows
          class="text-sm"
        >
          <Column field="domain" header="Domain" sortable style="min-width: 14rem">
            <template #body="{ data: row }">
              <span class="font-mono text-xs">{{ row.domain }}</span>
            </template>
          </Column>
          <Column field="category" header="Category" sortable>
            <template #body="{ data: row }">
              {{ formatCategory(row.category) }}
            </template>
          </Column>
          <Column field="company_name" header="Company" sortable />
          <Column field="query_count" header="Total" sortable style="text-align: right" />
          <Column field="blocked_count" header="Blocked" sortable>
            <template #body="{ data: row }">
              <span class="text-red-500 dark:text-red-400 font-medium">
                {{ row.blocked_count.toLocaleString() }}
              </span>
            </template>
          </Column>
          <Column field="allowed_count" header="Allowed" sortable>
            <template #body="{ data: row }">
              <span class="text-green-600 dark:text-green-400 font-medium">
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

    <!-- Client table -->
    <Card v-if="windowStore.reportGroupBy === 'client' && clientData">
      <template #content>
        <DataTable
          :value="clientData!.clients"
          :rows="50"
          paginator
          :rows-per-page-options="[25, 50, 100]"
          sort-field="query_count"
          :sort-order="-1"
          striped-rows
          class="text-sm"
        >
          <Column field="client_name" header="Device" sortable style="min-width: 14rem">
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
                    href="#client-details"
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
              <span class="text-red-500 dark:text-red-400 font-medium">
                {{ row.blocked_count.toLocaleString() }}
              </span>
            </template>
          </Column>
          <Column field="allowed_count" header="Allowed" sortable>
            <template #body="{ data: row }">
              <span class="text-green-600 dark:text-green-400 font-medium">
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

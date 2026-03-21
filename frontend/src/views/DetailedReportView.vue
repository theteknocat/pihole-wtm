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
import AutoComplete from 'primevue/autocomplete'
import Checkbox from 'primevue/checkbox'
import InputGroup from 'primevue/inputgroup'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import ClientNameDialog from '@/components/layout/ClientNameDialog.vue'
import DeviceStatsDialog from '@/components/layout/DeviceStatsDialog.vue'
import { useWindowStore } from '@/stores/window'
import { useScrolled } from '@/composables/useScrolled'
import { formatCategory } from '@/utils/format'
import { apiFetch } from '@/utils/api'
import type { DomainStats, ClientStats, ClientStat } from '@/types/api'

const route = useRoute()
const router = useRouter()
const windowStore = useWindowStore()
const scrolled = useScrolled()

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
const domainInput = ref<string | null>((route.query.domain as string) ?? null)
const appliedDomain = ref<string | null>((route.query.domain as string) ?? null)
const domainExact = ref(route.query.domain_exact === '1')
const domainSuggestions = ref<string[]>([])
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
  (windowStore.reportGroupBy === 'domain' && (selectedClientIp.value != null || appliedDomain.value != null))
)

// Data state
const domainData = ref<DomainStats | null>(null)
const clientData = ref<ClientStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let fetchController: AbortController | null = null

// Client name editing and device stats inspection
const editingClient = ref<ClientStat | null>(null)
const inspectingClient = ref<ClientStat | null>(null)

function syncUrlParams() {
  const query: Record<string, string> = {}
  if (selectedCategory.value) query.category = selectedCategory.value
  if (selectedCompany.value) query.company = selectedCompany.value
  if (selectedClientIp.value) query.client_ip = selectedClientIp.value
  if (appliedDomain.value) query.domain = appliedDomain.value
  if (domainExact.value) query.domain_exact = '1'
  router.replace({ path: '/detailed-report', query })
}

async function fetchOptions() {
  try {
    const [configRes, clientsRes] = await Promise.all([
      apiFetch('/api/settings/options'),
      apiFetch('/api/clients'),
    ])
    if (!configRes.ok || !clientsRes.ok) throw new Error('Failed to fetch filter options')
    const configJson = await configRes.json()
    categoryOptions.value = configJson.categories ?? []
    companyOptions.value = configJson.companies ?? []
    const clientsJson = await clientsRes.json()
    clientOptions.value = clientsJson.clients ?? []
  } catch (e) {
    console.warn('Failed to fetch filter options:', e)
  }
}

async function searchDomains(event: { query: string }) {
  if (event.query.length < 2) {
    domainSuggestions.value = []
    return
  }
  try {
    const params = new URLSearchParams({ q: event.query, hours: String(windowStore.hours) })
    const res = await apiFetch(`/api/domains/search?${params}`)
    if (res.ok) domainSuggestions.value = await res.json()
  } catch {
    domainSuggestions.value = []
  }
}

function applyDomainFilter() {
  const val = domainInput.value?.trim() || null
  if (val !== appliedDomain.value) {
    appliedDomain.value = val
  } else {
    // Same value but exact toggle may have changed
    syncUrlParams()
    fetchData()
  }
}

function onDomainSelect(event: { value: string }) {
  domainInput.value = event.value
  appliedDomain.value = event.value
}

function onDomainClear() {
  domainInput.value = null
  appliedDomain.value = null
}

async function fetchData() {
  // Cancel any in-flight request so a stale response can't overwrite fresh data
  fetchController?.abort()
  const controller = new AbortController()
  fetchController = controller

  loading.value = true
  error.value = null
  try {
    if (windowStore.reportGroupBy === 'client') {
      const params = new URLSearchParams({ hours: String(windowStore.hours) })
      if (selectedCategory.value) params.set('category', selectedCategory.value)
      if (selectedCompany.value) params.set('company', selectedCompany.value)
      const res = await apiFetch(`/api/stats/clients?${params}`, { signal: controller.signal })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      clientData.value = await res.json()
    } else {
      const params = new URLSearchParams({ hours: String(windowStore.hours) })
      if (selectedCategory.value) params.set('category', selectedCategory.value)
      if (selectedCompany.value) params.set('company', selectedCompany.value)
      if (selectedClientIp.value) params.set('client_ip', selectedClientIp.value)
      if (appliedDomain.value) {
        params.set('domain', appliedDomain.value)
        if (domainExact.value) params.set('domain_exact', 'true')
      }
      const res = await apiFetch(`/api/stats/domains?${params}`, { signal: controller.signal })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      domainData.value = await res.json()
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return
    error.value = 'Failed to load data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  selectedCategory.value = null
  selectedCompany.value = null
  selectedClientIp.value = null
  domainInput.value = null
  appliedDomain.value = null
  domainExact.value = false
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

onMounted(() => {
  fetchOptions()
  fetchData()
})

watch(() => windowStore.hours, fetchData)
watch(() => windowStore.refreshKey, () => {
  if (!editingClient.value) {
    fetchOptions()
    fetchData()
  }
})
watch(() => windowStore.reportGroupBy, fetchData)
watch([selectedCategory, selectedCompany, selectedClientIp, appliedDomain], () => {
  syncUrlParams()
  fetchData()
})
watch(domainExact, () => {
  if (appliedDomain.value) applyDomainFilter()
})

// Sync refs when the route query changes externally (e.g. navigation from a modal)
watch(() => route.query, (q) => {
  const cat = (q.category as string) ?? null
  const co = (q.company as string) ?? null
  const ip = (q.client_ip as string) ?? null
  const dom = (q.domain as string) ?? null
  const exact = q.domain_exact === '1'
  if (cat !== selectedCategory.value) selectedCategory.value = cat
  if (co !== selectedCompany.value) selectedCompany.value = co
  if (ip !== selectedClientIp.value) selectedClientIp.value = ip
  if (dom !== appliedDomain.value) {
    domainInput.value = dom
    appliedDomain.value = dom
  }
  if (exact !== domainExact.value) domainExact.value = exact
})
</script>

<template>
  <div class="p-6 space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between sticky-header" :class="{ scrolled }">
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
          :size="scrolled ? 'small' : undefined"
        />
        <SelectButton
          v-model="selectedWindow"
          :options="windowOptions"
          option-label="label"
          :allow-empty="false"
          :size="scrolled ? 'small' : undefined"
        />
      </div>
    </div>

    <!-- Filters -->
    <div class="flex items-start gap-3 flex-wrap">
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

      <!-- Domain search (domain mode only) -->
      <div v-if="windowStore.reportGroupBy === 'domain'" class="flex flex-col gap-1">
        <InputGroup class="w-64">
          <AutoComplete
            v-model="domainInput"
            :suggestions="domainSuggestions"
            placeholder="Search domains…"
            :pt="{ pcInputText: { root: { spellcheck: false, autocorrect: 'off', autocapitalize: 'off' } } }"
            @complete="searchDomains"
            @item-select="onDomainSelect"
            @clear="onDomainClear"
            @keydown.enter="applyDomainFilter"
          />
          <Button
            icon="pi pi-search"
            outlined
            aria-label="Search"
            @click="applyDomainFilter"
          />
        </InputGroup>
        <label class="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 cursor-pointer select-none ml-1">
          <Checkbox v-model="domainExact" :binary="true" />
          Exact match
        </label>
      </div>

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

    <!-- Loading skeleton -->
    <Card v-if="loading && !hasData">
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
          <template #empty>
            <p class="py-8 text-center text-gray-400 dark:text-gray-500">
              {{ hasFilters ? 'No domains match your filters' : 'No domain data for this time window' }}
            </p>
          </template>
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
          <template #empty>
            <p class="py-8 text-center text-gray-400 dark:text-gray-500">
              {{ hasFilters ? 'No devices match your filters' : 'No device data for this time window' }}
            </p>
          </template>
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

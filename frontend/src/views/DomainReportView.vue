<script setup lang="ts">
/**
 * DomainReportView — per-domain query breakdown with filterable category/company dropdowns.
 *
 * Filters are synced to URL query params so links are bookmarkable and the back button
 * preserves state. PrimeVue's Select component with `filter` gives a searchable dropdown
 * (similar to Select2), and `showClear` provides a per-filter clear button.
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
import { useWindowStore } from '@/stores/window'
import { formatCategory } from '@/utils/format'
import type { DomainStats } from '@/types/api'

const route = useRoute()
const router = useRouter()
const windowStore = useWindowStore()

const windowOptions = [
  { label: '24h', value: 24 },
  { label: '7d', value: 168 },
]
const selectedWindow = computed({
  get: () => windowOptions.find(o => o.value === windowStore.hours) ?? windowOptions[0],
  set: (v) => { windowStore.hours = v.value },
})

// Filter state — initialised from URL query params
const selectedCategory = ref<string | null>((route.query.category as string) ?? null)
const selectedCompany = ref<string | null>((route.query.company as string) ?? null)

// Available options from the backend
const categoryOptions = ref<string[]>([])
const companyOptions = ref<string[]>([])

const data = ref<DomainStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

const hasFilters = computed(() => selectedCategory.value != null || selectedCompany.value != null)

// Sync filter state to URL query params (replace, don't push — avoids history spam)
function syncUrlParams() {
  const query: Record<string, string> = {}
  if (selectedCategory.value) query.category = selectedCategory.value
  if (selectedCompany.value) query.company = selectedCompany.value
  router.replace({ path: '/report', query })
}

async function fetchOptions() {
  try {
    const res = await fetch('/api/config/options')
    const json = await res.json()
    categoryOptions.value = json.categories ?? []
    companyOptions.value = json.companies ?? []
  } catch (e) {
    console.warn('Failed to fetch filter options:', e)
  }
}

async function fetchData() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams({ hours: String(windowStore.hours) })
    if (selectedCategory.value) params.set('category', selectedCategory.value)
    if (selectedCompany.value) params.set('company', selectedCompany.value)
    const res = await fetch(`/api/stats/domains?${params}`)
    data.value = await res.json()
  } catch {
    error.value = 'Failed to load data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  selectedCategory.value = null
  selectedCompany.value = null
}

onMounted(async () => {
  await fetchOptions()
  await fetchData()
})

watch(() => windowStore.hours, fetchData)
watch(() => windowStore.refreshKey, () => {
  fetchOptions()
  fetchData()
})
watch([selectedCategory, selectedCompany], () => {
  syncUrlParams()
  fetchData()
})
</script>

<template>
  <div class="p-6 space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Domain Report</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          Domains grouped by query count — {{ selectedWindow.label }}
        </p>
      </div>
      <div class="flex items-center gap-2">
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
    <div v-if="error && data" class="text-sm text-red-500 text-right -mb-4">{{ error }}</div>

    <!-- Loading -->
    <div v-if="loading && !data" class="flex flex-col items-center justify-center py-24 gap-4 text-gray-500 dark:text-gray-400">
      <ProgressSpinner />
      <p>Loading…</p>
    </div>

    <!-- Error -->
    <div v-else-if="error && !data" class="flex items-center justify-center py-24">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Table -->
    <Card v-if="data">
      <template #content>
        <DataTable
          :value="data!.domains"
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

  </div>
</template>

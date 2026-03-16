<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import SelectButton from 'primevue/selectbutton'
import ProgressSpinner from 'primevue/progressspinner'
import Button from 'primevue/button'
import { useWindowStore } from '@/stores/window'
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

const category = computed(() => route.query.category as string | undefined)
const company = computed(() => route.query.company as string | undefined)

const data = ref<DomainStats | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

async function fetchData() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams({ hours: String(windowStore.hours) })
    if (category.value) params.set('category', category.value)
    if (company.value) params.set('company', company.value)
    const res = await fetch(`/api/stats/domains?${params}`)
    data.value = await res.json()
  } catch {
    error.value = 'Failed to load data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
watch(() => windowStore.hours, fetchData)
watch(() => windowStore.refreshKey, fetchData)
watch([category, company], fetchData)
</script>

<template>
  <div class="p-6 space-y-6">

    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <Button
          icon="pi pi-arrow-left"
          severity="secondary"
          text
          rounded
          aria-label="Back"
          @click="router.back()"
        />
        <div>
          <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">
            Domain Report
            <span v-if="category" class="font-normal text-gray-500 dark:text-gray-400">
              — {{ category }}
            </span>
            <span v-else-if="company" class="font-normal text-gray-500 dark:text-gray-400">
              — {{ company }}
            </span>
          </h1>
          <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Domains grouped by query count — {{ selectedWindow.label }}
          </p>
        </div>
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
          <Column v-if="!category" field="category" header="Category" sortable />
          <Column v-if="!company" field="company_name" header="Company" sortable />
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

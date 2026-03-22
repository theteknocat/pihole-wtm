<script setup lang="ts">
/**
 * DomainsReportView — query breakdown grouped by domain.
 *
 * Filters: category, company, device, domain search (with exact match toggle).
 */
import { computed } from 'vue'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import AutoComplete from 'primevue/autocomplete'
import Checkbox from 'primevue/checkbox'
import InputGroup from 'primevue/inputgroup'
import Select from 'primevue/select'
import Skeleton from 'primevue/skeleton'
import Button from 'primevue/button'
import PageHeader from '@/components/layout/PageHeader.vue'
import { formatCategory } from '@/utils/format'
import { useReportData, type ClientOption } from '@/composables/useReportData'
import type { DomainStats } from '@/types/api'

const {
  data, loading, error, hasFilters,
  selectedCategory, selectedCompany, selectedClientIp,
  categoryOptions, companyOptions, clientOptions,
  domainInput, appliedDomain, domainExact, domainSuggestions,
  resetFilters, searchDomains, applyDomainFilter,
  onDomainSelect, onDomainClear,
} = useReportData('domain')

const domainData = computed(() => data.value as DomainStats | null)
</script>

<template>
  <div class="p-6 space-y-6">
    <PageHeader
      icon="pi pi-globe"
      title="Domains Report"
    />

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

      <!-- Domain search -->
      <div class="flex flex-col gap-1">
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

    <!-- Refresh error -->
    <div v-if="error && domainData" class="error-banner">{{ error }}</div>

    <!-- Loading skeleton -->
    <Card v-if="loading && !domainData">
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
    <div v-else-if="error && !domainData" class="flex items-center justify-center py-24">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Domain table -->
    <Card v-if="domainData">
      <template #content>
        <DataTable
          :value="domainData.domains"
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
  </div>
</template>

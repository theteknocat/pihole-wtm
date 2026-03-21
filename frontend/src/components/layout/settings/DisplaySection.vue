<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import AutoComplete from 'primevue/autocomplete'
import ProgressSpinner from 'primevue/progressspinner'
import { useWindowStore } from '@/stores/window'
import { formatCategory } from '@/utils/format'
import { apiFetch } from '@/utils/api'

const emit = defineEmits<{ (e: 'saved'): void }>()
const windowStore = useWindowStore()

const loading = ref(true)
const error = ref<string | null>(null)

// Available options
const availableCategories = ref<string[]>([])
const availableCompanies = ref<string[]>([])

// Current exclusion selections
const excludedCategories = ref<string[]>([])
const excludedCompanies = ref<string[]>([])
const excludedDomains = ref<string[]>([])


// Category objects: { label: "Advertising", value: "ad" }
interface CategoryOption { label: string; value: string }

const excludedCategoryObjects = computed(() =>
  excludedCategories.value.map(c => ({ label: formatCategory(c), value: c }))
)

const categorySuggestions = ref<CategoryOption[]>([])

function searchCategories(event: { query: string }) {
  const q = event.query.toLowerCase()
  categorySuggestions.value = availableCategories.value
    .filter(c => !excludedCategories.value.includes(c) && formatCategory(c).toLowerCase().includes(q))
    .map(c => ({ label: formatCategory(c), value: c }))
}

// Company autocomplete suggestions (filtered against already-excluded)
const companySuggestions = ref<string[]>([])

function searchCompanies(event: { query: string }) {
  const q = event.query.toLowerCase()
  companySuggestions.value = availableCompanies.value.filter(
    c => c.toLowerCase().includes(q) && !excludedCompanies.value.includes(c)
  )
}

function onCompaniesChanged(value: string[]) {
  excludedCompanies.value = value
  scheduleSave()
}

function onCategoriesChanged(value: CategoryOption[]) {
  excludedCategories.value = value.map(v => v.value)
  scheduleSave()
}

function onDomainsChanged(value: string[]) {
  excludedDomains.value = value.map(d => d.trim().toLowerCase()).filter(Boolean)
  scheduleSave()
}

// Domain autocomplete suggestions
const domainSuggestions = ref<string[]>([])

async function searchDomains(event: { query: string }) {
  if (event.query.length < 2) {
    domainSuggestions.value = []
    return
  }
  try {
    const params = new URLSearchParams({ q: event.query, hours: '168' })
    const res = await apiFetch(`/api/domains/search?${params}`)
    if (res.ok) domainSuggestions.value = await res.json()
  } catch {
    domainSuggestions.value = []
  }
}


// Debounced auto-save
let saveTimer: ReturnType<typeof setTimeout> | null = null
let dirty = false

function scheduleSave() {
  dirty = true
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(doSave, 1200)
}

/** Flush any pending save immediately. Returns when save is complete. */
async function flush() {
  if (saveTimer) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
  if (dirty) await doSave()
}

defineExpose({ flush })

async function doSave() {
  dirty = false
  try {
    const entries: [string, string[]][] = [
      ['excluded_categories', [...excludedCategories.value]],
      ['excluded_companies', [...excludedCompanies.value]],
      ['excluded_domains', [...excludedDomains.value]],
    ]
    await Promise.all(entries.map(([key, value]) =>
      apiFetch(`/api/settings/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value }),
      }).then(r => { if (!r.ok) throw new Error() })
    ))
    emit('saved')
    windowStore.triggerRefresh()
  } catch {
    error.value = 'Failed to save'
    setTimeout(() => { error.value = null }, 3000)
  }
}

onMounted(async () => {
  try {
    const [optionsRes, configRes] = await Promise.all([
      apiFetch('/api/settings/options').then(r => r.json()),
      apiFetch('/api/settings').then(r => r.json()),
    ])
    availableCategories.value = optionsRes.categories
    availableCompanies.value = optionsRes.companies
    excludedCategories.value = configRes.excluded_categories
    excludedCompanies.value = configRes.excluded_companies
    excludedDomains.value = configRes.excluded_domains
  } catch {
    error.value = 'Failed to load configuration'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <ProgressSpinner style="width: 32px; height: 32px" />
    </div>

    <div v-else class="space-y-5">

      <div v-if="error" class="text-xs text-red-500">{{ error }}</div>

      <p class="text-xs text-gray-500 dark:text-gray-400">
        Excluded items are hidden from dashboard views. Data is still collected.
      </p>

      <!-- Categories -->
      <div>
        <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Excluded Categories</h3>
        <AutoComplete
          :model-value="excludedCategoryObjects"
          :multiple="true"
          :suggestions="categorySuggestions"
          :dropdown="true"
          optionLabel="label"
          placeholder="Category name..."
          class="w-full"
          @complete="searchCategories"
          @update:model-value="onCategoriesChanged"
        />
      </div>

      <!-- Companies -->
      <div>
        <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Excluded Companies</h3>
        <AutoComplete
          :model-value="excludedCompanies"
          :multiple="true"
          :suggestions="companySuggestions"
          :dropdown="true"
          placeholder="Company name..."
          class="w-full"
          @complete="searchCompanies"
          @update:model-value="onCompaniesChanged"
        />
      </div>

      <!-- Domains -->
      <div>
        <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Excluded Domains</h3>
        <AutoComplete
          :model-value="excludedDomains"
          :multiple="true"
          :suggestions="domainSuggestions"
          placeholder="e.g. example.tracker.com"
          class="w-full"
          @complete="searchDomains"
          @update:model-value="onDomainsChanged"
        />
      </div>
    </div>
  </div>
</template>

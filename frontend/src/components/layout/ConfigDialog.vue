<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import { useWindowStore } from '@/stores/window'
import { formatCategory } from '@/utils/format'

const emit = defineEmits<{ (e: 'close'): void }>()
const windowStore = useWindowStore()

const visible = ref(true)
const loading = ref(true)
const saving = ref(false)
const error = ref<string | null>(null)

// Available options from the backend
const availableCategories = ref<string[]>([])
const availableCompanies = ref<string[]>([])

// Current exclusion selections (checked = excluded)
const excludedCategories = ref<Set<string>>(new Set())
const excludedCompanies = ref<Set<string>>(new Set())
const excludedDomains = ref<string[]>([])
const newDomain = ref('')

// Search/filter for the companies list
const companySearch = ref('')

const filteredCompanies = computed(() => {
  if (!companySearch.value) return availableCompanies.value
  const q = companySearch.value.toLowerCase()
  return availableCompanies.value.filter(c => c.toLowerCase().includes(q))
})

function toggleCategory(cat: string) {
  if (excludedCategories.value.has(cat)) {
    excludedCategories.value.delete(cat)
  } else {
    excludedCategories.value.add(cat)
  }
}

function toggleCompany(company: string) {
  if (excludedCompanies.value.has(company)) {
    excludedCompanies.value.delete(company)
  } else {
    excludedCompanies.value.add(company)
  }
}

function addDomain() {
  const d = newDomain.value.trim().toLowerCase()
  if (d && !excludedDomains.value.includes(d)) {
    excludedDomains.value.push(d)
  }
  newDomain.value = ''
}

function removeDomain(domain: string) {
  excludedDomains.value = excludedDomains.value.filter(d => d !== domain)
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const [optionsRes, configRes] = await Promise.all([
      fetch('/api/config/options').then(r => r.json()),
      fetch('/api/config').then(r => r.json()),
    ])
    availableCategories.value = optionsRes.categories
    availableCompanies.value = optionsRes.companies
    excludedCategories.value = new Set(configRes.excluded_categories)
    excludedCompanies.value = new Set(configRes.excluded_companies)
    excludedDomains.value = configRes.excluded_domains
  } catch {
    error.value = 'Failed to load configuration'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = null
  try {
    const res = await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        excluded_categories: [...excludedCategories.value],
        excluded_companies: [...excludedCompanies.value],
        excluded_domains: [...excludedDomains.value],
      }),
    })
    if (!res.ok) throw new Error(`Server error ${res.status}`)
    windowStore.triggerRefresh()
    close()
  } catch {
    error.value = 'Failed to save configuration'
  } finally {
    saving.value = false
  }
}

function close() {
  visible.value = false
  emit('close')
}

onMounted(load)
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :draggable="false"
    header="Tracker Source Configuration"
    :style="{ width: '720px', maxHeight: '85vh' }"
    :closable="true"
    @hide="close"
  >
    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <ProgressSpinner style="width: 40px; height: 40px" />
    </div>

    <div v-else class="space-y-6">

      <!-- Error banner -->
      <div v-if="error" class="text-sm text-red-500 bg-red-50 dark:bg-red-950/30 rounded px-3 py-2">
        {{ error }}
      </div>

      <p class="text-sm text-gray-500 dark:text-gray-400">
        Excluded categories, companies, and domains will be hidden from dashboard views.
        Data is still collected — exclusions only affect display.
      </p>

      <!-- Categories -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Categories</h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
          Uncheck categories you want to hide from the dashboard.
        </p>
        <div v-if="availableCategories.length === 0" class="text-xs text-gray-400 italic">
          No categories found — data may still be syncing.
        </div>
        <div v-else class="grid grid-cols-2 gap-2">
          <label
            v-for="cat in availableCategories"
            :key="cat"
            class="flex items-center gap-2 px-3 py-2 rounded border border-gray-200 dark:border-gray-700 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            :class="{ 'opacity-50': excludedCategories.has(cat) }"
          >
            <Checkbox
              :model-value="!excludedCategories.has(cat)"
              :binary="true"
              @update:model-value="toggleCategory(cat)"
            />
            <span class="text-sm">{{ formatCategory(cat) }}</span>
          </label>
        </div>
      </div>

      <!-- Companies -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">Companies</h3>
          <Tag v-if="excludedCompanies.size > 0" severity="warn" :value="`${excludedCompanies.size} excluded`" />
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
          Uncheck companies you want to hide from the dashboard.
        </p>
        <InputText
          v-model="companySearch"
          placeholder="Search companies..."
          class="w-full mb-3"
          size="small"
        />
        <div v-if="availableCompanies.length === 0" class="text-xs text-gray-400 italic">
          No companies found — data may still be syncing.
        </div>
        <div v-else class="max-h-48 overflow-auto border border-gray-200 dark:border-gray-700 rounded">
          <label
            v-for="company in filteredCompanies"
            :key="company"
            class="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors border-b border-gray-100 dark:border-gray-800 last:border-0"
            :class="{ 'opacity-50': excludedCompanies.has(company) }"
          >
            <Checkbox
              :model-value="!excludedCompanies.has(company)"
              :binary="true"
              @update:model-value="toggleCompany(company)"
            />
            <span class="text-sm">{{ company }}</span>
          </label>
        </div>
      </div>

      <!-- Domain exclusions -->
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Excluded Domains</h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-3">
          Specific domains to always hide, regardless of category or company.
        </p>
        <div class="flex gap-2 mb-3">
          <InputText
            v-model="newDomain"
            placeholder="e.g. example.tracker.com"
            class="flex-1"
            size="small"
            @keyup.enter="addDomain"
          />
          <Button label="Add" icon="pi pi-plus" size="small" :disabled="!newDomain.trim()" @click="addDomain" />
        </div>
        <div v-if="excludedDomains.length" class="flex flex-wrap gap-2">
          <Tag
            v-for="domain in excludedDomains"
            :key="domain"
            :value="domain"
            severity="secondary"
            class="cursor-pointer"
            @click="removeDomain(domain)"
            v-tooltip.top="'Click to remove'"
          >
            <template #default>
              <span class="text-xs">{{ domain }}</span>
              <i class="pi pi-times text-xs ml-1" />
            </template>
          </Tag>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button label="Cancel" severity="secondary" text @click="close" />
        <Button label="Save" icon="pi pi-check" :loading="saving" @click="save" />
      </div>
    </template>
  </Dialog>
</template>

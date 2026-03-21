<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import Checkbox from 'primevue/checkbox'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import ProgressSpinner from 'primevue/progressspinner'
import Button from 'primevue/button'
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
const excludedCategories = ref<Set<string>>(new Set())
const excludedCompanies = ref<Set<string>>(new Set())
const excludedDomains = ref<string[]>([])
const newDomain = ref('')

// Split categories into two columns (first half / second half, both alphabetical)
const categoryColumns = computed(() => {
  const cats = availableCategories.value
  const mid = Math.ceil(cats.length / 2)
  return [cats.slice(0, mid), cats.slice(mid)]
})

// Company search
const companySearch = ref('')
const filteredCompanies = computed(() => {
  if (!companySearch.value) return availableCompanies.value
  const q = companySearch.value.toLowerCase()
  return availableCompanies.value.filter(c => c.toLowerCase().includes(q))
})

// Debounced auto-save
let saveTimer: ReturnType<typeof setTimeout> | null = null
let dirty = false

function scheduleSave() {
  dirty = true
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(doSave, 2000)
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

function toggleCategory(cat: string) {
  if (excludedCategories.value.has(cat)) {
    excludedCategories.value.delete(cat)
  } else {
    excludedCategories.value.add(cat)
  }
  scheduleSave()
}

function toggleCompany(company: string) {
  if (excludedCompanies.value.has(company)) {
    excludedCompanies.value.delete(company)
  } else {
    excludedCompanies.value.add(company)
  }
  scheduleSave()
}

function addDomain() {
  const d = newDomain.value.trim().toLowerCase()
  if (d && !excludedDomains.value.includes(d)) {
    excludedDomains.value.push(d)
    scheduleSave()
  }
  newDomain.value = ''
}

function removeDomain(domain: string) {
  excludedDomains.value = excludedDomains.value.filter(d => d !== domain)
  scheduleSave()
}

onMounted(async () => {
  try {
    const [optionsRes, configRes] = await Promise.all([
      apiFetch('/api/settings/options').then(r => r.json()),
      apiFetch('/api/settings').then(r => r.json()),
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
        <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Categories</h3>
        <div v-if="availableCategories.length === 0" class="text-xs text-gray-400 italic">
          No categories found yet.
        </div>
        <div v-else class="flex flex-col sm:flex-row gap-0 sm:gap-4">
          <div v-for="(col, i) in categoryColumns" :key="i" class="flex-1 space-y-1">
            <label
              v-for="cat in col"
              :key="cat"
              class="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
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
      </div>

      <!-- Companies -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider">Companies</h3>
          <span v-if="excludedCompanies.size > 0" class="text-xs text-amber-500">{{ excludedCompanies.size }} excluded</span>
        </div>
        <InputText
          v-model="companySearch"
          placeholder="Search companies..."
          class="w-full mb-2"
          size="small"
        />
        <div v-if="availableCompanies.length === 0" class="text-xs text-gray-400 italic">
          No companies found yet.
        </div>
        <div v-else class="max-h-48 overflow-auto border border-gray-200 dark:border-gray-700 rounded">
          <label
            v-for="company in filteredCompanies"
            :key="company"
            class="flex items-center gap-2 px-2 py-1 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors border-b border-gray-100 dark:border-gray-800 last:border-0"
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

      <!-- Domains -->
      <div>
        <h3 class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider mb-2">Excluded Domains</h3>
        <p class="text-xs text-gray-500 dark:text-gray-400 mb-2">
          Specific domains to always hide.
        </p>
        <div class="flex gap-2 mb-2">
          <InputText
            v-model="newDomain"
            placeholder="e.g. example.tracker.com"
            class="flex-1"
            size="small"
            @keyup.enter="addDomain"
          />
          <Button label="Add" icon="pi pi-plus" size="small" :disabled="!newDomain.trim()" @click="addDomain" />
        </div>
        <div v-if="excludedDomains.length" class="flex flex-wrap gap-1">
          <Tag
            v-for="domain in excludedDomains"
            :key="domain"
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
  </div>
</template>

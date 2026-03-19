<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import ProgressSpinner from 'primevue/progressspinner'
import Button from 'primevue/button'
import SelectButton from 'primevue/selectbutton'
import ToggleButton from 'primevue/togglebutton'
import CategoryBarChart from '@/components/dashboard/CategoryBarChart.vue'
import CompanyBarChart from '@/components/dashboard/CompanyBarChart.vue'
import TopCompaniesTable from '@/components/dashboard/TopCompaniesTable.vue'
import RecentQueriesTable from '@/components/dashboard/RecentQueriesTable.vue'
import { useWindowStore } from '@/stores/window'
import { useScrolled } from '@/composables/useScrolled'
import type { TrackerStats, EnrichedQuery, CompanyStat } from '@/types/api'

const router = useRouter()
const windowStore = useWindowStore()
const scrolled = useScrolled()

const windowOptions = [
  { label: '24h', value: 24 },
  { label: '7d', value: 168 },
]
const selectedWindow = computed({
  get: () => windowOptions.find(o => o.value === windowStore.hours) ?? windowOptions[0],
  set: (v) => { windowStore.hours = v.value },
})
const trackerOnly = ref(true)

const stats = ref<TrackerStats | null>(null)
const recentBlocked = ref<EnrichedQuery[]>([])
const recentAllowed = ref<EnrichedQuery[]>([])
const loading = ref(true)
const recentLoading = ref(false)
const error = ref<string | null>(null)

const allCompanies = computed<CompanyStat[]>(() => {
  if (!stats.value) return []
  const map = new Map<string, CompanyStat>()
  for (const cat of stats.value.by_category) {
    for (const co of cat.companies) {
      const existing = map.get(co.company_name)
      if (existing) {
        existing.query_count += co.query_count
        existing.blocked_count += co.blocked_count
        existing.allowed_count += co.allowed_count
      } else {
        map.set(co.company_name, { ...co })
      }
    }
  }
  return [...map.values()]
})

function recentQueryUrl(statusType: 'blocked' | 'allowed') {
  const params = new URLSearchParams({ status_type: statusType, limit: '10' })
  if (trackerOnly.value) params.set('tracker_only', 'true')
  return `/api/queries?${params}`
}

async function fetchRecentQueries() {
  recentLoading.value = true
  try {
    const [blockedRes, allowedRes] = await Promise.all([
      fetch(recentQueryUrl('blocked')).then(r => r.json()),
      fetch(recentQueryUrl('allowed')).then(r => r.json()),
    ])
    recentBlocked.value = blockedRes.queries
    recentAllowed.value = allowedRes.queries
  } catch (e) {
    console.warn('Failed to fetch recent queries:', e)
  } finally {
    recentLoading.value = false
  }
}

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const [statsRes, blockedRes, allowedRes] = await Promise.all([
      fetch(`/api/stats/trackers?hours=${windowStore.hours}`).then(r => r.json()),
      fetch(recentQueryUrl('blocked')).then(r => r.json()),
      fetch(recentQueryUrl('allowed')).then(r => r.json()),
    ])
    stats.value = statsRes
    recentBlocked.value = blockedRes.queries
    recentAllowed.value = allowedRes.queries
  } catch {
    error.value = 'Failed to load dashboard data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

function drillCategory(category: string) {
  router.push({ path: '/detailed-report', query: { category } })
}

function drillCompany(company: string) {
  router.push({ path: '/detailed-report', query: { company } })
}

onMounted(fetchStats)
watch(() => windowStore.hours, fetchStats)
watch(() => windowStore.refreshKey, fetchStats)
watch(trackerOnly, fetchRecentQueries)
</script>

<template>
  <div class="p-6 space-y-6">

    <!-- Header row -->
    <div class="flex items-center justify-between sticky-header" :class="{ scrolled }">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100">Dashboard</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
          Tracker intelligence for the last {{ selectedWindow.label }}
        </p>
      </div>
      <div class="flex items-center gap-2">
        <SelectButton
          v-model="selectedWindow"
          :options="windowOptions"
          option-label="label"
          :allow-empty="false"
          :size="scrolled ? 'small' : undefined"
        />
        <Button
          icon="pi pi-refresh"
          severity="secondary"
          text
          rounded
          :loading="loading"
          :size="scrolled ? 'small' : undefined"
          aria-label="Refresh"
          @click="fetchStats()"
        />
      </div>
    </div>

    <!-- Refresh error (shown over existing data) -->
    <div v-if="error && stats" class="text-sm text-red-500 text-right -mb-4">{{ error }}</div>

    <!-- Loading -->
    <div v-if="loading && !stats" class="flex flex-col items-center justify-center py-24 gap-4 text-gray-500 dark:text-gray-400">
      <ProgressSpinner />
      <p>Loading{{ selectedWindow.value === 168 ? ' — 7 day window may take a moment' : '…' }}</p>
    </div>

    <!-- Error -->
    <div v-else-if="error && !stats" class="flex items-center justify-center py-24">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Dashboard grid -->
    <div v-if="stats" class="grid grid-cols-1 xl:grid-cols-2 gap-6">

      <Card>
        <template #title>Tracker Categories</template>
        <template #subtitle>By query count — {{ selectedWindow.label }}</template>
        <template #content>
          <CategoryBarChart
            :data="stats!.by_category"
            :total-tracker-queries="stats!.tracker_queries"
            @select-category="drillCategory"
          />
        </template>
      </Card>

      <Card>
        <template #title>Top Companies</template>
        <template #subtitle>By query count — {{ selectedWindow.label }}</template>
        <template #content>
          <CompanyBarChart
            :data="allCompanies"
            :total-tracker-queries="stats!.tracker_queries"
            @select-company="drillCompany"
          />
        </template>
      </Card>

      <Card>
        <template #title>Top Blocked Companies</template>
        <template #subtitle>{{ selectedWindow.label }}</template>
        <template #content>
          <TopCompaniesTable :data="allCompanies" type="blocked" @select-company="drillCompany" />
        </template>
      </Card>

      <Card>
        <template #title>Top Allowed Companies</template>
        <template #subtitle>{{ selectedWindow.label }}</template>
        <template #content>
          <TopCompaniesTable :data="allCompanies" type="allowed" @select-company="drillCompany" />
        </template>
      </Card>

      <!-- Recent queries section — spans full width for the toggle header -->
      <div class="xl:col-span-2 flex items-center justify-between">
        <div>
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">Recent Query Activity</h2>
          <p class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {{ trackerOnly ? 'Showing known tracker domains only' : 'Showing all queries' }}
          </p>
        </div>
        <ToggleButton
          v-model="trackerOnly"
          on-label="Trackers only"
          off-label="All queries"
          on-icon="pi pi-filter"
          off-icon="pi pi-filter-slash"
          :disabled="recentLoading"
        />
      </div>

      <Card>
        <template #title>Recent Blocked</template>
        <template #content>
          <div v-if="recentLoading" class="flex justify-center py-8">
            <ProgressSpinner style="width: 32px; height: 32px" />
          </div>
          <RecentQueriesTable v-else :queries="recentBlocked" type="blocked" />
        </template>
      </Card>

      <Card>
        <template #title>Recent Allowed</template>
        <template #content>
          <div v-if="recentLoading" class="flex justify-center py-8">
            <ProgressSpinner style="width: 32px; height: 32px" />
          </div>
          <RecentQueriesTable v-else :queries="recentAllowed" type="allowed" />
        </template>
      </Card>

    </div>
  </div>
</template>

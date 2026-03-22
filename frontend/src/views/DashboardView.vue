<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import Skeleton from 'primevue/skeleton'
import ToggleButton from 'primevue/togglebutton'
import CategoryBarChart from '@/components/dashboard/CategoryBarChart.vue'
import CompanyBarChart from '@/components/dashboard/CompanyBarChart.vue'
import TopCompaniesTable from '@/components/dashboard/TopCompaniesTable.vue'
import RecentQueriesTable from '@/components/dashboard/RecentQueriesTable.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { useWindowStore } from '@/stores/window'
import { apiFetch } from '@/utils/api'
import type { TrackerStats, EnrichedQuery, CompanyStat } from '@/types/api'

const router = useRouter()
const windowStore = useWindowStore()
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
      apiFetch(recentQueryUrl('blocked')),
      apiFetch(recentQueryUrl('allowed')),
    ])
    if (!blockedRes.ok || !allowedRes.ok) throw new Error('Server error')
    recentBlocked.value = (await blockedRes.json()).queries
    recentAllowed.value = (await allowedRes.json()).queries
  } catch {
    error.value = 'Failed to fetch recent queries.'
  } finally {
    recentLoading.value = false
  }
}

async function fetchStats() {
  loading.value = true
  error.value = null
  try {
    const [statsRes, blockedRes, allowedRes] = await Promise.all([
      apiFetch(`/api/stats/trackers?${windowStore.queryParams()}`),
      apiFetch(recentQueryUrl('blocked')),
      apiFetch(recentQueryUrl('allowed')),
    ])
    if (!statsRes.ok || !blockedRes.ok || !allowedRes.ok) throw new Error('Server error')
    stats.value = await statsRes.json()
    recentBlocked.value = (await blockedRes.json()).queries
    recentAllowed.value = (await allowedRes.json()).queries
  } catch {
    error.value = 'Failed to load dashboard data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

function drillCategory(category: string) {
  router.push({ path: '/domains-report', query: { category } })
}

function drillCompany(company: string) {
  router.push({ path: '/domains-report', query: { company } })
}

onMounted(fetchStats)
watch(() => windowStore.hours, fetchStats)
watch(() => windowStore.endTs, fetchStats)
watch(() => windowStore.refreshKey, fetchStats)
watch(trackerOnly, fetchRecentQueries)
</script>

<template>
  <div class="p-6 space-y-6">

    <PageHeader
      icon="pi pi-gauge"
      title="Dashboard"
    />

    <!-- Auto-refresh error (shown over existing data) -->
    <div v-if="error && stats" class="error-banner">{{ error }}</div>

    <!-- Loading skeletons -->
    <div v-if="loading && !stats" class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <Card v-for="i in 4" :key="i">
        <template #title><Skeleton width="10rem" height="1.2rem" /></template>
        <template #content>
          <div class="space-y-3">
            <Skeleton v-for="j in 5" :key="j" :width="`${85 - j * 10}%`" height="1.5rem" />
          </div>
        </template>
      </Card>
    </div>

    <!-- Error -->
    <div v-else-if="error && !stats" class="flex items-center justify-center py-24">
      <p class="text-red-500">{{ error }}</p>
    </div>

    <!-- Dashboard grid -->
    <div v-if="stats" class="grid grid-cols-1 xl:grid-cols-2 gap-6">

      <Card>
        <template #title>Top Categories</template>
        <template #content>
          <p v-if="stats!.by_category.length === 0" class="empty-state">No tracker data for this time window</p>
          <CategoryBarChart
            v-else
            :data="stats!.by_category"
            :total-tracker-queries="stats!.tracker_queries"
            @select-category="drillCategory"
          />
        </template>
      </Card>

      <Card>
        <template #title>Top Companies</template>
        <template #content>
          <p v-if="allCompanies.length === 0" class="empty-state">No tracker data for this time window</p>
          <CompanyBarChart
            v-else
            :data="allCompanies"
            :total-tracker-queries="stats!.tracker_queries"
            @select-company="drillCompany"
          />
        </template>
      </Card>

      <Card>
        <template #title>Top Blocked Companies</template>
        <template #content>
          <TopCompaniesTable :data="allCompanies" type="blocked" @select-company="drillCompany" />
        </template>
      </Card>

      <Card>
        <template #title>Top Allowed Companies</template>
        <template #content>
          <TopCompaniesTable :data="allCompanies" type="allowed" @select-company="drillCompany" />
        </template>
      </Card>

      <!-- Recent queries section — spans full width for the toggle header -->
      <div class="xl:col-span-2 flex flex-col items-center gap-2 md:flex-row md:justify-between">
        <div class="text-center md:text-left">
          <h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">Recent Domain Activity</h2>
          <p class="text-sm text-muted mt-0.5">
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
          <div v-if="recentLoading" class="space-y-3 py-2">
            <Skeleton v-for="i in 5" :key="i" width="100%" height="1.2rem" />
          </div>
          <RecentQueriesTable v-else :queries="recentBlocked" type="blocked" />
        </template>
      </Card>

      <Card>
        <template #title>Recent Allowed</template>
        <template #content>
          <div v-if="recentLoading" class="space-y-3 py-2">
            <Skeleton v-for="i in 5" :key="i" width="100%" height="1.2rem" />
          </div>
          <RecentQueriesTable v-else :queries="recentAllowed" type="allowed" />
        </template>
      </Card>

    </div>
  </div>
</template>

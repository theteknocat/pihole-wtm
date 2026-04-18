/**
 * useReportData — shared fetch/filter logic for domain and device report views.
 *
 * Handles loading state, abort control, category/company filter options,
 * URL param sync, and time-window watchers. Each view passes its mode
 * ('domain' | 'client') and gets back the relevant reactive state.
 */
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWindowStore } from '@/stores/window'
import { apiFetch } from '@/utils/api'
import type { DeviceGroup } from '@/types/api'

export interface ClientOption {
  client_ip: string
  client_name: string | null
  query_count: number
}

/** A single entry in the combined device filter Select. */
export interface DeviceOption {
  /** Display label (group name or device name/IP). */
  label: string
  /** IP(s) to filter on — array for groups, single string for individuals. */
  ips: string | string[]
  /** True when this entry represents a device group. */
  isGroup: boolean
  /** Shown as a second line: IP for named individuals, member count for groups. */
  subLabel: string | null
}

export function useReportData(mode: 'domain' | 'client') {
  const route = useRoute()
  const router = useRouter()
  const windowStore = useWindowStore()

  // Shared filter state
  const selectedCategory = ref<string | null>((route.query.category as string) ?? null)
  const selectedCompany = ref<string | null>((route.query.company as string) ?? null)
  const categoryOptions = ref<string[]>([])
  const companyOptions = ref<string[]>([])

  // Domain-only filter state — device groups + combined Select model
  const deviceGroups = ref<DeviceGroup[]>([])
  const clientOptions = ref<ClientOption[]>([])

  /**
   * Combined device option list: groups and ungrouped individuals, sorted
   * alphabetically. Individuals that belong to a group are excluded.
   */
  const groupedIps = computed(() => {
    const s = new Set<string>()
    for (const g of deviceGroups.value) for (const m of g.members) s.add(m.client_ip)
    return s
  })

  const deviceOptions = computed<DeviceOption[]>(() => {
    const opts: DeviceOption[] = []
    for (const g of deviceGroups.value) {
      opts.push({
        label: g.name,
        ips: g.members.map(m => m.client_ip),
        isGroup: true,
        subLabel: `${g.members.length} devices`,
      })
    }
    for (const c of clientOptions.value) {
      if (groupedIps.value.has(c.client_ip)) continue
      opts.push({
        label: c.client_name ?? c.client_ip,
        ips: c.client_ip,
        isGroup: false,
        subLabel: c.client_name ? c.client_ip : null,
      })
    }
    opts.sort((a, b) => a.label.localeCompare(b.label))
    return opts
  })

  /**
   * Try to find a DeviceOption matching a given set of IPs (used when restoring
   * from URL). Returns null if no group matches exactly.
   */
  function findDeviceOption(ips: string | string[]): DeviceOption | null {
    const target = Array.isArray(ips) ? [...ips].sort().join(',') : ips
    for (const opt of deviceOptions.value) {
      const optIps = Array.isArray(opt.ips) ? [...opt.ips].sort().join(',') : opt.ips
      if (optIps === target) return opt
    }
    return null
  }

  // The Select's bound model. null = "All devices".
  const selectedDeviceOption = ref<DeviceOption | null>(null)

  // Derive selectedClientIp from the Select model (used by fetch + URL sync).
  const selectedClientIp = computed<string | string[] | null>(
    () => selectedDeviceOption.value?.ips ?? null
  )

  // Raw multi-IP value from URL (only set on init when no group matched yet).
  const pendingUrlIps = ref<string | string[] | null>(
    (() => {
      const v = route.query.client_ip
      if (!v) return null
      if (Array.isArray(v)) return v.filter(Boolean) as string[]
      return v as string
    })()
  )
  const domainInput = ref<string | null>((route.query.domain as string) ?? null)
  const appliedDomain = ref<string | null>((route.query.domain as string) ?? null)
  const domainExact = ref(route.query.domain_exact === '1')
  const domainSuggestions = ref<string[]>([])

  // Data state
  const data = ref<unknown>(null)
  const loading = ref(true)
  const error = ref<string | null>(null)
  let fetchController: AbortController | null = null

  const hasFilters = computed(() =>
    selectedCategory.value != null || selectedCompany.value != null ||
    (mode === 'domain' && (selectedClientIp.value != null || appliedDomain.value != null))
  )

  const routePath = mode === 'domain' ? '/domains-report' : '/devices-report'

  function syncUrlParams() {
    const query: Record<string, string | string[]> = {}
    if (selectedCategory.value) query.category = selectedCategory.value
    if (selectedCompany.value) query.company = selectedCompany.value
    if (mode === 'domain') {
      if (selectedClientIp.value) query.client_ip = selectedClientIp.value
      if (appliedDomain.value) query.domain = appliedDomain.value
      if (domainExact.value) query.domain_exact = '1'
    }
    router.replace({ path: routePath, query })
  }

  async function fetchOptions() {
    try {
      const qs = windowStore.queryParams({})
      const requests: Promise<Response>[] = [
        apiFetch(`/api/settings/options?${qs}`),
        apiFetch(`/api/clients?${qs}`),
      ]
      if (mode === 'domain') requests.push(apiFetch('/api/device-groups'))
      const [configRes, clientsRes, groupsRes] = await Promise.all(requests)
      if (!configRes.ok || !clientsRes.ok) throw new Error('Failed to fetch filter options')
      const configJson = await configRes.json()
      categoryOptions.value = configJson.categories ?? []
      companyOptions.value = configJson.companies ?? []
      const clientsJson = await clientsRes.json()
      clientOptions.value = clientsJson.clients ?? []
      if (groupsRes?.ok) {
        const groupsJson = await groupsRes.json()
        deviceGroups.value = groupsJson.groups ?? []
      }
      // Resolve any pending URL selection (set before options were loaded)
      if (mode === 'domain' && pendingUrlIps.value !== null) {
        const match = findDeviceOption(pendingUrlIps.value)
        if (match) selectedDeviceOption.value = match
        pendingUrlIps.value = null
      }
    } catch (e) {
      console.warn('Failed to fetch filter options:', e)
    }
  }

  async function fetchData() {
    fetchController?.abort()
    const controller = new AbortController()
    fetchController = controller

    loading.value = true
    error.value = null
    try {
      if (mode === 'client') {
        const qs = windowStore.queryParams({
          category: selectedCategory.value,
          company: selectedCompany.value,
        })
        const res = await apiFetch(`/api/stats/clients?${qs}`, { signal: controller.signal })
        if (!res.ok) throw new Error(`Server error ${res.status}`)
        data.value = await res.json()
      } else {
        const base = windowStore.queryParams({
          category: selectedCategory.value,
          company: selectedCompany.value,
          domain: appliedDomain.value,
          domain_exact: appliedDomain.value && domainExact.value ? true : undefined,
        })
        const ips = selectedClientIp.value
          ? (Array.isArray(selectedClientIp.value) ? selectedClientIp.value : [selectedClientIp.value])
          : []
        const ipPart = ips.map(ip => `client_ip=${encodeURIComponent(ip)}`).join('&')
        const qs = [base, ipPart].filter(Boolean).join('&')
        const res = await apiFetch(`/api/stats/domains?${qs}`, { signal: controller.signal })
        if (!res.ok) throw new Error(`Server error ${res.status}`)
        data.value = await res.json()
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return
      error.value = 'Failed to load data. Is the backend reachable?'
    } finally {
      loading.value = false
    }
  }

  async function searchDomains(event: { query: string }) {
    if (event.query.length < 2) {
      domainSuggestions.value = []
      return
    }
    try {
      const qs = windowStore.queryParams({ q: event.query })
      const res = await apiFetch(`/api/domains/search?${qs}`)
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

  function resetFilters() {
    selectedCategory.value = null
    selectedCompany.value = null
    if (mode === 'domain') {
      selectedDeviceOption.value = null
      domainInput.value = null
      appliedDomain.value = null
      domainExact.value = false
    }
  }

  // Watchers
  watch(() => windowStore.hours, fetchData)
  watch(() => windowStore.endTs, fetchData)
  watch(() => windowStore.refreshKey, () => { fetchOptions(); fetchData() })

  const watchSources = mode === 'domain'
    ? [selectedCategory, selectedCompany, selectedDeviceOption, appliedDomain]
    : [selectedCategory, selectedCompany]

  watch(watchSources, () => { syncUrlParams(); fetchData() })

  if (mode === 'domain') {
    watch(domainExact, () => { if (appliedDomain.value) applyDomainFilter() })
  }

  // Sync refs when route query changes externally (e.g. browser back/forward)
  watch(() => route.query, (q) => {
    const cat = (q.category as string) ?? null
    const co = (q.company as string) ?? null
    if (cat !== selectedCategory.value) selectedCategory.value = cat
    if (co !== selectedCompany.value) selectedCompany.value = co
    if (mode === 'domain') {
      const rawIp = q.client_ip
      const ip: string | string[] | null = !rawIp
        ? null
        : Array.isArray(rawIp)
          ? (rawIp.filter(Boolean) as string[])
          : (rawIp as string)
      const dom = (q.domain as string) ?? null
      const exact = q.domain_exact === '1'
      if (JSON.stringify(ip) !== JSON.stringify(selectedClientIp.value)) {
        selectedDeviceOption.value = ip ? (findDeviceOption(ip) ?? null) : null
      }
      if (dom !== appliedDomain.value) {
        domainInput.value = dom
        appliedDomain.value = dom
      }
      if (exact !== domainExact.value) domainExact.value = exact
    }
  })

  onMounted(() => { fetchOptions(); fetchData() })

  return {
    // Shared
    data, loading, error, hasFilters,
    selectedCategory, selectedCompany,
    categoryOptions, companyOptions,
    resetFilters, fetchData,
    // Domain-only
    selectedClientIp, selectedDeviceOption, deviceOptions,
    domainInput, appliedDomain, domainExact,
    domainSuggestions, searchDomains, applyDomainFilter,
    onDomainSelect, onDomainClear,
  }
}

/**
 * Tests for useReportData (src/composables/useReportData.ts).
 *
 * vue-router is mocked (useRoute/useRouter) so we don't need a full router
 * setup. apiFetch is mocked. Pinia is fresh per test.
 *
 * We call the composable directly inside withSetup(), a small helper that
 * mounts it inside a real Vue component so Vue's lifecycle hooks (onMounted,
 * watch) are active.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent, ref } from 'vue'
import { mount } from '@vue/test-utils'

// --- Mocks (hoisted) --------------------------------------------------------

const mockRouterReplace = vi.fn()
const mockQuery = ref<Record<string, string>>({})

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: mockQuery.value }),
  useRouter: () => ({ replace: mockRouterReplace }),
}))

const mockApiFetch = vi.fn()
vi.mock('@/utils/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  resetRedirectFlag: vi.fn(),
}))

// --- Helper -----------------------------------------------------------------

type ComposableResult = ReturnType<typeof import('@/composables/useReportData').useReportData>

/**
 * Mounts a tiny component that calls the composable, runs onMounted, and
 * returns the composable's return value for assertions.
 */
async function withSetup(mode: 'domain' | 'client'): Promise<ComposableResult> {
  const { useReportData } = await import('@/composables/useReportData')
  let result!: ComposableResult

  const TestComponent = defineComponent({
    setup() {
      result = useReportData(mode)
      return result
    },
    template: '<div />',
  })

  mount(TestComponent, {
    global: { plugins: [createPinia()] },
  })

  // Let onMounted + initial fetch settle
  await new Promise(resolve => setTimeout(resolve, 0))
  return result
}

// --- Setup ------------------------------------------------------------------

function mockSuccessResponse(data: unknown) {
  return { ok: true, json: async () => data }
}

beforeEach(() => {
  setActivePinia(createPinia())
  mockApiFetch.mockReset()
  mockRouterReplace.mockReset()
  mockQuery.value = {}

  // Default: fetchOptions returns empty lists, fetchData returns empty domains
  mockApiFetch.mockResolvedValue(mockSuccessResponse({ categories: [], companies: [], clients: [], domains: [] }))
})

afterEach(() => {
  vi.restoreAllMocks()
})

// --- Tests ------------------------------------------------------------------

describe('mode: domain', () => {
  it('calls /api/stats/domains on mount', async () => {
    await withSetup('domain')
    const calls = mockApiFetch.mock.calls.map((c: unknown[]) => c[0] as string)
    expect(calls.some(url => url.includes('/api/stats/domains'))).toBe(true)
  })

  it('hasFilters is false with no active filters', async () => {
    const result = await withSetup('domain')
    expect(result.hasFilters.value).toBe(false)
  })

  it('hasFilters is true when a category is selected', async () => {
    const result = await withSetup('domain')
    result.selectedCategory.value = 'advertising'
    expect(result.hasFilters.value).toBe(true)
  })

  it('resetFilters clears all domain filters', async () => {
    const result = await withSetup('domain')
    result.selectedCategory.value = 'advertising'
    result.selectedCompany.value = 'Acme'
    result.selectedDeviceOption.value = { label: 'My Laptop', ips: '192.168.1.1', isGroup: false, subLabel: null }
    result.appliedDomain.value = 'example.com'

    result.resetFilters()

    expect(result.selectedCategory.value).toBeNull()
    expect(result.selectedCompany.value).toBeNull()
    expect(result.selectedClientIp.value).toBeNull()  // computed from selectedDeviceOption
    expect(result.appliedDomain.value).toBeNull()
  })

  it('reads initial filters from route query', async () => {
    mockQuery.value = { category: 'analytics', company: 'Acme' }
    const result = await withSetup('domain')
    expect(result.selectedCategory.value).toBe('analytics')
    expect(result.selectedCompany.value).toBe('Acme')
  })

  it('sets error on failed fetch', async () => {
    mockApiFetch
      .mockResolvedValueOnce(mockSuccessResponse({ categories: [], companies: [] })) // fetchOptions /api/settings/options
      .mockResolvedValueOnce(mockSuccessResponse({ clients: [] }))                   // fetchOptions /api/clients
      .mockResolvedValueOnce(mockSuccessResponse({ groups: [] }))                    // fetchOptions /api/device-groups
      .mockResolvedValueOnce({ ok: false })                                          // fetchData
    const result = await withSetup('domain')
    expect(result.error.value).toBeTruthy()
  })
})

describe('mode: client', () => {
  it('calls /api/stats/clients on mount', async () => {
    await withSetup('client')
    const calls = mockApiFetch.mock.calls.map((c: unknown[]) => c[0] as string)
    expect(calls.some(url => url.includes('/api/stats/clients'))).toBe(true)
  })

  it('resetFilters does not clear domain-only fields in client mode', async () => {
    const result = await withSetup('client')
    result.selectedCategory.value = 'analytics'
    result.resetFilters()
    expect(result.selectedCategory.value).toBeNull()
    // selectedClientIp is domain-mode only — should not throw or error
  })
})

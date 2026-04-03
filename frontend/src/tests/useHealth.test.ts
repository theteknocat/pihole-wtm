/**
 * Tests for useHealth (src/composables/useHealth.ts).
 *
 * apiFetch is mocked. Pinia is set up fresh per test so the window store
 * is clean. Each test mounts a real component via withSetup() so that
 * onMounted/onUnmounted lifecycle hooks fire correctly. The wrapper is
 * unmounted in afterEach to keep the module-level mountCount at zero
 * between tests.
 *
 * vi.useFakeTimers is scoped to setInterval/clearInterval only — faking
 * setTimeout would break the Promise tick inside withSetup().
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { defineComponent } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { useWindowStore } from '@/stores/window'

// Mock apiFetch before importing useHealth
const mockApiFetch = vi.fn()
vi.mock('@/utils/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
  resetRedirectFlag: vi.fn(),
}))

// Import after mocking
import { useHealth } from '@/composables/useHealth'

// --- Types ------------------------------------------------------------------

type HealthResult = ReturnType<typeof useHealth>

// --- Helper -----------------------------------------------------------------

let wrapper: VueWrapper | null = null

/**
 * Mounts a tiny component that calls the composable, triggering onMounted
 * (which fires the initial fetchHealth and starts the tick timer). Awaits
 * one Promise tick so the async fetch settles before assertions run.
 */
async function withSetup(): Promise<HealthResult> {
  let result!: HealthResult

  const TestComponent = defineComponent({
    setup() {
      result = useHealth()
      return {}
    },
    template: '<div />',
  })

  wrapper = mount(TestComponent, { global: { plugins: [createPinia()] } })
  await new Promise(resolve => setTimeout(resolve, 0))
  return result
}

// --- Fixtures ---------------------------------------------------------------

function mockHealthResponse(overrides = {}) {
  return {
    ok: true,
    json: async () => ({
      status: 'ok',
      pihole_api_url: 'http://pihole.local',
      version: '0.1.0',
      sources: [],
      last_synced_at: 1000,
      stored_queries: 500,
      sync_active: true,
      sync_source: 'env',
      oldest_ts: 100,
      newest_ts: 2000,
      ...overrides,
    }),
  }
}

// --- Setup ------------------------------------------------------------------

beforeEach(() => {
  // Only fake setInterval/clearInterval to prevent the 5-second tick timer
  // from running. Leaving setTimeout real so withSetup()'s Promise tick works.
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
  setActivePinia(createPinia())
  mockApiFetch.mockReset()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.useRealTimers()
})

// --- Tests ------------------------------------------------------------------

describe('fetchHealth()', () => {
  it('sets health data on successful response', async () => {
    mockApiFetch.mockResolvedValue(mockHealthResponse())

    const { health } = await withSetup()

    expect(health.value).not.toBeNull()
    expect(health.value?.status).toBe('ok')
    expect(health.value?.stored_queries).toBe(500)
  })

  it('strips oldest_ts and newest_ts from health data', async () => {
    mockApiFetch.mockResolvedValue(mockHealthResponse())

    const { health } = await withSetup()

    // oldest_ts / newest_ts go to the window store, not health
    expect((health.value as Record<string, unknown>)?.oldest_ts).toBeUndefined()
    expect((health.value as Record<string, unknown>)?.newest_ts).toBeUndefined()
  })

  it('feeds oldest_ts and newest_ts into the window store', async () => {
    mockApiFetch.mockResolvedValue(mockHealthResponse({ oldest_ts: 100, newest_ts: 2000 }))

    await withSetup()
    const windowStore = useWindowStore()

    expect(windowStore.oldestTs).toBe(100)
    expect(windowStore.newestTs).toBe(2000)
  })

  it('sets error to true on non-ok response', async () => {
    mockApiFetch.mockResolvedValue({ ok: false })

    const { error } = await withSetup()

    expect(error.value).toBe(true)
  })

  it('sets error to true on network failure', async () => {
    mockApiFetch.mockRejectedValue(new Error('network'))

    const { error } = await withSetup()

    expect(error.value).toBe(true)
  })

  it('clears error on successful subsequent fetch', async () => {
    mockApiFetch.mockResolvedValueOnce({ ok: false })
    mockApiFetch.mockResolvedValueOnce(mockHealthResponse())

    const { fetchHealth, error } = await withSetup()
    expect(error.value).toBe(true)

    await fetchHealth()
    expect(error.value).toBe(false)
  })
})

/**
 * Tests for DomainClientsDialog (src/components/layout/DomainClientsDialog.vue).
 *
 * PrimeVue components are mocked at the module level to avoid pulling in the
 * full PrimeVue runtime. DataTable is given a minimal implementation that
 * iterates its `value` prop and renders the Column body slot per row, which
 * is enough to test the device link click behaviour.
 *
 * fetch is stubbed per-test via vi.stubGlobal. vue-router is mocked so
 * router.push calls can be asserted without a real router.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DomainClientsDialog from '@/components/layout/DomainClientsDialog.vue'

// --- Mocks (hoisted so they're available inside vi.mock factories) -----------

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    props: ['visible'],
    emits: ['update:visible', 'hide'],
    template: '<div><slot name="header" /><slot /></div>',
  },
}))

// DataTable iterates `value` and exposes each row to the Column body slot.
// DataTable provides its rows reactively so Column re-renders after the fetch resolves.
vi.mock('primevue/datatable', async () => {
  const { h, provide, computed } = await import('vue')
  return {
    default: {
      name: 'DataTable',
      props: ['value'],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setup(props: any, ctx: any) {
        provide('dtRows', computed(() => props.value ?? []))
        return () => h('div', { class: 'data-table' }, ctx.slots.default?.())
      },
    },
  }
})

vi.mock('primevue/column', async () => {
  const { h, inject, computed } = await import('vue')
  return {
    default: {
      name: 'Column',
      props: ['field', 'header'],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setup(_props: any, ctx: any) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const rows = inject('dtRows', computed(() => [])) as any
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return () => h('div', { class: 'column' }, rows.value.map((row: any, i: number) =>
          ctx.slots.body?.({ data: row, index: i })
        ))
      },
    },
  }
})

vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    props: ['icon', 'severity', 'text', 'rounded', 'size', 'title', 'ariaLabel'],
    emits: ['click'],
    template: '<button @click="$emit(\'click\')" />',
  },
}))

vi.mock('primevue/progressspinner', () => ({
  default: { name: 'ProgressSpinner', template: '<div class="spinner" />' },
}))

vi.mock('@/components/layout/ClientNameDialog.vue', () => ({
  default: { name: 'ClientNameDialog', template: '<div />' },
}))

// --- Helpers -----------------------------------------------------------------

type FetchMock = ReturnType<typeof vi.fn>

function stubFetch(data: unknown, ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok,
    json: async () => data,
  }))
}

function mountDialog(domain = 'ads.example.com') {
  return mount(DomainClientsDialog, {
    props: { domain },
    global: { plugins: [createPinia()] },
  })
}

const sampleClients = {
  window_hours: 24,
  clients: [
    { client_ip: '192.168.1.1', client_name: 'My Laptop', query_count: 5, blocked_count: 2, allowed_count: 3, block_rate: 40.0 },
    { client_ip: '192.168.1.2', client_name: null,         query_count: 2, blocked_count: 0, allowed_count: 2, block_rate: 0.0 },
  ],
}

// --- Setup ------------------------------------------------------------------

beforeEach(() => {
  setActivePinia(createPinia())
  mockPush.mockReset()
  vi.unstubAllGlobals()
})

// --- Tests ------------------------------------------------------------------

describe('DomainClientsDialog', () => {
  it('fetches from /api/stats/clients with the domain param on mount', async () => {
    stubFetch(sampleClients)
    mountDialog('ads.example.com')
    await new Promise(resolve => setTimeout(resolve, 0))

    const calls = (globalThis.fetch as FetchMock).mock.calls
    expect(calls.length).toBe(1)
    const url: string = calls[0][0]
    expect(url).toContain('/api/stats/clients')
    expect(url).toContain('domain=ads.example.com')
  })

  it('shows an error message when the fetch fails', async () => {
    stubFetch(null, false)
    const wrapper = mountDialog()
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('Failed to load device breakdown')
  })

  it('navigates to /domains-report filtered by client_ip when a device link is clicked', async () => {
    stubFetch(sampleClients)
    const wrapper = mountDialog()
    await new Promise(resolve => setTimeout(resolve, 0))

    // Find the anchor for the first client (192.168.1.1 / My Laptop)
    const links = wrapper.findAll('a[href="#device-details"]')
    expect(links.length).toBeGreaterThan(0)
    await links[0].trigger('click')

    expect(mockPush).toHaveBeenCalledWith({
      path: '/domains-report',
      query: { client_ip: '192.168.1.1' },
    })
  })
})

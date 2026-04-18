/**
 * Tests for ClientBreakdownDialog (src/components/layout/ClientBreakdownDialog.vue).
 *
 * PrimeVue components are mocked at the module level to avoid pulling in the
 * full PrimeVue runtime. DataTable is given a minimal implementation that
 * iterates its `value` prop and renders the Column body slot per row.
 *
 * @/utils/api is mocked so apiFetch (used by useDeviceGroups) doesn't pull
 * in the real router. fetch is stubbed per-test for the /api/stats/clients call.
 * vue-router is mocked for router.push assertions.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import ClientBreakdownDialog from '@/components/layout/ClientBreakdownDialog.vue'
import { apiFetch } from '@/utils/api'
import type { ClientFilter } from '@/types/api'

// --- Mocks (hoisted so they're available inside vi.mock factories) -----------

const { mockPush } = vi.hoisted(() => ({ mockPush: vi.fn() }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}))

// Prevent apiFetch → router.ts → createRouter import chain
vi.mock('@/utils/api', () => ({
  apiFetch: vi.fn(),
}))

vi.mock('@/components/layout/DeviceStatsDialog.vue', () => ({
  default: {
    name: 'DeviceStatsDialog',
    props: ['clientIps', 'clientName'],
    emits: ['close', 'navigate'],
    template: '<div data-testid="device-stats-dialog" />',
  },
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
    props: ['icon', 'severity', 'text', 'rounded', 'size', 'title', 'ariaLabel', 'label'],
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

function stubGroups(groups: unknown[] = []) {
  vi.mocked(apiFetch).mockResolvedValue({
    ok: true,
    json: async () => ({ groups }),
  } as Response)
}

function mountDialog(filter: ClientFilter = { type: 'domain', value: 'ads.example.com' }) {
  return mount(ClientBreakdownDialog, {
    props: { filter },
    global: { plugins: [createPinia()] },
  })
}

const tick = () => new Promise(resolve => setTimeout(resolve, 0))

const sampleClients = {
  window_hours: 24,
  clients: [
    { client_ip: '192.168.1.1', client_name: 'My Laptop', query_count: 5, blocked_count: 2, allowed_count: 3, block_rate: 40.0 },
    { client_ip: '192.168.1.2', client_name: null,         query_count: 2, blocked_count: 0, allowed_count: 2, block_rate: 0.0 },
  ],
}

const sampleGroup = {
  id: 1,
  name: 'Home Devices',
  members: [
    { client_ip: '192.168.1.1', client_name: 'My Laptop' },
    { client_ip: '192.168.1.2', client_name: null },
  ],
}

// --- Setup ------------------------------------------------------------------

beforeEach(() => {
  setActivePinia(createPinia())
  mockPush.mockReset()
  vi.unstubAllGlobals()
  stubGroups() // default: no groups
})

// --- Tests ------------------------------------------------------------------

describe('ClientBreakdownDialog', () => {
  it('fetches from /api/stats/clients with the domain param on mount', async () => {
    stubFetch(sampleClients)
    mountDialog({ type: 'domain', value: 'ads.example.com' })
    await tick()

    const calls = (globalThis.fetch as FetchMock).mock.calls
    expect(calls.length).toBe(1)
    const url: string = calls[0][0]
    expect(url).toContain('/api/stats/clients')
    expect(url).toContain('domain=ads.example.com')
  })

  it('fetches with category param when filter type is category', async () => {
    stubFetch(sampleClients)
    mountDialog({ type: 'category', value: 'advertising' })
    await tick()

    const calls = (globalThis.fetch as FetchMock).mock.calls
    expect(calls.length).toBe(1)
    const url: string = calls[0][0]
    expect(url).toContain('/api/stats/clients')
    expect(url).toContain('category=advertising')
  })

  it('fetches with company param when filter type is company', async () => {
    stubFetch(sampleClients)
    mountDialog({ type: 'company', value: 'Google' })
    await tick()

    const calls = (globalThis.fetch as FetchMock).mock.calls
    expect(calls.length).toBe(1)
    const url: string = calls[0][0]
    expect(url).toContain('/api/stats/clients')
    expect(url).toContain('company=Google')
  })

  it('shows an error message when the fetch fails', async () => {
    stubFetch(null, false)
    const wrapper = mountDialog()
    await tick()

    expect(wrapper.text()).toContain('Failed to load device breakdown')
  })

  it('opens DeviceStatsDialog when a device name is clicked', async () => {
    stubFetch(sampleClients)
    const wrapper = mountDialog({ type: 'domain', value: 'ads.example.com' })
    await tick()

    const links = wrapper.findAll('a[href="#device-stats"]')
    expect(links.length).toBeGreaterThan(0)
    await links[0].trigger('click')

    const statsDialog = wrapper.findComponent({ name: 'DeviceStatsDialog' })
    expect(statsDialog.exists()).toBe(true)
    expect(statsDialog.props('clientIps')).toEqual(['192.168.1.1'])
  })

  it('passes client_name to DeviceStatsDialog for a named device', async () => {
    stubFetch(sampleClients)
    const wrapper = mountDialog()
    await tick()

    const links = wrapper.findAll('a[href="#device-stats"]')
    await links[0].trigger('click')

    const statsDialog = wrapper.findComponent({ name: 'DeviceStatsDialog' })
    expect(statsDialog.props('clientName')).toBe('My Laptop')
  })

  it('shows a group row when 2+ group members appear in the data', async () => {
    stubFetch(sampleClients)
    stubGroups([sampleGroup])
    const wrapper = mountDialog()
    await tick()

    expect(wrapper.text()).toContain('Home Devices')
  })

  it('opens DeviceStatsDialog with all member IPs when a group name is clicked', async () => {
    stubFetch(sampleClients)
    stubGroups([sampleGroup])
    const wrapper = mountDialog()
    await tick()

    const links = wrapper.findAll('a[href="#device-stats"]')
    expect(links.length).toBeGreaterThan(0)
    await links[0].trigger('click')

    const statsDialog = wrapper.findComponent({ name: 'DeviceStatsDialog' })
    expect(statsDialog.exists()).toBe(true)
    expect(statsDialog.props('clientIps')).toEqual(['192.168.1.1', '192.168.1.2'])
    expect(statsDialog.props('clientName')).toBe('Home Devices')
  })

  it('shows device as a single row when only 1 group member appears in the data', async () => {
    // Only one member present — group threshold not met, shown as plain device
    stubFetch({ ...sampleClients, clients: [sampleClients.clients[0]] })
    stubGroups([sampleGroup])
    const wrapper = mountDialog()
    await tick()

    expect(wrapper.text()).not.toContain('Home Devices')
    expect(wrapper.text()).toContain('My Laptop')
  })
})

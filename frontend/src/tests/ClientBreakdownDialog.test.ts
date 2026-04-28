/**
 * Tests for ClientBreakdownDialog (src/components/layout/ClientBreakdownDialog.vue).
 *
 * PrimeVue components are mocked at the module level to avoid pulling in the
 * full PrimeVue runtime. PvChart is given a minimal stub so we can read chart
 * data/options and simulate bar clicks by calling options.onClick() directly.
 *
 * @/utils/api is mocked so apiFetch (used by useDeviceGroups) doesn't pull
 * in the real router. fetch is stubbed per-test for the /api/stats/clients call.
 * vue-router is mocked for router.push assertions.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'
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

vi.mock('primevue/chart', () => ({
  default: {
    name: 'PvChart',
    props: ['type', 'data', 'options'],
    template: '<canvas data-testid="pv-chart" />',
  },
}))

vi.mock('@/components/timeline/TrackerTimelineChart.vue', () => ({
  default: {
    name: 'TrackerTimelineChart',
    props: ['series', 'bucketTimestamps', 'bucketSeconds'],
    template: '<div data-testid="tracker-timeline" />',
  },
}))

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
  it('fetches from /api/stats/clients with the correct params on mount', async () => {
    stubFetch(sampleClients)
    mountDialog({ type: 'domain', value: 'ads.example.com' })
    await tick()

    const calls = (globalThis.fetch as FetchMock).mock.calls
    expect(calls.length).toBe(1)
    const url: string = calls[0][0]
    expect(url).toContain('/api/stats/clients')
    expect(url).toContain('domain=ads.example.com')
    expect(url).toContain('include_timeline=true')
  })

  it('fetches with category param when filter type is category', async () => {
    stubFetch(sampleClients)
    mountDialog({ type: 'category', value: 'advertising' })
    await tick()

    const calls = (globalThis.fetch as FetchMock).mock.calls
    expect(calls.length).toBe(1)
    const url: string = calls[0][0]
    expect(url).toContain('category=advertising')
    expect(url).toContain('include_timeline=true')
  })

  it('fetches with company param when filter type is company', async () => {
    stubFetch(sampleClients)
    mountDialog({ type: 'company', value: 'Google' })
    await tick()

    const calls = (globalThis.fetch as FetchMock).mock.calls
    expect(calls.length).toBe(1)
    const url: string = calls[0][0]
    expect(url).toContain('company=Google')
    expect(url).toContain('include_timeline=true')
  })

  it('shows an error message when the fetch fails', async () => {
    stubFetch(null, false)
    const wrapper = mountDialog()
    await tick()

    expect(wrapper.text()).toContain('Failed to load device breakdown')
  })

  it('renders a bar chart with device labels after successful fetch', async () => {
    stubFetch(sampleClients)
    const wrapper = mountDialog()
    await tick()

    const chart = wrapper.findComponent({ name: 'PvChart' })
    expect(chart.exists()).toBe(true)
    expect(chart.props('data').labels).toContain('My Laptop')
    expect(chart.props('data').labels).toContain('192.168.1.2')
  })

  it('opens DeviceStatsDialog when a bar is clicked', async () => {
    stubFetch(sampleClients)
    const wrapper = mountDialog()
    await tick()

    const chart = wrapper.findComponent({ name: 'PvChart' })
    chart.props('options').onClick(null, [{ index: 0 }])
    await nextTick()

    expect(wrapper.findComponent({ name: 'DeviceStatsDialog' }).exists()).toBe(true)
  })

  it('passes clientIps and clientName to DeviceStatsDialog for a named device', async () => {
    stubFetch(sampleClients)
    const wrapper = mountDialog()
    await tick()

    const chart = wrapper.findComponent({ name: 'PvChart' })
    chart.props('options').onClick(null, [{ index: 0 }])
    await nextTick()

    const statsDialog = wrapper.findComponent({ name: 'DeviceStatsDialog' })
    expect(statsDialog.props('clientIps')).toEqual(['192.168.1.1'])
    expect(statsDialog.props('clientName')).toBe('My Laptop')
  })

  it('merges group members into a single bar when a group is configured', async () => {
    stubFetch(sampleClients)
    stubGroups([sampleGroup])
    const wrapper = mountDialog()
    await tick()

    const chart = wrapper.findComponent({ name: 'PvChart' })
    expect(chart.props('data').labels).toEqual(['Home Devices'])
  })

  it('opens DeviceStatsDialog with all member IPs when a group bar is clicked', async () => {
    stubFetch(sampleClients)
    stubGroups([sampleGroup])
    const wrapper = mountDialog()
    await tick()

    const chart = wrapper.findComponent({ name: 'PvChart' })
    chart.props('options').onClick(null, [{ index: 0 }])
    await nextTick()

    const statsDialog = wrapper.findComponent({ name: 'DeviceStatsDialog' })
    expect(statsDialog.exists()).toBe(true)
    expect(statsDialog.props('clientIps')).toEqual(['192.168.1.1', '192.168.1.2'])
    expect(statsDialog.props('clientName')).toBe('Home Devices')
  })

  it('shows individual device bars when only 1 group member appears in the data', async () => {
    stubFetch({ ...sampleClients, clients: [sampleClients.clients[0]] })
    stubGroups([sampleGroup])
    const wrapper = mountDialog()
    await tick()

    const chart = wrapper.findComponent({ name: 'PvChart' })
    expect(chart.props('data').labels).not.toContain('Home Devices')
    expect(chart.props('data').labels).toContain('My Laptop')
  })

  it('shows TrackerTimelineChart when timeline data is present', async () => {
    stubFetch({
      ...sampleClients,
      bucket_seconds: 3600,
      bucket_timestamps: [1700000000, 1700003600],
      by_client_timeline: [
        { client_ip: '192.168.1.1', client_name: 'My Laptop', counts: [3, 2] },
      ],
    })
    const wrapper = mountDialog()
    await tick()

    expect(wrapper.findComponent({ name: 'TrackerTimelineChart' }).exists()).toBe(true)
  })
})

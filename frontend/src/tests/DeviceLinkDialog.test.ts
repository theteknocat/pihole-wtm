/**
 * Tests for DeviceLinkDialog (src/components/layout/DeviceLinkDialog.vue).
 *
 * PrimeVue components are mocked at the module level. fetch is stubbed
 * per-test via vi.stubGlobal.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import DeviceLinkDialog from '@/components/layout/DeviceLinkDialog.vue'
import type { ClientStat, DeviceGroup } from '@/types/api'

// --- Mocks -------------------------------------------------------------------

vi.mock('primevue/dialog', () => ({
  default: {
    name: 'Dialog',
    props: ['visible'],
    emits: ['update:visible', 'hide'],
    template: '<div><slot name="header" /><slot /><slot name="footer" /></div>',
  },
}))

vi.mock('primevue/inputtext', () => ({
  default: {
    name: 'InputText',
    props: ['modelValue', 'maxlength'],
    emits: ['update:modelValue'],
    template: '<input type="text" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}))

vi.mock('primevue/checkbox', () => ({
  default: {
    name: 'Checkbox',
    props: ['modelValue', 'binary', 'disabled'],
    emits: ['change'],
    template: '<input type="checkbox" :checked="modelValue" :disabled="disabled" @change="$emit(\'change\')" />',
  },
}))

vi.mock('primevue/button', () => ({
  default: {
    name: 'Button',
    props: ['icon', 'severity', 'text', 'rounded', 'size', 'label', 'loading', 'disabled'],
    emits: ['click'],
    template: '<button :disabled="disabled || loading" @click="$emit(\'click\')">{{ label }}</button>',
  },
}))

// --- Helpers -----------------------------------------------------------------

type FetchMock = ReturnType<typeof vi.fn>

function stubFetch(ok = true) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok,
    json: async () => (ok ? { status: 'ok', id: 42 } : { detail: 'Server error' }),
  }))
}

const sampleClients: ClientStat[] = [
  { client_ip: '192.168.1.1', client_name: 'My Laptop', query_count: 10, blocked_count: 3, allowed_count: 7, block_rate: 30 },
  { client_ip: '192.168.1.2', client_name: 'Phone',     query_count: 5,  blocked_count: 1, allowed_count: 4, block_rate: 20 },
  { client_ip: '192.168.1.3', client_name: null,         query_count: 2,  blocked_count: 0, allowed_count: 2, block_rate: 0  },
]

const sampleGroup: DeviceGroup = {
  id: 7,
  name: 'My Devices',
  members: [
    { client_ip: '192.168.1.1', client_name: 'My Laptop' },
    { client_ip: '192.168.1.2', client_name: 'Phone' },
  ],
}

function mountCreate(anchorIp = '192.168.1.1') {
  return mount(DeviceLinkDialog, {
    props: {
      anchorIp,
      anchorName: sampleClients.find(c => c.client_ip === anchorIp)?.client_name ?? null,
      allClients: sampleClients,
      existingGroup: null,
    },
    global: { plugins: [createPinia()] },
  })
}

function mountEdit() {
  return mount(DeviceLinkDialog, {
    props: {
      anchorIp: '192.168.1.1',
      anchorName: 'My Laptop',
      allClients: sampleClients,
      existingGroup: sampleGroup,
    },
    global: { plugins: [createPinia()] },
  })
}

// --- Setup ------------------------------------------------------------------

beforeEach(() => {
  setActivePinia(createPinia())
  vi.unstubAllGlobals()
})

// --- Tests ------------------------------------------------------------------

describe('DeviceLinkDialog', () => {
  it('pre-selects the anchor IP with a disabled checkbox', () => {
    const wrapper = mountCreate()
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    // The anchor IP checkbox is the first one (it's always shown first or at its position in allClients)
    const anchorCheckbox = checkboxes.find(c => {
      // Find the checkbox in the same label as the anchor IP
      return c.attributes('disabled') !== undefined && (c.element as HTMLInputElement).checked
    })
    expect(anchorCheckbox).toBeTruthy()
    expect((anchorCheckbox!.element as HTMLInputElement).checked).toBe(true)
    expect(anchorCheckbox!.attributes('disabled')).toBeDefined()
  })

  it('disables the save button when only 1 IP is selected', () => {
    const wrapper = mountCreate()
    // Only anchor IP selected by default — that's 1 IP
    // Find the Link/Save button (last button in footer)
    const buttons = wrapper.findAll('button')
    const saveButton = buttons[buttons.length - 1]
    expect(saveButton.attributes('disabled')).toBeDefined()
  })

  it('enables the save button when name and 2+ IPs are provided', async () => {
    const wrapper = mountCreate()

    // Type a name
    await wrapper.find('input[type="text"]').setValue('Test Group')

    // Select a second IP (192.168.1.2 — not the anchor)
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    const secondCheckbox = checkboxes.find(c => !(c.element as HTMLInputElement).checked && !c.attributes('disabled'))
    expect(secondCheckbox).toBeTruthy()
    await secondCheckbox!.trigger('change')

    const buttons = wrapper.findAll('button')
    const saveButton = buttons[buttons.length - 1]
    expect(saveButton.attributes('disabled')).toBeUndefined()
  })

  it('POSTs to /api/device-groups on create', async () => {
    stubFetch()
    const wrapper = mountCreate()

    await wrapper.find('input[type="text"]').setValue('New Group')

    // Select the second device
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    const unchecked = checkboxes.find(c => !(c.element as HTMLInputElement).checked && !c.attributes('disabled'))
    await unchecked!.trigger('change')

    // Click Link button
    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    const mockFetch = globalThis.fetch as FetchMock
    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/device-groups')
    expect(opts.method).toBe('POST')
    const body = JSON.parse(opts.body)
    expect(body.name).toBe('New Group')
    expect(body.member_ips).toContain('192.168.1.1')
  })

  it('PUTs to /api/device-groups/{id} on update', async () => {
    stubFetch()
    const wrapper = mountEdit()

    // Name is pre-filled — just click Save
    const buttons = wrapper.findAll('button')
    const saveButton = buttons[buttons.length - 1]
    await saveButton.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    const mockFetch = globalThis.fetch as FetchMock
    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/device-groups/7')
    expect(opts.method).toBe('PUT')
  })

  it('DELETEs on unlink', async () => {
    stubFetch()
    const wrapper = mountEdit()

    // The "Unlink Group" button is the first button in the footer
    const buttons = wrapper.findAll('button')
    // Unlink button has label "Unlink Group" — find by text
    const unlinkBtn = buttons.find(b => b.text().includes('Unlink'))
    expect(unlinkBtn).toBeTruthy()
    await unlinkBtn!.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    const mockFetch = globalThis.fetch as FetchMock
    expect(mockFetch).toHaveBeenCalledOnce()
    const [url, opts] = mockFetch.mock.calls[0]
    expect(url).toBe('/api/device-groups/7')
    expect(opts.method).toBe('DELETE')
  })

  it('emits saved on successful create', async () => {
    stubFetch()
    const wrapper = mountCreate()

    await wrapper.find('input[type="text"]').setValue('New Group')
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    const unchecked = checkboxes.find(c => !(c.element as HTMLInputElement).checked && !c.attributes('disabled'))
    await unchecked!.trigger('change')

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('emits saved on successful delete', async () => {
    stubFetch()
    const wrapper = mountEdit()

    const buttons = wrapper.findAll('button')
    const unlinkBtn = buttons.find(b => b.text().includes('Unlink'))
    await unlinkBtn!.trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('shows an error when the fetch fails', async () => {
    stubFetch(false)
    const wrapper = mountCreate()

    await wrapper.find('input[type="text"]').setValue('New Group')
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    const unchecked = checkboxes.find(c => !(c.element as HTMLInputElement).checked && !c.attributes('disabled'))
    await unchecked!.trigger('change')

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1].trigger('click')
    await new Promise(resolve => setTimeout(resolve, 0))

    expect(wrapper.text()).toContain('Server error')
    expect(wrapper.emitted('saved')).toBeFalsy()
  })

  it('pre-fills name from existingGroup in edit mode', () => {
    const wrapper = mountEdit()
    const nameInput = wrapper.find('input[type="text"]')
    expect((nameInput.element as HTMLInputElement).value).toBe('My Devices')
  })

  it('shows Unlink Group button only in edit mode', () => {
    const createWrapper = mountCreate()
    const editWrapper = mountEdit()

    const createButtons = createWrapper.findAll('button')
    expect(createButtons.some(b => b.text().includes('Unlink'))).toBe(false)

    const editButtons = editWrapper.findAll('button')
    expect(editButtons.some(b => b.text().includes('Unlink'))).toBe(true)
  })
})

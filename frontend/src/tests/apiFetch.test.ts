/**
 * Tests for apiFetch (src/utils/api.ts).
 *
 * fetch is stubbed per-test. The router push spy and useAuth mock are
 * defined via vi.hoisted() so they're available inside the hoisted vi.mock()
 * factory blocks (vi.mock calls are hoisted to the top of the file by Vitest).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// vi.hoisted() runs before any imports, so these refs are available inside vi.mock() factories
const { mockPush, mockIsAuthenticated } = vi.hoisted(() => ({
  mockPush: vi.fn(),
  mockIsAuthenticated: { value: false },
}))

vi.mock('@/router', () => ({
  getRouter: () => ({ push: mockPush }),
}))

vi.mock('@/composables/useAuth', () => ({
  useAuth: () => ({ isAuthenticated: mockIsAuthenticated }),
}))

beforeEach(() => {
  vi.resetModules()
  mockIsAuthenticated.value = false
  mockPush.mockReset()
})

describe('apiFetch', () => {
  it('returns response unchanged for a normal 200', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 200, ok: true }))
    const { apiFetch } = await import('@/utils/api')
    const res = await apiFetch('/api/health')
    expect(res.status).toBe(200)
  })

  it('clears auth state and redirects to /login on 401 when authenticated', async () => {
    mockIsAuthenticated.value = true
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 401, ok: false }))
    const { apiFetch } = await import('@/utils/api')
    await apiFetch('/api/health')
    expect(mockIsAuthenticated.value).toBe(false)
    expect(mockPush).toHaveBeenCalledWith('/login')
  })

  it('does not redirect on 401 when already unauthenticated', async () => {
    mockIsAuthenticated.value = false
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 401, ok: false }))
    const { apiFetch } = await import('@/utils/api')
    await apiFetch('/api/health')
    expect(mockPush).not.toHaveBeenCalled()
  })

  it('passes through non-401 error responses without redirecting', async () => {
    mockIsAuthenticated.value = true
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 503, ok: false }))
    const { apiFetch } = await import('@/utils/api')
    const res = await apiFetch('/api/health')
    expect(res.status).toBe(503)
    expect(mockPush).not.toHaveBeenCalled()
    expect(mockIsAuthenticated.value).toBe(true)
  })
})

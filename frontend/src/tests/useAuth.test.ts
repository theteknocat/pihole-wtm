/**
 * Tests for useAuth (src/composables/useAuth.ts).
 *
 * useAuth holds state at module level (refs outside the function), so all
 * calls to useAuth() share the same refs. We reset them in beforeEach to
 * prevent tests from bleeding into each other.
 *
 * fetch is stubbed per-test using vi.stubGlobal.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuth } from '@/composables/useAuth'

// resetRedirectFlag is a no-op in these tests — mock it to avoid real module deps
vi.mock('@/utils/api', () => ({
  resetRedirectFlag: vi.fn(),
}))

function resetAuthState() {
  const { isAuthenticated, piholeUrl, checking } = useAuth()
  isAuthenticated.value = false
  piholeUrl.value = null
  checking.value = true
}

beforeEach(() => {
  resetAuthState()
})

describe('checkSession()', () => {
  it('sets isAuthenticated to true on authenticated response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: true, pihole_url: 'http://pihole.local', pihole_url_from_env: false }),
    }))

    const { checkSession, isAuthenticated, piholeUrl } = useAuth()
    const result = await checkSession()

    expect(result).toBe(true)
    expect(isAuthenticated.value).toBe(true)
    expect(piholeUrl.value).toBe('http://pihole.local')
  })

  it('sets isAuthenticated to false on unauthenticated response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: false, pihole_url: null }),
    }))

    const { checkSession, isAuthenticated } = useAuth()
    const result = await checkSession()

    expect(result).toBe(false)
    expect(isAuthenticated.value).toBe(false)
  })

  it('sets isAuthenticated to false on network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network error')))

    const { checkSession, isAuthenticated } = useAuth()
    const result = await checkSession()

    expect(result).toBe(false)
    expect(isAuthenticated.value).toBe(false)
  })

  it('sets checking to false after completion', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ authenticated: false }),
    }))

    const { checkSession, checking } = useAuth()
    expect(checking.value).toBe(true)
    await checkSession()
    expect(checking.value).toBe(false)
  })
})

describe('login()', () => {
  it('returns ok=true and sets auth state on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', pihole_url: 'http://pihole.local' }),
    }))

    const { login, isAuthenticated, piholeUrl } = useAuth()
    const result = await login('correct-password', 'http://pihole.local')

    expect(result.ok).toBe(true)
    expect(isAuthenticated.value).toBe(true)
    expect(piholeUrl.value).toBe('http://pihole.local')
  })

  it('returns ok=false with error on wrong password', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ status: 'Invalid password' }),
    }))

    const { login, isAuthenticated } = useAuth()
    const result = await login('wrong-password')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Invalid password')
    expect(isAuthenticated.value).toBe(false)
  })

  it('returns ok=false on network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network')))

    const { login } = useAuth()
    const result = await login('password')

    expect(result.ok).toBe(false)
    expect(result.error).toBe('Could not reach server')
  })
})

describe('logout()', () => {
  it('clears isAuthenticated', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    const { logout, isAuthenticated } = useAuth()
    isAuthenticated.value = true

    await logout()

    expect(isAuthenticated.value).toBe(false)
  })

  it('clears piholeUrl when not from env', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }))

    const { logout, piholeUrl } = useAuth()
    piholeUrl.value = 'http://pihole.local'

    await logout()

    expect(piholeUrl.value).toBeNull()
  })
})

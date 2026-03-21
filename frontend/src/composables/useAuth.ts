import { ref } from 'vue'
import { resetRedirectFlag } from '@/utils/api'

/**
 * Reactive auth state shared across the app.
 *
 * State is held at module level so all consumers share the same refs.
 * `checkSession()` hits the backend to verify the HTTP-only session cookie.
 */
const isAuthenticated = ref(false)
const piholeUrl = ref<string | null>(null)
const piholeUrlFromEnv = ref(false)
const checking = ref(true) // true until the first checkSession completes

async function checkSession(): Promise<boolean> {
  try {
    const res = await fetch('/api/auth/status')
    if (!res.ok) {
      isAuthenticated.value = false
      return false
    }
    const data = await res.json()
    isAuthenticated.value = data.authenticated
    piholeUrl.value = data.pihole_url ?? null
    piholeUrlFromEnv.value = data.pihole_url_from_env ?? false
    return data.authenticated
  } catch {
    isAuthenticated.value = false
    return false
  } finally {
    checking.value = false
  }
}

async function login(password: string, url?: string): Promise<{ ok: boolean; error?: string }> {
  try {
    const body: Record<string, string> = { password }
    if (url) body.pihole_url = url
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json()
    if (res.ok && data.status === 'ok') {
      isAuthenticated.value = true
      piholeUrl.value = data.pihole_url
      resetRedirectFlag()
      return { ok: true }
    }
    return { ok: false, error: data.status || 'Login failed' }
  } catch {
    return { ok: false, error: 'Could not reach server' }
  }
}

async function logout(): Promise<void> {
  try {
    await fetch('/api/auth/logout', { method: 'POST' })
  } catch {
    // Best-effort
  }
  isAuthenticated.value = false
  if (!piholeUrlFromEnv.value) {
    piholeUrl.value = null
  }
}

export function useAuth() {
  return {
    isAuthenticated,
    piholeUrl,
    checking,
    checkSession,
    login,
    logout,
  }
}

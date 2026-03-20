/**
 * Thin wrapper around fetch that redirects to login on 401 responses.
 *
 * Use this for all authenticated API calls instead of bare `fetch()`.
 * When a 401 is received (session expired), it clears the auth state
 * and uses the Vue router to navigate to the login page.
 */
import { useAuth } from '@/composables/useAuth'
import { getRouter } from '@/router'

let redirecting = false

export function resetRedirectFlag() {
  redirecting = false
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, init)
  if (res.status === 401 && !redirecting) {
    const { isAuthenticated } = useAuth()
    if (isAuthenticated.value) {
      redirecting = true
      isAuthenticated.value = false
      getRouter().push('/login')
    }
  }
  return res
}

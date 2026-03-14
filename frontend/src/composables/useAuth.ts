import { ref } from 'vue'

// Placeholder until authentication is implemented (see docs/authentication.md).
// When auth is built out, this composable will manage session state.
const isAuthenticated = ref(false)

export function useAuth() {
  return { isAuthenticated }
}

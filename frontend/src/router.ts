import { createRouter, createWebHistory, type Router } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', name: 'dashboard', component: () => import('./views/DashboardView.vue') },
    { path: '/timeline', name: 'timeline', component: () => import('./views/TimelineView.vue') },
    { path: '/detailed-report', name: 'detailed-report', component: () => import('./views/DetailedReportView.vue') },
  ],
})

// Navigation guard — redirects unauthenticated users to login
let sessionChecked = false
router.beforeEach(async (to) => {
  const { useAuth } = await import('./composables/useAuth')
  const { isAuthenticated, checkSession } = useAuth()

  // Check session once on first navigation (retry on failure)
  if (!sessionChecked) {
    const ok = await checkSession()
    if (ok || !to.meta.public) sessionChecked = true
  }

  // If going to a public route while authenticated, redirect to dashboard
  if (to.meta.public && isAuthenticated.value) {
    return { name: 'dashboard' }
  }

  // If going to a protected route while not authenticated, redirect to login
  if (!to.meta.public && !isAuthenticated.value) {
    return { name: 'login' }
  }
})

export default router

export function getRouter(): Router {
  return router
}

<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useDark, useToggle } from '@vueuse/core'
import { useAuth } from './composables/useAuth'
import SettingsSidebar from './components/layout/SettingsSidebar.vue'
import AppFooter from './components/layout/AppFooter.vue'

const isDark = useDark()
const toggleDark = useToggle(isDark)
const { isAuthenticated, checking, logout } = useAuth()
const router = useRouter()
const route = useRoute()
const settingsOpen = ref(false)

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <div class="h-screen flex flex-col text-gray-900 dark:text-gray-100">
    <!-- Show header only when authenticated (and session check is done) -->
    <header
      v-if="isAuthenticated && !checking"
      class="shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-3 flex items-center justify-between"
    >
      <div class="flex items-center gap-6">
        <RouterLink
          to="/dashboard"
          class="font-semibold tracking-tight text-gray-900 dark:text-gray-100 no-underline hover:opacity-75 transition-opacity"
        >pihole-wtm</RouterLink>
        <nav class="flex items-center gap-1">
          <RouterLink
            to="/dashboard"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm no-underline transition-colors"
            :class="route.path === '/dashboard'
              ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 font-medium'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800'"
          ><i class="pi pi-objects-column text-xs" />Dashboard</RouterLink>
          <RouterLink
            to="/timeline"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm no-underline transition-colors"
            :class="route.path === '/timeline'
              ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 font-medium'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800'"
          ><i class="pi pi-chart-line text-xs" />Timeline</RouterLink>
          <RouterLink
            to="/detailed-report"
            class="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm no-underline transition-colors"
            :class="route.path === '/detailed-report'
              ? 'bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 font-medium'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-gray-100 dark:hover:bg-gray-800'"
          ><i class="pi pi-list text-xs" />Detailed Report</RouterLink>
        </nav>
      </div>
      <div class="flex items-center gap-1">
        <Button
          :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
          severity="secondary"
          text
          rounded
          @click="toggleDark()"
          aria-label="Toggle dark mode"
        />
        <Button
          icon="pi pi-cog"
          severity="secondary"
          text
          rounded
          aria-label="Settings"
          @click="settingsOpen = true"
        />
        <Button
          icon="pi pi-sign-out"
          severity="secondary"
          text
          rounded
          aria-label="Sign out"
          @click="handleLogout()"
        />
      </div>
    </header>
    <main class="flex-1 overflow-auto">
      <RouterView />
    </main>
    <AppFooter v-if="isAuthenticated && !checking" />
    <SettingsSidebar v-if="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>

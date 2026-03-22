<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useDark, useToggle } from '@vueuse/core'
import { useAuth } from './composables/useAuth'
import SettingsSidebar from './components/layout/SettingsSidebar.vue'
import AppFooter from './components/layout/AppFooter.vue'

const isDark = useDark()
const toggleDark = useToggle(isDark)
const { isAuthenticated, checking, logout } = useAuth()
const route = useRoute()
const router = useRouter()
const settingsOpen = ref(false)
const mobileNavOpen = ref(false)

// Close mobile nav when route changes
watch(() => route.path, () => { mobileNavOpen.value = false })

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
        <!-- Desktop nav -->
        <nav class="hidden md:flex items-center gap-1">
          <RouterLink to="/dashboard" class="nav-link"><i class="pi pi-gauge text-xs" />Dashboard</RouterLink>
          <RouterLink to="/timeline" class="nav-link"><i class="pi pi-chart-line text-xs" />Timeline</RouterLink>
          <RouterLink to="/domains-report" class="nav-link"><i class="pi pi-globe text-xs" />Domains</RouterLink>
          <RouterLink to="/devices-report" class="nav-link"><i class="pi pi-mobile text-xs" />Devices</RouterLink>
        </nav>
      </div>
      <div class="flex items-center gap-1">
        <!-- Hamburger (mobile only) -->
        <Button
          :icon="mobileNavOpen ? 'pi pi-times' : 'pi pi-bars'"
          severity="secondary"
          text
          rounded
          class="md:!hidden"
          aria-label="Toggle navigation"
          @click="mobileNavOpen = !mobileNavOpen"
        />
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
    <!-- Mobile nav dropdown -->
    <div
      v-if="isAuthenticated && !checking"
      class="md:hidden grid transition-[grid-template-rows] duration-200 ease-in-out"
      :class="mobileNavOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'"
    >
      <nav class="overflow-hidden px-6 flex flex-col gap-1"
        :class="mobileNavOpen ? 'border-b border-gray-200 dark:border-gray-800' : ''"
      >
        <div class="py-2">
          <RouterLink to="/dashboard" class="nav-link"><i class="pi pi-gauge text-xs" />Dashboard</RouterLink>
          <RouterLink to="/timeline" class="nav-link"><i class="pi pi-chart-line text-xs" />Timeline</RouterLink>
          <RouterLink to="/domains-report" class="nav-link"><i class="pi pi-globe text-xs" />Domains</RouterLink>
          <RouterLink to="/devices-report" class="nav-link"><i class="pi pi-mobile text-xs" />Devices</RouterLink>
        </div>
      </nav>
    </div>
    <main class="flex-1 overflow-auto">
      <RouterView />
    </main>
    <AppFooter v-if="isAuthenticated && !checking" />
    <SettingsSidebar v-if="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import { RouterLink, useRoute } from 'vue-router'
import { useColorMode } from '@vueuse/core'
import { useAuth } from './composables/useAuth'
import NavLinks from './components/layout/NavLinks.vue'
import UtilityButtons from './components/layout/UtilityButtons.vue'
import SettingsSidebar from './components/layout/SettingsSidebar.vue'
import AppFooter from './components/layout/AppFooter.vue'

// Initialise colour mode at the app root so the .dark class is applied on every
// page load — including the login page, before UtilityButtons is mounted.
useColorMode()

const { isAuthenticated, checking } = useAuth()
const route = useRoute()
const settingsOpen = ref(false)
const mobileNavOpen = ref(false)

// Close mobile nav when route changes
watch(() => route.path, () => { mobileNavOpen.value = false })
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
          <NavLinks />
        </nav>
      </div>
      <div class="flex items-center gap-1">
        <!-- Hamburger (mobile only) -->
        <Button
          :icon="mobileNavOpen ? 'pi pi-times' : 'pi pi-bars'"
          severity="secondary"
          variant="outlined"
          rounded
          class="md:!hidden"
          aria-label="Toggle navigation"
          @click="mobileNavOpen = !mobileNavOpen"
        />
        <!-- Desktop utility buttons -->
        <div class="hidden md:flex items-center gap-2">
          <UtilityButtons @open-settings="settingsOpen = true" />
        </div>
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
        <div class="py-2 flex flex-col gap-1">
          <div class="flex items-center justify-center gap-2 mb-1">
            <UtilityButtons @open-settings="settingsOpen = true" />
          </div>
          <NavLinks />
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

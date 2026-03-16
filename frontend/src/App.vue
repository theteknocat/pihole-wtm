<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import { RouterLink } from 'vue-router'
import { useDark, useToggle } from '@vueuse/core'
import { useAuth } from './composables/useAuth'
import SettingsSidebar from './components/layout/SettingsSidebar.vue'

const isDark = useDark()
const toggleDark = useToggle(isDark)
const { isAuthenticated } = useAuth()
const settingsOpen = ref(false)
</script>

<template>
  <div class="h-screen flex flex-col text-gray-900 dark:text-gray-100">
    <header class="shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-3 flex items-center justify-between">
      <RouterLink
        :to="isAuthenticated ? '/dashboard' : '/'"
        class="font-semibold tracking-tight text-gray-900 dark:text-gray-100 no-underline hover:opacity-75 transition-opacity"
      >pihole-wtm</RouterLink>
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
      </div>
    </header>
    <main class="flex-1 overflow-auto">
      <RouterView />
    </main>
    <SettingsSidebar v-if="settingsOpen" @close="settingsOpen = false" />
  </div>
</template>

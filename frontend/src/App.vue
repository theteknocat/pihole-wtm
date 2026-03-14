<script setup lang="ts">
import Button from 'primevue/button'
import { RouterLink } from 'vue-router'
import { useDark, useToggle } from '@vueuse/core'
import { useAuth } from './composables/useAuth'

const isDark = useDark()
const toggleDark = useToggle(isDark)
const { isAuthenticated } = useAuth()
</script>

<template>
  <div class="h-screen flex flex-col text-gray-900 dark:text-gray-100">
    <header class="shrink-0 border-b border-gray-200 dark:border-gray-800 px-6 py-3 flex items-center justify-between">
      <RouterLink
        :to="isAuthenticated ? '/dashboard' : '/'"
        class="font-semibold tracking-tight text-gray-900 dark:text-gray-100 no-underline hover:opacity-75 transition-opacity"
      >pihole-wtm</RouterLink>
      <Button
        :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'"
        severity="secondary"
        text
        rounded
        @click="toggleDark()"
        aria-label="Toggle dark mode"
      />
    </header>
    <main class="flex-1 overflow-auto">
      <RouterView />
    </main>
  </div>
</template>

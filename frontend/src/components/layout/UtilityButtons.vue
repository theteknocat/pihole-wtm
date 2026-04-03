<script setup lang="ts">
import Button from 'primevue/button'
import { useColorMode } from '@vueuse/core'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

const mode = useColorMode()
// Separate visual state from the actual mode so we can animate the knob
// before the dark class change triggers a full-page repaint.
const visualDark = ref(mode.value === 'dark')

function toggleDark() {
  const next = !visualDark.value
  visualDark.value = next
  setTimeout(() => {
    mode.store.value = next ? 'dark' : 'light'
  }, 50)
}

const { logout } = useAuth()
const router = useRouter()

const emit = defineEmits<{ (e: 'open-settings'): void }>()

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="visualDark"
    :aria-label="visualDark ? 'Switch to light mode' : 'Switch to dark mode'"
    v-tooltip.bottom="visualDark ? 'Switch to light mode' : 'Switch to dark mode'"
    class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full bg-gray-300 transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500 dark:bg-gray-600"
    :class="visualDark ? '!bg-gray-500' : ''"
    @click="toggleDark"
  >
    <span
      class="inline-flex h-4 w-4 items-center justify-center rounded-full bg-white shadow transition-transform duration-200"
      :class="visualDark ? 'translate-x-[1.125rem]' : 'translate-x-0.5'"
    >
      <i :class="['pi text-[9px] text-gray-500', visualDark ? 'pi-moon' : 'pi-sun']" />
    </span>
  </button>
  <Button icon="pi pi-cog" severity="secondary" text rounded aria-label="Settings" @click="emit('open-settings')" />
  <Button icon="pi pi-sign-out" severity="secondary" text rounded aria-label="Sign out" @click="handleLogout()" />
</template>

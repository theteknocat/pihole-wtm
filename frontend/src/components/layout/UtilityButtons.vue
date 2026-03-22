<script setup lang="ts">
import Button from 'primevue/button'
import { useDark, useToggle } from '@vueuse/core'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'

const isDark = useDark()
const toggleDark = useToggle(isDark)
const { logout } = useAuth()
const router = useRouter()

const emit = defineEmits<{ (e: 'open-settings'): void }>()

async function handleLogout() {
  await logout()
  router.push('/login')
}
</script>

<template>
  <Button :icon="isDark ? 'pi pi-sun' : 'pi pi-moon'" severity="secondary" text rounded @click="toggleDark()" aria-label="Toggle dark mode" />
  <Button icon="pi pi-cog" severity="secondary" text rounded aria-label="Settings" @click="emit('open-settings')" />
  <Button icon="pi pi-sign-out" severity="secondary" text rounded aria-label="Sign out" @click="handleLogout()" />
</template>

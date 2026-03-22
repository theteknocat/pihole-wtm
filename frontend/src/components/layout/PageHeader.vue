<script setup lang="ts">
/**
 * PageHeader — sticky header with title, subtitle, time window nav,
 * and an optional slot for extra controls (e.g. group-by toggle).
 *
 * Handles scroll-aware compact mode internally via useScrolled.
 */
import { useScrolled } from '@/composables/useScrolled'
import TimeWindowNav from '@/components/layout/TimeWindowNav.vue'

defineProps<{
  title: string
  icon?: string
  subtitle?: string
}>()

const scrolled = useScrolled()
</script>

<template>
  <div class="flex items-center justify-between sticky-header" :class="{ scrolled }">
    <div>
      <h1 class="text-xl font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
        <i v-if="icon" :class="[icon, scrolled ? 'text-sm' : '']" />
        {{ title }}
      </h1>
      <p v-if="subtitle" class="text-sm text-gray-500 dark:text-gray-400 mt-0.5">{{ subtitle }}</p>
    </div>
    <div class="flex items-center gap-2">
      <TimeWindowNav :compact="scrolled" />
    </div>
  </div>
</template>

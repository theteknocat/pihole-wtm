<script setup lang="ts">
import { RouterLink } from 'vue-router'

const props = withDefaults(defineProps<{ size?: 'small' | 'large' }>(), { size: 'small' })
</script>

<template>
  <RouterLink to="/dashboard" :class="['nav-link', props.size === 'large' && 'nav-link-large']"><i :class="['pi pi-gauge', props.size === 'large' ? 'text-sm' : 'text-xs']" />Dashboard</RouterLink>
  <RouterLink to="/timeline" :class="['nav-link', props.size === 'large' && 'nav-link-large']"><i :class="['pi pi-chart-line', props.size === 'large' ? 'text-sm' : 'text-xs']" />Timeline</RouterLink>
  <RouterLink to="/domains-report" :class="['nav-link', props.size === 'large' && 'nav-link-large']"><i :class="['pi pi-globe', props.size === 'large' ? 'text-sm' : 'text-xs']" />Domains</RouterLink>
  <RouterLink to="/devices-report" :class="['nav-link', props.size === 'large' && 'nav-link-large']"><i :class="['pi pi-mobile', props.size === 'large' ? 'text-sm' : 'text-xs']" />Devices</RouterLink>
</template>

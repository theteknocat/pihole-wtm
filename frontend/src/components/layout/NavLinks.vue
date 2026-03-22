<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <RouterLink to="/dashboard" class="nav-link"><i class="pi pi-gauge text-xs" />Dashboard</RouterLink>
  <RouterLink to="/timeline" class="nav-link"><i class="pi pi-chart-line text-xs" />Timeline</RouterLink>
  <RouterLink to="/domains-report" class="nav-link"><i class="pi pi-globe text-xs" />Domains</RouterLink>
  <RouterLink to="/devices-report" class="nav-link"><i class="pi pi-mobile text-xs" />Devices</RouterLink>
</template>

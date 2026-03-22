<script setup lang="ts">
import { useHealth } from '@/composables/useHealth'

const { health, error, syncAgo } = useHealth()
</script>

<template>
  <footer
    class="shrink-0 border-t border-gray-200 dark:border-gray-800 px-4 py-1.5 flex items-center gap-4 text-xs text-muted font-mono"
  >
    <template v-if="error">
      <span class="text-red-400 flex items-center gap-1">
        <i class="pi pi-times-circle" />Backend unreachable
      </span>
    </template>
    <template v-else-if="health">
      <!-- Version -->
      <span>v{{ health.version }}</span>

      <span class="text-divider">|</span>

      <!-- Pi-hole status -->
      <span class="flex items-center gap-2">
        <i
          :class="health.pihole_api_url
            ? 'pi pi-check-circle text-green-500 dark:text-green-400'
            : 'pi pi-times-circle text-red-400'"
        />
        Pi-hole
      </span>

      <span class="text-divider">|</span>

      <!-- Sources -->
      <template v-for="(source, i) in health.sources" :key="source.name">
        <span v-if="i > 0" class="text-divider">|</span>
        <span
          class="flex items-center gap-2"
          :title="source.loaded ? `${source.domain_count.toLocaleString()} domains` : 'Not loaded'"
        >
        <i
          :class="source.loaded
            ? 'pi pi-check-circle text-green-500 dark:text-green-400'
            : 'pi pi-times-circle text-red-400'"
        />
        {{ source.label }}
      </span>
      </template>

      <span class="text-divider">|</span>

      <!-- Sync status -->
      <span class="flex items-center gap-2">
        <i class="pi pi-sync" />
        <span>Last sync {{ syncAgo }}</span>
        <span v-if="health.sync_source === 'session'"
          v-tooltip.top="'Sync runs only while logged in — set PIHOLE_API_PASSWORD for always-on sync'"
        >
          <i
            class="pi pi-info-circle text-amber-500 dark:text-amber-400"
          />
        </span>
      </span>

      <span class="text-divider">|</span>

      <!-- Stored queries -->
      <span class="flex items-center gap-2">
        <i class="pi pi-globe" />
        {{ health.stored_queries.toLocaleString() }} queries
      </span>

    </template>
    <template v-else>
      <span class="text-gray-400">Loading...</span>
    </template>
  </footer>
</template>

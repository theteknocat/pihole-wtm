<script setup lang="ts">
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import { useHealth } from '@/composables/useHealth'

const { health, error, syncAgo } = useHealth()
const statusPopover = ref<InstanceType<typeof Popover>>()

/**
 * Overall health status: 'red' if backend unreachable or pihole disconnected,
 * 'amber' if any tracker source isn't loaded, 'green' if all systems go.
 */
const statusLevel = computed(() => {
  if (error.value || !health.value) return 'red'
  if (!health.value.pihole_api_url) return 'red'
  if (health.value.sources.some(s => !s.loaded)) return 'amber'
  return 'green'
})

const statusColor = computed(() => ({
  red: 'text-red-500 dark:text-red-400',
  amber: 'text-amber-500 dark:text-amber-400',
  green: 'text-green-500 dark:text-green-400',
}[statusLevel.value]))
</script>

<template>
  <footer
    class="shrink-0 border-t border-gray-200 dark:border-gray-800 px-4 py-1.5 flex items-center text-xs text-muted font-mono"
  >
    <!-- Health status button (left) -->
    <div class="flex-1 flex items-center">
      <Button
        severity="secondary"
        text
        rounded
        size="small"
        class="!px-2 md:!px-2"
        @click="statusPopover?.toggle($event)"
      >
        <i class="pi pi-heart-fill text-sm md:text-xs" :class="statusColor" />
        <span class="ml-1.5 hidden md:inline text-xs">Status</span>
      </Button>

      <Popover ref="statusPopover">
        <div class="text-xs font-mono space-y-2 min-w-[14rem]">
          <template v-if="error">
            <div class="flex items-center gap-2 text-red-500">
              <i class="pi pi-times-circle" />
              Backend unreachable
            </div>
          </template>
          <template v-else-if="health">
            <!-- Pi-hole -->
            <div class="flex items-center gap-2">
              <i
                :class="health.pihole_api_url
                  ? 'pi pi-check-circle text-green-500 dark:text-green-400'
                  : 'pi pi-times-circle text-red-400'"
              />
              Pi-hole
            </div>

            <!-- Tracker sources -->
            <div
              v-for="source in health.sources"
              :key="source.name"
              class="flex items-center gap-2"
            >
              <i
                :class="source.loaded
                  ? 'pi pi-check-circle text-green-500 dark:text-green-400'
                  : 'pi pi-times-circle text-red-400'"
              />
              <span>{{ source.label }}</span>
            </div>

            <!-- Sync source warning -->
            <div
              v-if="health.sync_source === 'session'"
              class="flex items-center gap-2 text-amber-500 dark:text-amber-400"
            >
              <i class="pi pi-info-circle" />
              <span>Session-only sync</span>
            </div>
          </template>
        </div>
      </Popover>
    </div>

    <!-- Sync + queries (centre) -->
    <div class="flex items-center gap-3 justify-center">
      <template v-if="error">
        <span class="text-red-400">Backend unreachable</span>
      </template>
      <template v-else-if="health">
        <span class="flex items-center gap-1.5" v-tooltip.top="'Last Pi-hole sync'">
          <i class="pi pi-sync" />
          {{ syncAgo }}
        </span>
        <span class="text-divider">|</span>
        <span class="flex items-center gap-1.5" v-tooltip.top="'Stored queries'">
          <i class="pi pi-globe" />
          {{ health.stored_queries.toLocaleString() }}
        </span>
      </template>
      <template v-else>
        <span class="text-muted-inverse">Loading...</span>
      </template>
    </div>

    <!-- Version (right) -->
    <div class="flex-1 text-right">
      <span v-if="health">v{{ health.version }}</span>
    </div>
  </footer>
</template>

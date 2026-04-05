<script setup lang="ts">
/**
 * TimeWindowNav — period selector with prev/next time navigation.
 *
 * Renders a period dropdown (24h, 7d, 30d, 90d — filtered by available data),
 * prev/next buttons to slide the window through time, and a date range label
 * showing the current window boundaries. A "Latest" button appears when
 * viewing a historical window to jump back to live.
 *
 * All state lives in the window store — this component is purely a control.
 */
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import Menu from 'primevue/menu';
import { useWindowStore } from '@/stores/window'

const props = defineProps<{
  compact?: boolean
}>()

const windowStore = useWindowStore()
const periodMenu = ref<InstanceType<typeof Menu>>()

const selectedPeriod = computed({
  get: () => windowStore.availablePeriods.find(o => o.value === windowStore.hours)
    ?? windowStore.availablePeriods[0],
  set: (v) => { windowStore.hours = v.value },
})

const periodItems = computed(() => {
  let items = windowStore.availablePeriods
  .map(p => ({
    label: p.label,
    icon: p.icon || '',
    is_active: p.value == selectedPeriod.value.value,
    command: () => { selectedPeriod.value = p },
  }))
  return [
    {
      label: 'Display Period',
      items: items
    }
  ]
})

/** Format a unix timestamp as a short readable date/time */
function formatTs(ts: number): string {
  const d = new Date(ts * 1000)
  const now = new Date()

  // If same year, omit year
  const sameYear = d.getFullYear() === now.getFullYear()
  const opts: Intl.DateTimeFormatOptions = {
    month: windowStore.hours <= 24 ? 'short' : 'long',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  }

  // For windows ≤ 24h show time too
  if (windowStore.hours <= 24) {
    opts.hour = '2-digit'
    opts.minute = '2-digit'
  }

  return d.toLocaleDateString(undefined, opts)
}

const rangeLabel = computed(() => {
  const from = formatTs(windowStore.fromTs)
  const to = formatTs(windowStore.effectiveEndTs)
  return `${from} – ${to}`
})
</script>

<template>
  <div class="flex items-center gap-2">
    <!-- Time navigation -->
    <div class="flex items-center gap-1">
      <Button
        icon="pi pi-angle-double-left"
        severity="contrast"
        variant="outlined"
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoPrev"
        @click="windowStore.goOldest()"
        v-tooltip.top="windowStore.canGoPrev ? 'Oldest data' : null"
      />
      <Button
        icon="pi pi-angle-left"
        severity="contrast"
        variant="outlined"
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoPrev"
        @click="windowStore.goPrev()"
        v-tooltip.top="windowStore.canGoPrev ? 'Previous period' : null"
      />
      <div class="dropnav-container">
        <Button
          severity="contrast"
          variant="outlined"
          rounded
          @click="periodMenu?.toggle($event)"
          :size="props.compact ? 'small' : undefined"
          :class="{ 'pointer-events-none': windowStore.availablePeriods.length <= 1 }"
          :tabindex="windowStore.availablePeriods.length <= 1 ? -1 : 0"
        >
          <span>{{ rangeLabel }}</span>
          <i v-if="windowStore.availablePeriods.length > 1" class="pi pi-chevron-down text-xs" />
        </Button>
        <Menu v-if="windowStore.availablePeriods.length > 1" ref="periodMenu" :model="periodItems" :popup="true">
          <template #item="{ item, props }">
              <a v-ripple class="flex items-center" :class="{'pointer-events-none italic': item.is_active}" v-bind="props.action">
                  <span class="flex items-center gap-1" :class="{'text-muted': item.is_active}">
                    <i :class="item.icon" />
                    <span>{{ item.label }}</span>
                  </span>
                  <span v-if="item.is_active" class="ml-auto pi pi-check text-xs" />
              </a>
          </template>
        </Menu>
      </div>
      <Button
        icon="pi pi-angle-right"
        severity="contrast"
        variant="outlined"
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoNext"
        @click="windowStore.goNext()"
        v-tooltip.top="windowStore.canGoNext ? 'Next period' : null"
      />
      <Button
        icon="pi pi-angle-double-right"
        severity="contrast"
        variant="outlined"
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoNext"
        @click="windowStore.goLatest()"
        v-tooltip.top="windowStore.canGoNext ? 'Latest data' : null"
      />
    </div>
  </div>
</template>

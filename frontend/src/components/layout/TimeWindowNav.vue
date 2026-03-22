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

const periodItems = computed(() =>
  windowStore.availablePeriods
  .filter(p => p.value != selectedPeriod.value.value)
  .map(p => ({
    label: p.label,
    command: () => { selectedPeriod.value = p },
  }))
)

/** Format a unix timestamp as a short readable date/time */
function formatTs(ts: number): string {
  const d = new Date(ts * 1000)
  const now = new Date()

  // If same year, omit year
  const sameYear = d.getFullYear() === now.getFullYear()
  const opts: Intl.DateTimeFormatOptions = {
    month: 'short',
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
        severity="secondary"
        text
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoPrev"
        @click="windowStore.goOldest()"
        v-tooltip.top="'Oldest data'"
      />
      <Button
        icon="pi pi-angle-left"
        severity="secondary"
        text
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoPrev"
        @click="windowStore.goPrev()"
        v-tooltip.top="'Previous period'"
      />
      <div class="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap min-w-[10rem] text-center">
        <Button
          severity="secondary"
          text
          @click="periodMenu?.toggle($event)"
          size="small"
          :class="{ 'pointer-events-none': windowStore.availablePeriods.length <= 1 }"
          :tabindex="windowStore.availablePeriods.length <= 1 ? -1 : 0"
        >
          <i class="pi pi-history" />
          <span class="whitespace-nowrap"><strong>{{ selectedPeriod.label }}</strong>: {{ rangeLabel }}</span>
          <i v-if="windowStore.availablePeriods.length > 1" class="pi pi-chevron-down text-xs" />
        </Button>
        <Menu v-if="windowStore.availablePeriods.length > 1" ref="periodMenu" :model="periodItems" :popup="true" />
      </div>
      <Button
        icon="pi pi-angle-right"
        severity="secondary"
        text
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoNext"
        @click="windowStore.goNext()"
        v-tooltip.top="'Next period'"
      />
      <Button
        icon="pi pi-angle-double-right"
        severity="secondary"
        text
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoNext"
        @click="windowStore.goLatest()"
        v-tooltip.top="'Latest data'"
      />
    </div>
  </div>
</template>

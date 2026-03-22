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
import { computed } from 'vue'
import Select from 'primevue/select'
import Button from 'primevue/button'
import { useWindowStore } from '@/stores/window'

const props = defineProps<{
  compact?: boolean
}>()

const windowStore = useWindowStore()

const selectedPeriod = computed({
  get: () => windowStore.availablePeriods.find(o => o.value === windowStore.hours)
    ?? windowStore.availablePeriods[0],
  set: (v) => { windowStore.hours = v.value },
})

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
  const to = windowStore.isHistorical
    ? formatTs(windowStore.effectiveEndTs)
    : 'Now'
  return `${from} – ${to}`
})
</script>

<template>
  <div class="flex items-center gap-2">
    <!-- Period dropdown -->
    <Select
      v-model="selectedPeriod"
      :options="windowStore.availablePeriods"
      option-label="label"
      :class="props.compact ? 'w-20' : 'w-24'"
    />

    <!-- Prev / Next navigation -->
    <div class="flex items-center gap-1">
      <Button
        icon="pi pi-chevron-left"
        severity="secondary"
        text
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoPrev"
        @click="windowStore.goPrev()"
        v-tooltip.top="'Previous period'"
      />
      <span class="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap min-w-[10rem] text-center">
        {{ rangeLabel }}
      </span>
      <Button
        icon="pi pi-chevron-right"
        severity="secondary"
        text
        rounded
        :size="props.compact ? 'small' : undefined"
        :disabled="!windowStore.canGoNext"
        @click="windowStore.goNext()"
        v-tooltip.top="'Next period'"
      />
    </div>

    <!-- Latest button — only when viewing historical data -->
    <Button
      v-if="windowStore.isHistorical"
      label="Latest"
      icon="pi pi-forward"
      severity="secondary"
      text
      :size="props.compact ? 'small' : undefined"
      @click="windowStore.goLatest()"
    />
  </div>
</template>

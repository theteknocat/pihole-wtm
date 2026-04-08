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

const fromLabel = computed(() => formatTs(windowStore.fromTs))
const toLabel = computed(() => formatTs(windowStore.effectiveEndTs))
</script>

<template>
  <div class="flex items-center gap-2">
    <!-- Time navigation -->
    <div class="flex flex-wrap items-center gap-1">
      <!-- Prev buttons: row 2 on mobile (order-2), row 1 on sm+ (order-1) -->
      <div class="flex flex-1 sm:flex-none items-center gap-1 order-2 sm:order-1">
        <Button
          class="flex-1 sm:flex-none !rounded-full"
          icon="pi pi-angle-double-left"
          severity="contrast"
          variant="outlined"
          :size="props.compact ? 'small' : undefined"
          :disabled="!windowStore.canGoPrev"
          @click="windowStore.goOldest()"
          v-tooltip.top="windowStore.canGoPrev ? 'Oldest data' : null"
        />
        <Button
          class="flex-1 sm:flex-none !rounded-full"
          icon="pi pi-angle-left"
          severity="contrast"
          variant="outlined"
          :size="props.compact ? 'small' : undefined"
          :disabled="!windowStore.canGoPrev"
          @click="windowStore.goPrev()"
          v-tooltip.top="windowStore.canGoPrev ? 'Previous period' : null"
        />
      </div>
      <!-- Dropdown: row 1 on mobile (order-1, full width), inline on sm+ (order-2, auto width) -->
      <div class="dropnav-container w-full sm:w-auto order-1 sm:order-2">
        <Button
          class="w-full sm:w-auto"
          severity="contrast"
          variant="outlined"
          rounded
          @click="periodMenu?.toggle($event)"
          :size="props.compact ? 'small' : undefined"
          :class="{ 'pointer-events-none': windowStore.availablePeriods.length <= 1 }"
          :tabindex="windowStore.availablePeriods.length <= 1 ? -1 : 0"
        >
          <span class="flex w-full items-center gap-2 sm:gap-4">
            <span class="flex-1 text-left whitespace-normal leading-snug">
              <span class="whitespace-nowrap">{{ fromLabel }}</span>
              &ndash;
              <span class="whitespace-nowrap"> {{ toLabel }}</span>
            </span>
            <i v-if="windowStore.availablePeriods.length > 1" class="pi pi-chevron-down text-xs shrink-0" />
          </span>
        </Button>
        <Menu v-if="windowStore.availablePeriods.length > 1" ref="periodMenu" :model="periodItems" :popup="true">
          <template #item="{ item, props }">
              <a class="flex items-center" :class="{'pointer-events-none italic': item.is_active}" v-bind="props.action">
                  <span class="flex items-center gap-1" :class="{'text-muted': item.is_active}">
                    <i :class="item.icon" />
                    <span>{{ item.label }}</span>
                  </span>
                  <span v-if="item.is_active" class="ml-auto pi pi-check text-xs" />
              </a>
          </template>
        </Menu>
      </div>
      <!-- Next buttons: row 2 on mobile (order-3), row 1 on sm+ (order-3) -->
      <div class="flex flex-1 sm:flex-none items-center gap-1 order-3">
        <Button
          class="flex-1 sm:flex-none !rounded-full"
          icon="pi pi-angle-right"
          severity="contrast"
          variant="outlined"
          :size="props.compact ? 'small' : undefined"
          :disabled="!windowStore.canGoNext"
          @click="windowStore.goNext()"
          v-tooltip.top="windowStore.canGoNext ? 'Next period' : null"
        />
        <Button
          class="flex-1 sm:flex-none !rounded-full"
          icon="pi pi-angle-double-right"
          severity="contrast"
          variant="outlined"
          :size="props.compact ? 'small' : undefined"
          :disabled="!windowStore.canGoNext"
          @click="windowStore.goLatest()"
          v-tooltip.top="windowStore.canGoNext ? 'Latest data' : null"
        />
      </div>
    </div>
  </div>
</template>

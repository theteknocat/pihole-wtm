<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import Button from 'primevue/button'
import SelectButton from 'primevue/selectbutton'
import { useColorMode } from '@vueuse/core'

import DisplaySection from './settings/DisplaySection.vue'
import SyncSection from './settings/SyncSection.vue'
import DataSourcesSection from './settings/DataSourcesSection.vue'
import DataManagementSection from './settings/DataManagementSection.vue'

const emit = defineEmits<{ (e: 'close'): void }>()

// Colour mode — mode.store is the raw stored preference ('light' | 'dark' | 'auto')
const mode = useColorMode()
const colorModeStore = mode.store
const appearanceOptions = [
  { label: 'Light', value: 'light', icon: 'pi pi-sun' },
  { label: 'Dark', value: 'dark', icon: 'pi pi-moon' },
  { label: 'System', value: 'auto', icon: 'pi pi-desktop' },
]

// Slide-in animation
const visible = ref(false)
onMounted(() => requestAnimationFrame(() => { visible.value = true }))

async function close() {
  await flushIfNeeded()
  visible.value = false
  setTimeout(() => emit('close'), 200)
}

// Active section — null means showing the menu, string means a section is expanded
const activeSection = ref<string | null>(null)

const sections = [
  { id: 'display', label: 'Global Filters', icon: 'pi-filter', component: DisplaySection },
  { id: 'sync', label: 'Sync Settings', icon: 'pi-sync', component: SyncSection },
  { id: 'data-sources', label: 'Data Sources', icon: 'pi-database', component: DataSourcesSection },
  { id: 'data-management', label: 'Data Management', icon: 'pi-server', component: DataManagementSection },
]

const contentVisible = ref(false)
const expanded = ref(false)

function openSection(id: string) {
  contentVisible.value = false
  activeSection.value = id
  nextTick(() => requestAnimationFrame(() => { contentVisible.value = true }))
  // Use the same timeout value here as the delay class on the section content.
  setTimeout(() => { expanded.value = true }, 200)
}

async function closeSection() {
  await flushIfNeeded()
  activeSection.value = null
  expanded.value = false
}

// Save indicator in section header
const showSaved = ref(false)
let savedTimer: ReturnType<typeof setTimeout> | null = null

function onSaved() {
  showSaved.value = true
  if (savedTimer) clearTimeout(savedTimer)
  savedTimer = setTimeout(() => { showSaved.value = false }, 2000)
}

// Flush pending saves before navigating away
const sectionRef = ref<{ flush?: () => Promise<void> }>()
const flushing = ref(false)

async function flushIfNeeded() {
  if (sectionRef.value?.flush) {
    flushing.value = true
    await sectionRef.value.flush()
    flushing.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-40">

    <!-- Backdrop -->
    <div
      class="absolute inset-0 bg-black/20 dark:bg-black/40 transition-opacity duration-200"
      :class="visible ? 'opacity-100' : 'opacity-0'"
      @click="close"
    />

    <!-- Panel -->
    <aside
      class="absolute top-0 right-0 h-full bg-white dark:bg-stone-900 border-l border-gray-200 dark:border-gray-800 shadow-xl flex flex-col transition-all duration-200 ease-out"
      :class="[
        visible ? 'translate-x-0' : 'translate-x-full',
        activeSection ? 'w-[28rem] sm:w-[32rem] max-w-full' : 'w-72 max-w-full',
      ]"
    >
      <!-- Header -->
      <div class="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800 shrink-0">
        <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">Settings</span>
        <Button icon="pi pi-times" severity="secondary" text rounded size="small" @click="close" />
      </div>

      <!-- Content -->
      <div class="flex-1 min-h-0 flex flex-col overflow-hidden">

        <!-- Menu mode: show all sections -->
        <div v-if="!activeSection" class="flex-1 min-h-0 flex flex-col overflow-auto p-2 gap-1">
          <button
            v-for="section in sections"
            :key="section.id"
            class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            @click="openSection(section.id)"
          >
            <i :class="['pi', section.icon, 'text-gray-400 dark:text-gray-500']" />
            <span class="flex-1">{{ section.label }}</span>
            <i class="pi pi-chevron-right text-xs text-gray-400 dark:text-gray-500" />
          </button>

          <!-- Appearance — pinned to bottom -->
          <div class="mt-auto pt-2 border-t border-gray-200 dark:border-gray-800">
            <SelectButton
              size="small"
              v-model="colorModeStore"
              :options="appearanceOptions"
              option-label="label"
              option-value="value"
              :pt="{
                root: { class: 'flex w-full' },
                pcToggleButton: {
                  root: { class: 'flex-1' },
                  content: { class: 'w-full justify-center' },
                },
              }"
            >
              <template #option="{ option }">
                <i :class="['pi text-xs', option.icon]" />
                <span class="hidden sm:inline">{{ option.label }}</span>
              </template>
            </SelectButton>
          </div>
        </div>

        <!-- Expanded mode: show active section -->
        <template v-else>
          <!-- Section title (click to go back) — stays pinned -->
          <button
            class="w-full flex items-center gap-3 px-4 py-3 mt-2 text-sm text-left text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors border-b border-gray-200 dark:border-gray-800 shrink-0"
            :class="{ 'pointer-events-none': flushing }"
            @click="closeSection"
          >
            <i class="pi pi-chevron-left text-xs text-gray-400 dark:text-gray-500" />
            <i :class="['pi', sections.find(s => s.id === activeSection)!.icon, 'text-gray-400 dark:text-gray-500']" />
            <span class="flex-1 font-medium">{{ sections.find(s => s.id === activeSection)!.label }}</span>
            <span v-if="flushing" class="text-xs text-gray-400 flex items-center gap-1">
              <i class="pi pi-spin pi-spinner text-xs" /> Saving...
            </span>
            <span v-else-if="showSaved" class="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
              <i class="pi pi-check text-xs" /> Saved
            </span>
          </button>

          <!-- Section content — scrollable, fades in after width expansion -->
          <div
            class="p-4 h-0 grow transition-opacity duration-150"
            :class="['delay-200', contentVisible ? 'opacity-100' : 'opacity-0', expanded ? 'overflow-auto' : 'overflow-hidden', flushing ? 'pointer-events-none opacity-50' : '']"
          >
            <component ref="sectionRef" :is="sections.find(s => s.id === activeSection)!.component" @saved="onSaved" />
          </div>
        </template>

      </div>
    </aside>
  </div>
</template>

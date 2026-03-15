<script setup lang="ts">
import { computed } from 'vue'
import type { CompanyStat } from '@/types/api'

const props = defineProps<{
  data: CompanyStat[]
  type: 'allowed' | 'blocked'
}>()

const rows = computed(() =>
  [...props.data]
    .sort((a, b) =>
      props.type === 'blocked'
        ? b.blocked_count - a.blocked_count
        : b.allowed_count - a.allowed_count
    )
    .slice(0, 10)
)

const countKey = computed(() => (props.type === 'blocked' ? 'blocked_count' : 'allowed_count'))
</script>

<template>
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-gray-200 dark:border-gray-700">
        <th class="text-left py-2 pr-4 font-medium text-gray-500 dark:text-gray-400 w-6">#</th>
        <th class="text-left py-2 pr-4 font-medium text-gray-500 dark:text-gray-400">Company</th>
        <th class="text-right py-2 font-medium text-gray-500 dark:text-gray-400">Queries</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="(company, i) in rows"
        :key="company.company_name"
        class="border-b border-gray-100 dark:border-gray-800 last:border-0"
      >
        <td class="py-2 pr-4 text-gray-400 dark:text-gray-500">{{ i + 1 }}</td>
        <td class="py-2 pr-4 truncate max-w-0 w-full">{{ company.company_name }}</td>
        <td class="py-2 text-right tabular-nums">
          <span
            :class="type === 'blocked' ? 'text-red-500 dark:text-red-400' : 'text-green-600 dark:text-green-400'"
            class="font-medium"
          >{{ company[countKey].toLocaleString() }}</span>
        </td>
      </tr>
      <tr v-if="rows.length === 0">
        <td colspan="3" class="py-4 text-center text-gray-400 dark:text-gray-500">No data</td>
      </tr>
    </tbody>
  </table>
</template>

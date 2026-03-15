<script setup lang="ts">
import type { EnrichedQuery } from '@/types/api'

defineProps<{
  queries: EnrichedQuery[]
  type: 'allowed' | 'blocked'
}>()

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function truncateDomain(domain: string, max = 35): string {
  return domain.length > max ? '…' + domain.slice(-(max - 1)) : domain
}
</script>

<template>
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-gray-200 dark:border-gray-700">
        <th class="text-left py-2 pr-3 font-medium text-gray-500 dark:text-gray-400">Time</th>
        <th class="text-left py-2 pr-3 font-medium text-gray-500 dark:text-gray-400">Domain</th>
        <th class="text-left py-2 font-medium text-gray-500 dark:text-gray-400">Company</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="q in queries"
        :key="q.id"
        class="border-b border-gray-100 dark:border-gray-800 last:border-0"
      >
        <td class="py-2 pr-3 tabular-nums text-gray-400 dark:text-gray-500 whitespace-nowrap">
          {{ formatTime(q.timestamp) }}
        </td>
        <td class="py-2 pr-3 font-mono text-xs" :title="q.domain">
          {{ truncateDomain(q.domain) }}
        </td>
        <td class="py-2 text-gray-500 dark:text-gray-400 truncate">
          {{ q.company_name ?? '—' }}
        </td>
      </tr>
      <tr v-if="queries.length === 0">
        <td colspan="3" class="py-4 text-center text-gray-400 dark:text-gray-500">No data</td>
      </tr>
    </tbody>
  </table>
</template>

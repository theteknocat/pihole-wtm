<script setup lang="ts">
import type { EnrichedQuery } from '@/types/api'

defineProps<{
  queries: EnrichedQuery[]
}>()

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

</script>

<template>
  <div class="overflow-x-auto">
  <table class="w-full text-sm min-w-[24rem]">
    <thead>
      <tr class="table-header-row">
        <th class="table-header-cell">Time</th>
        <th class="table-header-cell">Domain</th>
        <th class="table-header-cell !pr-0">Company</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="q in queries"
        :key="q.id"
        class="table-row"
      >
        <td class="py-2 pr-3 tabular-nums text-muted-inverse whitespace-nowrap">
          {{ formatTime(q.timestamp) }}
        </td>
        <td class="py-2 pr-3 font-mono text-xs truncate" :title="q.domain">
          {{ q.domain }}
        </td>
        <td class="py-2 text-muted truncate">
          {{ q.company_name ?? '—' }}
        </td>
      </tr>
      <tr v-if="queries.length === 0">
        <td colspan="3" class="table-empty">No data</td>
      </tr>
    </tbody>
  </table>
  </div>
</template>

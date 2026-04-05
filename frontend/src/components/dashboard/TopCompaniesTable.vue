<script setup lang="ts">
import { computed } from 'vue'
import type { CompanyStat } from '@/types/api'

const props = defineProps<{
  data: CompanyStat[]
  type: 'allowed' | 'blocked'
}>()

const emit = defineEmits<{ (e: 'select-company', company: string): void }>()

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
      <tr class="table-header-row">
        <th class="table-header-cell w-6">#</th>
        <th class="table-header-cell">Company</th>
        <th class="table-header-cell text-right !pr-0">Queries</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="(company, i) in rows"
        :key="company.company_name"
        class="table-row"
      >
        <td class="py-2 pr-4 text-muted-inverse">{{ i + 1 }}</td>
        <td class="py-2 pr-4 truncate max-w-0 w-full">
          <a
            href="#domain-company-details"
            v-tooltip.top="'Domains by company'"
            @click.prevent="emit('select-company', company.company_name)"
          >{{ company.company_name }}</a>
        </td>
        <td class="py-2 text-right tabular-nums">
          <span :class="type === 'blocked' ? 'text-blocked' : 'text-allowed'">
            {{ company[countKey].toLocaleString() }}
          </span>
        </td>
      </tr>
      <tr v-if="rows.length === 0">
        <td colspan="3" class="table-empty">No data</td>
      </tr>
    </tbody>
  </table>
</template>

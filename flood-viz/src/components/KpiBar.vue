<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { getSummary } from '@/api/api'
import { useAppStore } from '@/store/app'
import type { Scenario, Mode, SummaryKpi } from '@/api/types'

const store = useAppStore()
const kpi = ref<SummaryKpi | null>(null)

async function load() {
  const { data } = await getSummary(store.mode as Mode, store.scenario as Scenario)
  kpi.value = data
}

onMounted(load)
watch(() => [store.mode, store.scenario], load)
</script>

<template>
  <div class="grid grid-cols-4 gap-3">
    <div class="bg-white rounded shadow p-3">
      <div class="text-xs text-gray-500">Total Delay (min)</div>
      <div class="text-2xl font-semibold">{{ kpi?.total_delay_min?.toFixed(0) ?? '--' }}</div>
    </div>
    <div class="bg-white rounded shadow p-3">
      <div class="text-xs text-gray-500">Affected Segments</div>
      <div class="text-2xl font-semibold">{{ kpi ? (kpi.affected_ratio*100).toFixed(1) : '--' }}%</div>
    </div>
    <div class="bg-white rounded shadow p-3">
      <div class="text-xs text-gray-500">Top Segment</div>
      <div class="text-2xl font-semibold">#{{ kpi?.top_segment?.segment_id ?? '--' }}</div>
    </div>
    <div class="bg-white rounded shadow p-3">
      <div class="text-xs text-gray-500">Impacted Bus</div>
      <div class="text-2xl font-semibold">{{ kpi?.impacted_bus_count ?? '--' }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { Bar } from 'vue-chartjs'
import {
  Chart, BarElement, CategoryScale, LinearScale, Tooltip, Legend,
} from 'chart.js'
import { getDelay } from '@/api/api'
import { useAppStore } from '@/store/app'
import type { Scenario, Mode, DelayFeatureProps } from '@/api/types'

Chart.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const store = useAppStore()
const topN = 10

const dataRef = ref({
  labels: [] as string[],
  datasets: [{
    label: 'Delay (min)',
    data: [] as number[],
  }],
})

const optionsRef = ref({
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { ticks: { autoSkip: false, maxRotation: 45, minRotation: 0 } },
    y: { beginAtZero: true }
  }
})

async function load() {
  const { data } = await getDelay(store.mode as Mode, store.scenario as Scenario, 'segment', 2000)
  // Expect a FeatureCollection<LineString, DelayFeatureProps>
  const items = (data.features ?? [])
    .map(f => ({
      id: (f.properties as DelayFeatureProps | undefined)?.segment_id ?? -1,
      delay: (f.properties as DelayFeatureProps | undefined)?.delay_min ?? 0,
    }))
    .sort((a, b) => b.delay - a.delay)
    .slice(0, topN)

  dataRef.value.labels = items.map(it => `#${it.id}`)
  dataRef.value.datasets[0].data = items.map(it => it.delay)
}

onMounted(load)
watch(() => [store.mode, store.scenario], load)
</script>

<template>
  <div class="bg-white rounded shadow p-3 h-72">
    <div class="text-sm font-semibold mb-2">Top {{ topN }} Delayed Segments</div>
    <Bar :data="dataRef" :options="optionsRef" />
  </div>
</template>

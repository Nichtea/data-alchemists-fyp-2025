<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/store/app'

const store = useAppStore()
const s = computed<any>(() => store.selectedFlood || {})

const title = computed(() =>
  s.value.flooded_location || s.value.title || s.value.name || 'Flood details'
)
const idText = computed(() =>
  s.value.flood_id ?? s.value.id ?? s.value.flood_event_id ?? s.value.event_id ?? ''
)
const date = computed(() => s.value.date ?? '')
const lat = computed(() =>
  s.value.latitude ?? s.value.lat ?? s.value.center_lat ?? s.value.geom?.coordinates?.[1]
)
const lon = computed(() =>
  s.value.longitude ?? s.value.lon ?? s.value.center_lon ?? s.value.lng ?? s.value.geom?.coordinates?.[0]
)

const daily = computed(() => s.value['daily rainfall total (mm)'])
const r30 = computed(() => s.value['highest 30 min rainfall (mm)'])
const r60 = computed(() => s.value['highest 60 min rainfall (mm)'])
const r120 = computed(() => s.value['highest 120 min rainfall (mm)'])
const meanPr = computed(() => s.value.mean_pr)

// New: road segment fields from the API response of getFloodEventById
const roadName = computed(() => s.value.road_name)
const roadType = computed(() => s.value.road_type)
const lengthKm = computed(() => {
  const m = Number(s.value.length_m)
  return isFinite(m) ? (m / 1000).toFixed(3) : null
})
</script>

<template>
  <div class="bg-white rounded shadow p-3">
    <div class="text-base font-semibold mb-1">Flood</div>

    <div v-if="store.selectedFloodLoading" class="text-sm text-gray-500">
      Loading flood details...
    </div>

    <div v-else-if="!store.selectedFlood">
      <div class="text-sm text-gray-500">Click a flood event on the map to see details here.</div>
    </div>

    <div v-else>
      <div class="flex items-center justify-between mb-2">
        <div>
          <div class="font-semibold">{{ title }}</div>
          <div class="text-xs text-gray-500" v-if="idText">ID: {{ idText }}</div>
          <div class="text-xs text-gray-500" v-if="date">Date: {{ date }}</div>
        </div>
        <button class="text-xs text-gray-500 hover:text-gray-700" @click="store.clearSelection()">clear</button>
      </div>

      <div class="text-xs text-gray-600 space-y-1 mb-2">
        <div v-if="lat != null && lon != null">Location: {{ lat }}, {{ lon }}</div>
        <div v-if="daily != null">Daily rainfall (mm): {{ daily }}</div>
        <div v-if="r30 != null">Highest 30 min (mm): {{ r30 }}</div>
        <div v-if="r60 != null">Highest 60 min (mm): {{ r60 }}</div>
        <div v-if="r120 != null">Highest 120 min (mm): {{ r120 }}</div>
        <div v-if="meanPr != null">Mean PR: {{ meanPr }}</div>

        <!-- New: show road segment info if available -->
        <div class="pt-2 border-t border-gray-100 mt-2" v-if="roadName || roadType || lengthKm">
          <div class="text-gray-500">Road segment</div>
          <div v-if="roadName">Road: {{ roadName }}</div>
          <div v-if="roadType">Type: {{ roadType }}</div>
          <div v-if="lengthKm != null">Length: {{ lengthKm }} km</div>
        </div>
      </div>

      <details class="mt-3">
        <summary class="cursor-pointer text-xs text-gray-500">Raw</summary>
        <pre class="text-[11px] bg-gray-50 p-2 rounded overflow-auto">
{{ JSON.stringify(store.selectedFlood, null, 2) }}
        </pre>
      </details>
    </div>
  </div>
</template>

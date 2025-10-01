<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAppStore } from '@/store/app'

const store = useAppStore()

// Toggle if you ever want the raw JSON back
const showDebug = ref(false)

/** Normalize: sometimes API = object, sometimes = [object] */
const flood = computed<any>(() => {
  const f = store.selectedFlood
  if (!f) return {}
  return Array.isArray(f) ? (f[0] ?? {}) : f
})

/** Safe getters */
const title = computed(() =>
  flood.value.flooded_location || flood.value.title || flood.value.name || 'Flood details'
)
const idText = computed(() =>
  flood.value.flood_id ?? flood.value.id ?? flood.value.flood_event_id ?? flood.value.event_id ?? ''
)
const date = computed(() => flood.value.date ?? '')

const lat = computed(() =>
  flood.value.latitude ?? flood.value.lat ?? flood.value.center_lat ?? flood.value.geom?.coordinates?.[1] ?? null
)
const lon = computed(() =>
  flood.value.longitude ?? flood.value.lon ?? flood.value.center_lon ?? flood.value.lng ?? flood.value.geom?.coordinates?.[0] ?? null
)

/** Rainfall */
const daily = computed(() => flood.value['daily rainfall total (mm)'])
const r30 = computed(() => flood.value['highest 30 min rainfall (mm)'])
const r60 = computed(() => flood.value['highest 60 min rainfall (mm)'])
const r120 = computed(() => flood.value['highest 120 min rainfall (mm)'])
const meanPr = computed(() => flood.value.mean_pr)

/** Road segment */
const roadName = computed(() => flood.value.road_name)
const roadType = computed(() => flood.value.road_type)
const lengthKm = computed(() => {
  const m = Number(flood.value.length_m)
  return Number.isFinite(m) ? (m / 1000) : null
})

/** Traffic impact (format to 2 d.p. minutes) */
const t20 = computed(() => to2dp(flood.value.time_20kmh_min))
const t50 = computed(() => to2dp(flood.value.time_50kmh_min))
const delay = computed(() => to2dp(flood.value.time_travel_delay_min))

function to2dp(x: any) {
  const n = Number(x)
  return Number.isFinite(n) ? Number(n.toFixed(2)) : null
}

/** Display friendly lat/lon */
const latText = computed(() => (lat.value == null ? null : Number(lat.value).toFixed(6)))
const lonText = computed(() => (lon.value == null ? null : Number(lon.value).toFixed(6)))
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
      <!-- Header -->
      <div class="flex items-center justify-between mb-3">
        <div>
          <div class="font-semibold">{{ title }}</div>
          <div class="text-xs text-gray-500" v-if="idText">ID: {{ idText }}</div>
          <div class="text-xs text-gray-500" v-if="date">Date: {{ date }}</div>
        </div>
        <div class="flex items-center gap-2">
          <button v-if="showDebug" class="text-xs text-gray-500 hover:text-gray-700"
                  @click="showDebug = !showDebug">
            {{ showDebug ? 'Hide raw data' : 'Show raw data' }}
          </button>
          <button class="text-xs text-gray-500 hover:text-gray-700" @click="store.clearSelection()">clear</button>
        </div>
      </div>

      <!-- Event -->
      <div class="mb-3">
        <div class="font-medium text-gray-700 mb-1">Event</div>
        <div class="overflow-x-auto">
          <table class="min-w-full text-xs text-left text-gray-700 border">
            <tbody>
              <tr v-if="latText && lonText">
                <th class="border px-2 py-1 w-48 bg-gray-50">Location</th>
                <td class="border px-2 py-1">{{ latText }}, {{ lonText }}</td>
              </tr>
              <tr v-if="daily != null">
                <th class="border px-2 py-1 bg-gray-50">Daily rainfall</th>
                <td class="border px-2 py-1">{{ daily }} mm</td>
              </tr>
              <tr v-if="r30 != null">
                <th class="border px-2 py-1 bg-gray-50">Highest 30 min</th>
                <td class="border px-2 py-1">{{ r30 }} mm</td>
              </tr>
              <tr v-if="r60 != null">
                <th class="border px-2 py-1 bg-gray-50">Highest 60 min</th>
                <td class="border px-2 py-1">{{ r60 }} mm</td>
              </tr>
              <tr v-if="r120 != null">
                <th class="border px-2 py-1 bg-gray-50">Highest 120 min</th>
                <td class="border px-2 py-1">{{ r120 }} mm</td>
              </tr>
              <tr v-if="meanPr != null">
                <th class="border px-2 py-1 bg-gray-50">Mean PR</th>
                <td class="border px-2 py-1">{{ meanPr }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Road Segment -->
      <div v-if="roadName || roadType || lengthKm != null" class="mb-3">
        <div class="font-medium text-gray-700 mb-1">Road segment</div>
        <div class="overflow-x-auto">
          <table class="min-w-full text-xs text-left text-gray-700 border">
            <tbody>
              <tr v-if="roadName">
                <th class="border px-2 py-1 w-48 bg-gray-50">Road name</th>
                <td class="border px-2 py-1">{{ roadName }}</td>
              </tr>
              <tr v-if="roadType">
                <th class="border px-2 py-1 bg-gray-50">Type</th>
                <td class="border px-2 py-1">{{ roadType }}</td>
              </tr>
              <tr v-if="lengthKm != null">
                <th class="border px-2 py-1 bg-gray-50">Length</th>
                <td class="border px-2 py-1">{{ lengthKm.toFixed(3) }} km</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Traffic Impact -->
      <div v-if="t20 != null || t50 != null || delay != null">
        <div class="font-medium text-gray-700 mb-1">Traffic impact</div>
        <div class="overflow-x-auto">
          <table class="min-w-full text-xs text-left text-gray-700 border">
            <tbody>
              <tr v-if="t20 != null">
                <th class="border px-2 py-1 w-48 bg-gray-50">Time @ 20 km/h</th>
                <td class="border px-2 py-1">{{ t20 }} min</td>
              </tr>
              <tr v-if="t50 != null">
                <th class="border px-2 py-1 bg-gray-50">Time @ 50 km/h</th>
                <td class="border px-2 py-1">{{ t50 }} min</td>
              </tr>
              <tr v-if="delay != null">
                <th class="border px-2 py-1 bg-gray-50">Travel delay</th>
                <td class="border px-2 py-1">{{ delay }} min</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Optional raw JSON (off by default) -->
      <div v-if="showDebug" class="mt-3">
        <details>
          <summary class="cursor-pointer text-xs text-gray-500">Show raw data</summary>
          <pre class="text-[11px] bg-gray-50 p-2 rounded overflow-auto">
{{ JSON.stringify(flood, null, 2) }}
          </pre>
        </details>
      </div>
    </div>
  </div>
</template>

<!-- src/pages/PrivateTransport.vue -->
<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import MapCanvasCar from '@/components/MapCanvasCar.vue'
import TravelTimeBarChart from '@/components/TravelTimeBarChart.vue'
import AddressDetailsPanel from '@/components/AddressDetailsPanel.vue'
import { getOnemapCarRoute } from '@/api/api'
// import mockRouteResp from '@/mocks/mock.json'
const USE_MOCK = false

// ======== UI State ========
const startAddress = ref('143 Victoria St, Singapore 188019')
const endAddress = ref('961 Bukit Timah Rd, Singapore 588179')
const date = ref<string>('') // optional: YYYY-MM-DD
const time = ref<string>('') // optional: HH:mm

const loading = ref(false)
const errorMsg = ref<string | null>(null)

const routeResp = ref<any | null>(null)

const selectedIdx = ref<number>(0)

// ======== helpers ========
const overallStatus = computed<'clear' | 'flooded' | undefined>(
  () => routeResp.value?.overall_route_status
)
const simulation = computed<any | null>(
  () => routeResp.value?.time_travel_simulation || null
)

function decodePolyline(str: string): [number, number][] {
  let index = 0, lat = 0, lon = 0
  const out: [number, number][] = []
  while (index < str.length) {
    let b = 0, shift = 0, result = 0
    do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5 } while (b >= 0x20)
    const dlat = (result & 1) ? ~(result >> 1) : (result >> 1)
    lat += dlat
    shift = 0; result = 0
    do { b = str.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5 } while (b >= 0x20)
    const dlon = (result & 1) ? ~(result >> 1) : (result >> 1)
    lon += dlon
    out.push([lat / 1e5, lon / 1e5])
  }
  return out
}

function normalizeToPolylineList(route: any): [number, number][][] {
  if (!route) return []

  // 1) encoded polyline in `route_geometry` / `encoded`
  if (typeof route?.route_geometry === 'string') return [decodePolyline(route.route_geometry)]
  if (typeof route?.encoded === 'string') return [decodePolyline(route.encoded)]

  // 2) direct list like [[lon,lat] or [lat,lon]]
  const direct = route.polyline || route.path || route.points
  if (Array.isArray(direct) && direct.length && Array.isArray(direct[0])) {
    const guess = direct[0]
    const looksLonLat = Math.abs(guess[0]) > Math.abs(guess[1]) // 新加坡经度绝对值 > 纬度
    const mapped = direct.map((p: any) => {
      const a = Number(p[0]), b = Number(p[1])
      return looksLonLat ? [b, a] as [number, number] : [a, b] as [number, number]
    })
    return [mapped]
  }

  // 3) GeoJSON-like
  const gj = route.geometry || route.geojson || route.shape
  if (gj && gj.type && Array.isArray(gj.coordinates)) {
    if (gj.type === 'LineString') {
      const arr = gj.coordinates.map(([lon, lat]: any) => [Number(lat), Number(lon)])
      return [arr]
    }
    if (gj.type === 'MultiLineString') {
      return gj.coordinates.map((seg: any[]) => seg.map(([lon, lat]) => [Number(lat), Number(lon)]))
    }
  }

  return []
}


function normalizeFloodedSegments(r: any): [number, number][][] | null {
  
  if (Array.isArray(r?.flooded_segments) && r.flooded_segments.length) {
    
    const segs: [number, number][][] = []
    for (const seg of r.flooded_segments) {
      if (Array.isArray(seg) && seg.length) {
        const first = seg[0]
        const looksLonLat = Array.isArray(first) && Math.abs(first[0]) > Math.abs(first[1])
        const mapped = seg.map(([a, b]: any) => looksLonLat ? [b, a] : [a, b])
        segs.push(mapped as [number, number][])
      }
    }
    if (segs.length) return segs
  }

  
  if (typeof r?.flooded_geometry === 'string') {
    return [decodePolyline(r.flooded_geometry)]
  }

  return null
}


const allRoutesRaw = computed(() => {
  if (!routeResp.value) return []

  const main = routeResp.value
  const phy = routeResp.value?.phyroute
  const alts = Array.isArray(routeResp.value?.alternativeroute) ? routeResp.value.alternativeroute : []

  const list: any[] = []
  if (main && (main.route_geometry || main.geometry || main.encoded)) {
    list.push({ ...main, __label: main?.subtitle || 'Fastest route' })
  }
  if (phy && (phy.route_geometry || phy.geometry || phy.encoded)) {
    list.push({ ...phy, __label: phy?.subtitle || 'Shortest distance' })
  }
  for (const a of alts) {
    if (a && (a.route_geometry || a.geometry || a.encoded)) {
      list.push({ ...a, __label: a?.subtitle || 'Alternative' })
    }
  }
  return list
})


const routes = computed(() => {
  const list = allRoutesRaw.value
  if (!list.length) return []

  const items = list.map((r: any, i: number) => {
    const lines = normalizeToPolylineList(r)
    const duration_s = Number(
      r?.summary?.duration_s ??
      r?.route_summary?.total_time ??
      r?.duration_s ?? r?.duration ?? r?.time_s ?? r?.time
    )
    const distance_m = Number(
      r?.summary?.distance_m ??
      r?.route_summary?.total_distance ??
      r?.distance_m ?? r?.distance ?? r?.length_m
    )

    return {
      idx: i,
      label: r?.summary?.label || r?.__label || (i === 0 ? 'Primary' : `Alternative ${i}`),
      duration_s: Number.isFinite(duration_s) ? duration_s : undefined,
      distance_m: Number.isFinite(distance_m) ? distance_m : undefined,
      polylines: lines,
      flooded_segments: normalizeFloodedSegments(r), 
    }
  })

  const sel = Math.min(Math.max(selectedIdx.value ?? 0, 0), items.length - 1)
  
  const [picked] = items.splice(sel, 1)
  return [picked, ...items]
})

const endpoints = computed(() => {
  const r0 = routes.value?.[0]
  if (!r0 || !r0.polylines?.length || !r0.polylines[0]?.length) return { start: null, end: null }
  const first = r0.polylines[0][0]
  const lastSeg = [...r0.polylines].reverse().find(seg => seg && seg.length)
  const last = lastSeg ? lastSeg[lastSeg.length - 1] : null
  return {
    start: first ? { lat: first[0], lon: first[1] } : null,
    end:   last   ? { lat: last[0],  lon: last[1]  } : null,
  }
})

function minToSec(n: any): number | undefined {
  const v = Number(n); return Number.isFinite(v) ? Math.round(v * 60) : undefined
}
function sec(n: any): number | undefined {
  const v = Number(n); return Number.isFinite(v) ? Math.round(v) : undefined
}

const chartEntry = computed(() => {
  const sim = simulation.value
  if (!sim) return null

  const clear_s =
    sec(sim.clear_duration_s ?? sim.clear_s) ??
    minToSec(sim.t_clear_min ?? sim.clear_time_min) ??
    sec(routeResp.value?.route_summary?.total_time)

  const flood_s_from_field =
    sec(sim.flood_duration_s ?? sim.flood_s) ??
    minToSec(sim.t_flood_min ?? sim.flood_time_min)

  const delay_s =
    sec(sim.delay_s) ??
    minToSec(sim.delay_min ?? sim.additional_delay_min)

  const flood_s = flood_s_from_field ?? (
    clear_s != null && delay_s != null ? clear_s + delay_s : undefined
  )

  const primary_s = flood_s ?? clear_s
  if (primary_s == null) return null

  const scenarios: { scenario: string; duration_s: number }[] = []
  if (clear_s != null) scenarios.push({ scenario: 'Clear',   duration_s: clear_s })
  if (flood_s != null) scenarios.push({ scenario: 'Flooded', duration_s: flood_s })

  return {
    duration_s: primary_s,
    floodSummary: {
      baseline_s: clear_s,
      scenarios
    }
  }
})

async function fetchRoute() {
  errorMsg.value = null
  routeResp.value = null
  selectedIdx.value = 0
  if (!startAddress.value.trim() || !endAddress.value.trim()) {
    errorMsg.value = 'Please input start and end address.'
    return
  }
  loading.value = true
  try {
    let res: any

    if (USE_MOCK) {
      res = mockRouteResp
    } else {
      res = await getOnemapCarRoute({
        start_address: startAddress.value.trim(),
        end_address: endAddress.value.trim(),
        date: date.value || undefined,
        time: time.value || undefined,
      })
    }

    if (!res || typeof res !== 'object') throw new Error('Empty response')
    routeResp.value = res
    await nextTick()
  } catch (e: any) {
    errorMsg.value = e?.message || 'Failed to fetch route.'
  } finally {
    loading.value = false
  }
}

</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-6 bg-gray-50">
    <!-- LEFT: controls -->
    <div class="col-span-3 space-y-4">
      <AddressDetailsPanel
        v-model:startAddress="startAddress"
        v-model:endAddress="endAddress"
        v-model:date="date"
        v-model:time="time"
        :loading="loading"
        :errorMsg="errorMsg"
        :overallStatus="overallStatus"
        @search="fetchRoute"
      />

      <!-- Route options -->
      <div v-if="allRoutesRaw.length" class="bg-white rounded-2xl shadow-sm p-3 border border-gray-100">
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm font-semibold">Route options ({{ allRoutesRaw.length }})</div>
          <div v-if="overallStatus" class="text-xs">
            <span
              :class="overallStatus === 'flooded' ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-700'"
              class="px-2 py-0.5 rounded-full font-medium"
            >
              {{ overallStatus }}
            </span>
          </div>
        </div>

        <div class="space-y-2">
          <div
            v-for="(r, i) in allRoutesRaw"
            :key="i"
            class="rounded-xl border p-3 shadow-sm border-gray-200 hover:border-blue-300"
            :class="i === selectedIdx ? 'ring-2 ring-blue-200' : ''"
          >
            <div class="flex items-center gap-2 text-sm">
              <div class="font-medium">Option {{ i + 1 }}</div>
              <div class="text-gray-400">•</div>
              <div class="text-gray-700">
                ~ {{ Math.round((r?.route_summary?.total_time ?? 0) / 60) }} min
              </div>
              <div class="text-gray-400">•</div>
              <div class="text-gray-700">
                {{ ((r?.route_summary?.total_distance ?? 0) / 1000).toFixed(2) }} km
              </div>
              <div class="ml-auto text-xs text-gray-500">
                {{ r?.subtitle || 'Route' }}
              </div>
            </div>

            <div class="mt-1 text-xs text-gray-500">
              via: {{ r?.viaRoute || (Array.isArray(r?.route_name) ? r.route_name.join(' → ') : '-') }}
            </div>

            <div class="mt-2 flex items-center gap-2">
              <button
                class="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
                @click="selectedIdx = i"
                :disabled="selectedIdx === i"
              >
                Show on map
              </button>

              <details class="ml-auto">
                <summary class="cursor-pointer text-xs text-gray-500">Instructions</summary>
                <ol class="mt-2 space-y-1 text-xs text-gray-700 list-decimal list-inside">
                  <li v-for="(ins, idx2) in (r?.route_instructions || [])" :key="idx2">
                    {{ ins?.[9] || `${ins?.[0]} ${ins?.[1] || ''}` }}
                    <span class="text-[11px] text-gray-400" v-if="ins?.[5]"> — {{ ins[5] }}</span>
                  </li>
                </ol>
              </details>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- RIGHT: Chart + Map -->
    <div class="col-span-9">
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 h-[calc(100vh-3rem)] p-3 flex flex-col space-y-4">

        <!-- Moved chart here -->
        <div v-if="chartEntry" class="bg-gray-50 rounded-xl border border-gray-100 p-4">
          <TravelTimeBarChart :entry="chartEntry" title="Time Travel Simulation" />
        </div>

        <!-- Map section -->
        <div class="flex-1 min-h-0 overflow-hidden rounded-xl border border-gray-100">
          <div class="flex items-center justify-between mb-2 px-3 pt-2">
            <h3 class="text-sm font-medium text-gray-700">Car Route Map</h3>
            <div v-if="routes.length" class="text-xs text-gray-500">
              Showing {{ routes.length }} route(s)
            </div>
          </div>
          <MapCanvasCar
            :routes="routes"
            :overall-status="overallStatus"
            :simulation="simulation"
            :endpoints="endpoints"
          />
        </div>
      </div>
    </div>
  </div>
</template>


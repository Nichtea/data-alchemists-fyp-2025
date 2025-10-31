<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import MapCanvasCar from '@/components/MapCanvasCar.vue'
import TravelTimeBarChart from '@/components/TravelTimeBarChart.vue'
import AddressDetailsPanel from '@/components/AddressDetailsPanel.vue'
import { getOnemapCarRoute } from '@/api/api'
const USE_MOCK = false

const startAddress = ref('143 Victoria St, Singapore 188019')
const endAddress = ref('961 Bukit Timah Rd, Singapore 588179')
const date = ref<string>('') 
const time = ref<string>('') 

const loading = ref(false)
const errorMsg = ref<string | null>(null)
const routeResp = ref<any | null>(null)
const selectedIdx = ref<number>(0)

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
  if (typeof route?.route_geometry === 'string') {
    return [decodePolyline(route.route_geometry)]
  }
  if (typeof route?.encoded === 'string') {
    return [decodePolyline(route.encoded)]
  }

  // 2) direct list like [[lon,lat] or [lat,lon]]
  const direct = route.polyline || route.path || route.points
  if (Array.isArray(direct) && direct.length && Array.isArray(direct[0])) {
    const guess = direct[0] as any
    const looksLonLat = Math.abs(guess[0]) > Math.abs(guess[1])

    const mapped: [number, number][] = direct.map((p: any): [number, number] => {
      const a = Number(p[0])
      const b = Number(p[1])
      // force tuple return
      return looksLonLat ? [b, a] : [a, b]
    })

    return [mapped]
  }

  // 3) GeoJSON-like
  const gj = route.geometry || route.geojson || route.shape
  if (gj && gj.type && Array.isArray(gj.coordinates)) {
    if (gj.type === 'LineString') {
      const arr: [number, number][] = gj.coordinates.map(
        ([lon, lat]: any): [number, number] => [Number(lat), Number(lon)]
      )
      return [arr]
    }

    if (gj.type === 'MultiLineString') {
      const multi: [number, number][][] = gj.coordinates.map(
        (seg: any[]): [number, number][] =>
          seg.map(
            ([lon, lat]: any): [number, number] => [Number(lat), Number(lon)]
          )
      )
      return multi
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
  if (typeof r?.flooded_geometry === 'string') return [decodePolyline(r.flooded_geometry)]
  return null
}

const allRoutesRaw = computed(() => {
  if (!routeResp.value) return []
  const main = routeResp.value
  const phy = routeResp.value?.phyroute
  const alts = Array.isArray(routeResp.value?.alternativeroute)
    ? routeResp.value.alternativeroute
    : []
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

const selectedRouteRaw = computed<any | null>(() => {
  const list = allRoutesRaw.value
  if (!list.length) return null
  const idx = Math.min(Math.max(selectedIdx.value ?? 0, 0), list.length - 1)
  return list[idx]
})

const endpoints = computed(() => {
  const r0 = routes.value?.[0]
  if (!r0 || !r0.polylines?.length || !r0.polylines[0]?.length) return { start: null, end: null }
  const first = r0.polylines[0][0]
  const lastSeg = [...r0.polylines].reverse().find(seg => seg && seg.length)
  const last = lastSeg ? lastSeg[lastSeg.length - 1] : null
  return {
    start: first ? { lat: first[0], lon: first[1] } : null,
    end: last ? { lat: last[0], lon: last[1] } : null,
  }
})

function sec(n: any): number | undefined {
  const v = Number(n)
  return Number.isFinite(v) ? Math.round(v) : undefined
}
function minToSec(n: any): number | undefined {
  const v = Number(n)
  return Number.isFinite(v) ? Math.round(v * 60) : undefined
}

const chartEntry = computed(() => {
  const r = selectedRouteRaw.value
  if (!r) return null

  // 1. Baseline (non-flooded) travel time in seconds
  const baselineSecondsMaybe = sec(
    r?.route_summary?.total_time ??
    r?.summary?.duration_s
  )

  // If we can't get a baseline, we can't chart.
  if (baselineSecondsMaybe === undefined || baselineSecondsMaybe === null) {
    return null
  }

  // From here on, baselineSeconds is guaranteed number
  const baselineSeconds: number = baselineSecondsMaybe

  // 2. Flood penalties (extra delay in seconds to add)
  const sim = r.time_travel_simulation || simulation.value || {}

  // Helper to build each scenario row.
  // We convert delaySeconds (penalty) into total trip time (baseline + delay),
  // because the chart expects scenario.duration_s to be TOTAL trip time.
  function buildScenario(label: string, delaySeconds: any) {
    const delay_s = sec(delaySeconds)
    if (delay_s === undefined || delay_s === null) return null
    return {
      scenario: label,
      duration_s: baselineSeconds + delay_s, // total under this scenario
    }
  }

  // 3. Build scenarios
  const scenariosList = [
    // Baseline row, no extra delay:
    { scenario: 'Baseline (normal traffic)', duration_s: baselineSeconds },

    buildScenario('5 km/h flood',  sim['5kph_total_duration']),
    buildScenario('10 km/h flood', sim['10kph_total_duration']),
    buildScenario('20 km/h flood', sim['20kph_total_duration']),
    buildScenario('45 km/h flood', sim['45kph_total_duration']),
    // optionally include higher ones:
    // buildScenario('72 km/h flood', sim['72kph_total_duration']),
    // buildScenario('81 km/h flood', sim['81kph_total_duration']),
    // buildScenario('90 km/h flood', sim['90kph_total_duration']),
  ].filter(Boolean) as { scenario: string; duration_s: number }[]

  if (!scenariosList.length) return null

  return {
    // This is used by the chart to compute "baseMin"
    duration_s: baselineSeconds,

    floodSummary: {
      baseline_s: baselineSeconds,    // used for deltaMin calculation
      scenarios: scenariosList,       // rows for rendering
    },
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
    const res: any = await getOnemapCarRoute({
      start_address: startAddress.value.trim(),
      end_address: endAddress.value.trim(),
      date: date.value || undefined,
      time: time.value || undefined,
    })
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
  <div class="min-h-screen bg-gradient-to-br from-[#f1f5f9] via-[#f8fafc] to-[#e2e8f0] text-gray-800 p-5">
    <div class="grid grid-cols-12 gap-5 h-[calc(100vh-2rem)]">
      <!-- LEFT SIDEBAR -->
      <div class="col-span-3 flex flex-col gap-4">
        <div class="rounded-2xl border border-blue-200 bg-white/90 shadow-sm backdrop-blur-sm p-4">
          <div class="flex items-start gap-3 mb-3">
            <div class="h-10 w-10 flex items-center justify-center rounded-xl bg-[#1e3a8a] text-white font-bold text-sm shadow">
              🚗
            </div>
            <div>
              <div class="text-sm font-semibold text-gray-900">Flood-Viz Drive</div>
              <div class="text-[11px] text-gray-500 leading-snug">
                Simulate flood-affected travel times for private cars
              </div>
            </div>
          </div>

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
        </div>

        <div
          v-if="allRoutesRaw.length"
          class="rounded-2xl border border-gray-200 bg-white/90 shadow-sm backdrop-blur-sm p-4"
        >
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm font-semibold text-gray-800">
              Available Routes ({{ allRoutesRaw.length }})
            </div>
            <span
              v-if="overallStatus"
              class="text-xs px-2 py-0.5 rounded-full font-medium"
              :class="overallStatus === 'flooded'
                ? 'bg-rose-100 text-rose-700'
                : 'bg-emerald-100 text-emerald-700'"
            >
              {{ overallStatus }}
            </span>
          </div>

          <div class="space-y-3">
            <div
              v-for="(r, i) in allRoutesRaw"
              :key="i"
              class="border rounded-xl p-3 hover:border-blue-300 transition-all duration-200"
              :class="i === selectedIdx ? 'ring-2 ring-blue-200 bg-blue-50/40' : 'bg-white'"
            >
              <div class="flex items-center gap-2 text-sm text-gray-700">
                <span class="font-medium">Route {{ i + 1 }}</span>
                <span class="text-gray-400">•</span>
                <span>~ {{ Math.round((r?.route_summary?.total_time ?? 0) / 60) }} min</span>
                <span class="text-gray-400">•</span>
                <span>{{ ((r?.route_summary?.total_distance ?? 0) / 1000).toFixed(2) }} km</span>
              </div>
              <div class="text-[12px] text-gray-500 mt-1">
                via {{ r?.viaRoute || (Array.isArray(r?.route_name) ? r.route_name.join(' → ') : '-') }}
              </div>

              <div class="mt-2 flex items-center gap-2">
                <button
                  class="inline-flex items-center gap-1 bg-[#0ea5e9] hover:bg-[#0284c7] text-white text-sm font-medium rounded-md px-3 py-1.5 transition"
                  @click="selectedIdx = i"
                  :disabled="selectedIdx === i"
                >
                  Show on Map
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- RIGHT SECTION -->
      <div class="col-span-9 flex flex-col gap-4">
        <div
          class="flex-1 rounded-2xl border border-gray-200 bg-white/80 shadow-sm backdrop-blur-sm p-4 flex flex-col"
        >
          <div v-if="chartEntry" class="mb-4 border border-gray-200 bg-gray-50 rounded-xl p-4">
            <div class="flex items-center gap-2 mb-2 text-sm font-semibold text-gray-800">
              <span class="inline-flex items-center justify-center rounded bg-[#1e3a8a] text-white text-[10px] font-bold leading-none h-5 px-2 shadow">
                ETA
              </span>
              <span>Travel Time Simulation</span>
            </div>
            <TravelTimeBarChart :entry="chartEntry" title="Time Travel Simulation" />
          </div>

          <div class="flex-1 relative rounded-xl border-2 border-blue-200 overflow-hidden">
            <div
              class="absolute left-0 right-0 top-0 z-[5] flex items-center justify-between bg-gradient-to-r from-white/80 via-blue-50/60 to-white/80 text-[11px] text-gray-700 px-3 py-2 border-b border-blue-100"
            >
              <span class="font-medium text-[#1e3a8a] flex items-center gap-1">
                <span
                  class="inline-flex items-center justify-center rounded bg-[#1e3a8a] text-white text-[10px] font-bold leading-none h-5 px-2 shadow-sm"
                >
                  MAP
                </span>
                Car Route Simulation
              </span>
              <span class="text-gray-400">Zoom or click to inspect flooded segments</span>
            </div>

            <div class="absolute inset-0 pt-[34px]">
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
    </div>
  </div>
</template>

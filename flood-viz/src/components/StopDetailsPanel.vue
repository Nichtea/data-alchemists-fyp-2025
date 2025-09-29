<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAppStore } from '@/store/app'
import { geocodeSG, type Coords } from '@/lib/geocode'
import { getAllBusStops, getBusStopByCode, getBusTripsDelay, getOneMapPtRoute } from '@/api/api'

const store = useAppStore()

let BUS_ROUTES_CACHE: any[] | null = null
let BUS_ROUTES_PROMISE: Promise<any[]> | null = null

type ServiceDirStops = Record<string, Record<number, string[]>>
let SERVICE_INDEX_PROMISE: Promise<ServiceDirStops> | null = null

let currentRouteAbort: AbortController | null = null

function toLonLat(p: [number, number]) {
  const [lat, lon] = p
  return `${lon},${lat}`
}

async function buildServiceIndex(): Promise<ServiceDirStops> {
  if (SERVICE_INDEX_PROMISE) return SERVICE_INDEX_PROMISE
  SERVICE_INDEX_PROMISE = (async () => {
    const rows = await loadBusRoutes()
    const idx: ServiceDirStops = Object.create(null)
    const key = (r:any) => `${r.ServiceNo}|${r.Direction}`
    const groups = new Map<string, any[]>()
    for (const r of rows) {
      const k = key(r)
      if (!groups.has(k)) groups.set(k, [])
      groups.get(k)!.push(r)
    }
    for (const [k, arr] of groups) {
      arr.sort((a,b) => Number(a.StopSequence) - Number(b.StopSequence))
      const [svcStr, dirStr] = k.split('|')
      const svc = String(svcStr)
      const dir = Number(dirStr)
      if (!idx[svc]) idx[svc] = {}
      idx[svc][dir] = arr.map(x => String(x.BusStopCode))
    }
    return idx
  })()
  return SERVICE_INDEX_PROMISE
}

type OsrmRoute = { path: [number, number][], distance_m: number, duration_s: number }

async function osrmRouteVia(pointsLatLon: [number, number][], signal?: AbortSignal): Promise<OsrmRoute | null> {
  if (!pointsLatLon || pointsLatLon.length < 2) return null
  const coords = pointsLatLon.map(([lat, lon]) => `${lon},${lat}`).join(';')
  const url = `https://router.project-osrm.org/route/v1/driving/${coords}?overview=full&geometries=geojson&steps=false`
  const r = await fetch(url, { signal })
  if (!r.ok) throw new Error(`OSRM ${r.status}`)
  const j = await r.json()
  const route = j?.routes?.[0]
  const line = route?.geometry?.coordinates
  if (!Array.isArray(line)) return null
  return {
    path: line.map(([lon, lat]: [number, number]) => [lat, lon]) as [number, number][],
    distance_m: Number(route?.distance ?? 0),
    duration_s: Number(route?.duration ?? 0),
  }
}

async function osrmRouteViaChunked(points: [number,number][], chunkSize = 90, signal?: AbortSignal): Promise<OsrmRoute | null> {
  if (points.length <= chunkSize) return await osrmRouteVia(points, signal)
  const pieces: OsrmRoute[] = []
  for (let i = 0; i < points.length - 1; i += (chunkSize - 1)) {
    const slice = points.slice(i, Math.min(points.length, i + chunkSize))
    if (slice.length >= 2) {
      const seg = await osrmRouteVia(slice, signal)
      if (seg && seg.path.length) pieces.push(seg)
    }
    await new Promise(r => setTimeout(r, 50))
  }
  if (!pieces.length) return null
  const joined: [number,number][] = []
  let dist = 0, dura = 0
  for (let i = 0; i < pieces.length; i++) {
    const seg = pieces[i]
    if (!seg?.path?.length) continue
    if (i === 0) joined.push(...seg.path)
    else joined.push(...seg.path.slice(1))
    dist += seg.distance_m
    dura += seg.duration_s
  }
  return { path: joined, distance_m: dist, duration_s: dura }
}

async function computeRoadPathForSegment(codes: string[]): Promise<OsrmRoute | null> {
  const points: [number,number][] = []
  for (const c of codes) {
    const p = stopIndexByCode.value[c]
    if (p) points.push([p.lat, p.lon])
  }
  if (points.length < 2) return null

  const estimatedLen = points.length * 24
  const useChunked = estimatedLen > 7000
  const res = useChunked
    ? await osrmRouteViaChunked(points, 90)
    : await osrmRouteVia(points).catch(() => osrmRouteViaChunked(points, 90))
  return res && res.path.length >= 2 ? res : null
}

async function osrmRouteTwoStops(a: {lat:number; lon:number}, b:{lat:number; lon:number}): Promise<OsrmRoute | null> {
  const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=full&geometries=geojson&steps=false`
  const r = await fetch(url)
  if (!r.ok) throw new Error(`OSRM ${r.status}`)
  const j = await r.json()
  const route = j?.routes?.[0]
  const coords = route?.geometry?.coordinates
  if (!Array.isArray(coords)) return null
  return {
    path: coords.map(([lon,lat]:[number,number]) => [lat,lon]) as [number,number][],
    distance_m: Number(route?.distance ?? 0),
    duration_s: Number(route?.duration ?? 0),
  }
}

type DirectCandidate = {
  serviceNo: string
  dir: number
  stopCodes: string[]
  iA: number
  iB: number
  hops: number
}

async function findDirectCandidates(aCode: string, bCode: string): Promise<DirectCandidate[]> {
  const idx = await buildServiceIndex()
  const out: DirectCandidate[] = []
  for (const svc of Object.keys(idx)) {
    const dirMap = idx[svc]
    for (const dirStr of Object.keys(dirMap)) {
      const dir = Number(dirStr)
      const seq = dirMap[dir]
      const iA = seq.indexOf(aCode)
      const iB = seq.indexOf(bCode)
      if (iA >= 0 && iB > iA) out.push({ serviceNo: svc, dir, stopCodes: seq, iA, iB, hops: iB - iA })
    }
  }
  out.sort((a,b) => a.hops - b.hops)
  return out
}

function latLonFromCode(code: string): [number, number] | null {
  const p = stopIndexByCode.value[code]
  if (!p) return null
  return [p.lat, p.lon]
}

async function loadBusRoutes(): Promise<any[]> {
  if (BUS_ROUTES_CACHE) return BUS_ROUTES_CACHE
  if (!BUS_ROUTES_PROMISE) {
    BUS_ROUTES_PROMISE = fetch('/data/bus_routes.json', { cache: 'force-cache' })
      .then(r => {
        if (!r.ok) throw new Error(`fetch bus_routes.json ${r.status}`)
        return r.json()
      })
      .then(arr => (BUS_ROUTES_CACHE = Array.isArray(arr) ? arr : []))
      .catch(err => { BUS_ROUTES_PROMISE = null; throw err })
  }
  return BUS_ROUTES_PROMISE
}

async function getBusRoutes(busNumber: any, opts: { direction?: 1 | 2 } = {}) {
  const allRoutes = await loadBusRoutes()
  const svc = String(busNumber)
  const filtered = allRoutes.filter((r: any) => {
    if (String(r.ServiceNo) !== svc) return false
    if (opts.direction && Number(r.Direction) !== opts.direction) return false
    return true
  })
  filtered.sort((a: any, b: any) =>
    Number(a.Direction) - Number(b.Direction) ||
    Number(a.StopSequence) - Number(b.StopSequence)
  )
  return filtered
}

type StopIdx = { id: string; code: string; name: string; lat: number; lon: number; q: string }
const allStops = ref<StopIdx[]>([])
const loaded = ref(false)

const stopIndexByCode = computed<Record<string, { lat:number; lon:number; name:string }>>(() => {
  const m: Record<string, any> = {}
  for (const s of allStops.value) {
    if (s.code && Number.isFinite(s.lat) && Number.isFinite(s.lon)) {
      m[s.code] = { lat: s.lat, lon: s.lon, name: s.name }
    }
  }
  return m
})

const roadSegCache = new Map<string, [number, number][]>()

/** ---------- OneMap PT (address) state ---------- */
const ptLoading = ref(false)
const ptError = ref<string | null>(null)

/** ---------- UI state ---------- */
const originText = ref<string>('') // can be stop name/code OR a free-form address
const destText = ref<string>('')   // same as above
const originHover = ref(0)
const destHover   = ref(0)

/** ---------- Arrival cards ---------- */
const arrivals = ref<any[] | null>(null)
const arrivalsLoading = ref(false)
const arrivalsError = ref<string | null>(null)

/** ---------- Helpers ---------- */
function pickStopFields(s: any) {
  const lat = s.lat ?? s.latitude ?? s.stop_lat
  const lon = s.lon ?? s.lng ?? s.longitude ?? s.stop_lon
  const name = s.name ?? s.stop_name ?? s.description ?? s.stop_desc ?? ''
  const code = s.stop_code ?? s.code ?? s.id ?? s.stop_id ?? ''
  const id = s.stop_id ?? s.id
  return { lat: Number(lat), lon: Number(lon), name: String(name), code: String(code), id }
}

function norm(s: any) {
  return String(s ?? '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function searchStops(query: string) {
  const q = norm(query)
  if (!q) return []
  const scored = []
  for (const s of allStops.value) {
    const inName = s.q.includes(q)
    const codePrefix = s.code.startsWith(query.trim())
    if (inName || codePrefix) {
      const score =
        (codePrefix ? 100 : 0) +
        (s.name.toLowerCase().startsWith(q) ? 50 : 0) - s.name.length
      scored.push([score, s] as const)
    }
  }
  return scored.sort((a,b) => b[0]-a[0]).slice(0, 12).map(([,s]) => s)
}

const originSuggests = computed(() => searchStops(originText.value))
const destSuggests   = computed(() => searchStops(destText.value))

async function selectStopFor(which: 'origin'|'dest', s: StopIdx) {
  if (!s) return
  const coords = { lat: s.lat, lon: s.lon }
  const stopCode = s.code

  if (which === 'origin') {
    ;(store as any).setOrigin?.(coords)
    ;(store as any).setOriginStopCode?.(stopCode)
    originText.value = `${s.name} (${stopCode})`
    originHover.value = 0
  } else {
    ;(store as any).setDestination?.(coords)
    ;(store as any).setDestStopCode?.(stopCode)
    destText.value = `${s.name} (${stopCode})`
    destHover.value = 0
  }

  ;(store as any).highlightStop?.({ role: which, stop: { lat: s.lat, lon: s.lon, code: stopCode, name: s.name }})
  ;(store as any).flyTo?.(coords)

  store.selectStop(stopCode)
  const detail = await getBusStopByCode(stopCode)
  store.setSelectedStop(detail)
  store.setActiveTab('stops')
}

function onKeyNav(e: KeyboardEvent, which: 'origin'|'dest') {
  const list = which === 'origin' ? originSuggests.value : destSuggests.value
  const idxRef = which === 'origin' ? originHover : destHover
  if (!list.length) return

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    idxRef.value = (idxRef.value + 1) % list.length
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    idxRef.value = (idxRef.value - 1 + list.length) % list.length
  } else if (e.key === 'Enter') {
    e.preventDefault()
    selectStopFor(which, list[idxRef.value])
  }
}

function mins(n?: number) {
  if (!Number.isFinite(n)) return '-'
  return `${Math.round(Number(n) / 60)} min`
}

async function copyItinerary(d: any) {
  const dist = Number.isFinite(d?.distance_m) ? `${(d.distance_m/1000).toFixed(2)} km` : '-'
  const dura = Number.isFinite(d?.duration_s) ? mins(d.duration_s) : '-'
  const lines = [
    `Route: ${(store as any).serviceRouteOverlay?.serviceNo ?? ''} (Dir ${d?.dir ?? '-'})`,
    `Distance: ${dist}, Duration: ${dura}`,
    `Stops (${Array.isArray(d?.stopCodes) ? d.stopCodes.length : 0}):`,
  ]
  for (const code of (d?.stopCodes ?? [])) {
    const name = stopIndexByCode.value[code]?.name ?? 'Stop'
    lines.push(` - ${name} (${code})`)
  }
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    alert('Itinerary copied!')
  } catch {
    alert('Copy failed.')
  }
}

async function fetchArrivalsRaw(stopId: string) {
  const url = `https://arrivelah2.busrouter.sg/?id=${encodeURIComponent(stopId)}`
  const r = await fetch(url, { method: 'GET' })
  if (!r.ok) throw new Error(`arrivelah2 ${r.status}`)
  return await r.json()
}

async function fetchArrivalsForSelected() {
  const s: any = store.selectedStop
  const stopId = s?.stop_code ?? s?.stop_id ?? s?.code
  if (!stopId) { arrivals.value = null; return }

  arrivalsLoading.value = true
  arrivalsError.value = null
  try {
    const data = await fetchArrivalsRaw(String(stopId))
    arrivals.value = Array.isArray(data?.services) ? data.services : []
  } catch (e: any) {
    arrivalsError.value = e?.message || 'Failed to load arrivals'
    arrivals.value = null
  } finally {
    arrivalsLoading.value = false
  }
}

watch(() => store.selectedStop, () => { fetchArrivalsForSelected() }, { immediate: true })


/** ---------- OneMap PT: top-level function (VISIBLE TO TEMPLATE) ---------- */
async function queryPtRouteViaOneMap() {
  if (!originText.value || !destText.value) {
    alert('Enter a start and end address to use OneMap PT routing.')
    return
  }

  if (currentRouteAbort) currentRouteAbort.abort()
  currentRouteAbort = new AbortController()

  ptLoading.value = true
  ptError.value = null

  try {
    const res: any = await getOneMapPtRoute({
      start_address: originText.value,
      end_address: destText.value,
      time: '07:00:00', // tweak/parameterize as needed
    })

    const it = res?.plan?.itineraries?.[0]
    if (!it || !Array.isArray(it.legs) || !it.legs.length) {
      alert('No PT itinerary found.')
      return
    }

    // BUS legs -> stop codes -> de-dup
    const busLegs = it.legs.filter((l: any) => l?.mode === 'BUS')
    const stopCodes: string[] = []
    for (const leg of busLegs) {
      const a = leg?.from?.stopCode
      const b = leg?.to?.stopCode
      if (a) stopCodes.push(String(a))
      if (b) stopCodes.push(String(b))
    }
    const seen = new Set<string>()
    const segmentCodes = stopCodes.filter(c => !seen.has(c) && seen.add(c))

    // try to draw an OSRM road polyline following the bus segment chain
    let roadPath: [number, number][] | undefined
    if (segmentCodes.length >= 2) {
      const osrmRes = await computeRoadPathForSegment(segmentCodes)
      if (osrmRes?.path?.length) roadPath = osrmRes.path
    }

    const points: [number, number][] = segmentCodes
      .map(c => latLonFromCode(c))
      .filter(Boolean) as [number, number][]

    ;(store as any).setServiceRouteOverlay?.({
      serviceNo: 'OneMap PT',
      directions: [{
        dir: 1,
        points,
        stopCodes: segmentCodes,
        roadPath,
        duration_s: Number(it.duration ?? 0),
      }]
    })

    ;(store as any).oneMapLegs = it.legs // optional for richer popups
    ;(store as any).setActiveTab?.('stops')
    ;(store as any).fitToOverlayBounds?.()
  } catch (e: any) {
    ptError.value = e?.message || 'PT route failed'
    console.error(e)
  } finally {
    ptLoading.value = false
  }
}



/** ---------- Stop→Stop best route ---------- */
const hasOrigin = computed(() => Boolean((store as any).origin?.lat && (store as any).origin?.lon))
const hasDest = computed(() => Boolean((store as any).destination?.lat && (store as any).destination?.lon))

async function queryBestBusRoute() {
  // require explicit stop selection; for addresses use OneMap PT button
  if (!store.originStopCode || !store.destStopCode) {
    alert('Pick origin and destination bus stops from the suggestions first. For address-to-address, use “OneMap PT (address)”.')
    return
  }
  const aCode = store.originStopCode
  const bCode = store.destStopCode
  if (aCode === bCode) {
    alert('Origin and destination are the same stop.')
    return
  }

  const candidates = await findDirectCandidates(String(aCode), String(bCode))
  if (!candidates.length) {
    const a = stopIndexByCode.value[aCode]
    const b = stopIndexByCode.value[bCode]
    const res = a && b ? await osrmRouteTwoStops(a, b) : null
    if (res && res.path.length >= 2) {
      ;(store as any).setServiceRouteOverlay?.({
        serviceNo: `${aCode} → ${bCode}`,
        directions: [{
          dir: 1,
          points: res.path,
          stopCodes: [aCode, bCode],
          roadPath: res.path,
          distance_m: res.distance_m,
          duration_s: res.duration_s,
        }]
      })
      ;(store as any).setActiveTab?.('stops')
      ;(store as any).fitToOverlayBounds?.()
      return
    }
    alert('No direct service found between the two stops. (Transfers not implemented yet)')
    return
  }

  const best = candidates[0]
  const segmentCodes = best.stopCodes.slice(best.iA, best.iB + 1)
  const osrmRes = await computeRoadPathForSegment(segmentCodes)
  const points: [number,number][] = segmentCodes
    .map(c => latLonFromCode(c))
    .filter(Boolean) as [number,number][]

  ;(store as any).setServiceRouteOverlay?.({
    serviceNo: best.serviceNo,
    directions: [{
      dir: best.dir,
      points,
      stopCodes: segmentCodes,
      roadPath: osrmRes?.path ?? undefined,
      distance_m: osrmRes?.distance_m,
      duration_s: osrmRes?.duration_s,
    }]
  } as any)

  ;(store as any).setActiveTab?.('stops')
  ;(store as any).fitToOverlayBounds?.()
}

/** ---------- lifecycle ---------- */
onMounted(async () => {
  const rows = await getAllBusStops()
  allStops.value = rows
    .map(pickStopFields)
    .filter(s => Number.isFinite(s.lat) && Number.isFinite(s.lon) && s.code)
    .map(s => ({ ...s, q: norm(`${s.name} ${s.code}`) }))
  loaded.value = true
  buildServiceIndex().catch(() => {})
})
</script>

<template>
  <div class="bg-white rounded shadow p-3">
    <div class="text-base font-semibold mb-2">Stops</div>

    <div class="space-y-2 mb-3">
      <!-- Starts At -->
      <label class="block relative">
        <div class="text-xs text-gray-600 mb-1">Starts At</div>
        <input
          v-model="originText"
          type="text"
          placeholder="Type stop name/code or an address"
          class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          @keydown="onKeyNav($event, 'origin')"
          @focus="originHover = 0"
          autocomplete="off"
        />
        <div
          v-if="loaded && originText && originSuggests.length"
          class="absolute left-0 right-0 mt-1 z-20 bg-white border rounded shadow"
        >
          <ul class="max-h-64 overflow-auto text-sm">
            <li
              v-for="(s,i) in originSuggests"
              :key="'o-' + s.code"
              :class="['px-2 py-1 cursor-pointer flex items-center justify-between',
                      i===originHover ? 'bg-blue-50' : 'hover:bg-gray-50']"
              @mouseenter="originHover = i"
              @mousedown.prevent="selectStopFor('origin', s)"
            >
              <span class="truncate">{{ s.name }}</span>
              <span class="text-xs text-gray-500 ml-2 shrink-0">{{ s.code }}</span>
            </li>
          </ul>
        </div>
      </label>

      <!-- Ends At -->
      <label class="block relative mt-2">
        <div class="text-xs text-gray-600 mb-1">Ends At</div>
        <input
          v-model="destText"
          type="text"
          placeholder="Type stop name/code or an address"
          class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          @keydown="onKeyNav($event, 'dest')"
          @focus="destHover = 0"
          autocomplete="off"
        />
        <div
          v-if="loaded && destText && destSuggests.length"
          class="absolute left-0 right-0 mt-1 z-20 bg-white border rounded shadow"
        >
          <ul class="max-h-64 overflow-auto text-sm">
            <li
              v-for="(s,i) in destSuggests"
              :key="'d-' + s.code"
              :class="['px-2 py-1 cursor-pointer flex items-center justify-between',
                      i===destHover ? 'bg-blue-50' : 'hover:bg-gray-50']"
              @mouseenter="destHover = i"
              @mousedown.prevent="selectStopFor('dest', s)"
            >
              <span class="truncate">{{ s.name }}</span>
              <span class="text-xs text-gray-500 ml-2 shrink-0">{{ s.code }}</span>
            </li>
          </ul>
        </div>
      </label>

      <div class="flex items-center gap-2">
        <!-- stop→stop best route -->
        <button
          class="inline-flex items-center gap-2 rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-60"
          @click="queryBestBusRoute"
          title="Find best bus route between selected stops"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
               viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M5 6h14a2 2 0 012 2v7a3 3 0 01-3 3h-1l1 2m-8-2H8l-1 2M5 6V4a2 2 0 012-2h10a2 2 0 012 2v2M5 6h14"/>
          </svg>
          Find best bus route
        </button>

        <!-- OneMap PT (address→address via backend) -->
        <button
          class="inline-flex items-center gap-2 rounded bg-violet-600 text-white px-3 py-1.5 text-sm hover:bg-violet-700 disabled:opacity-60"
          @click="queryPtRouteViaOneMap"
          :disabled="ptLoading"
          title="Public transport via OneMap (type addresses above)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
            <path d="M6 3a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3v2a1 1 0 1 0 2 0v-2h8v2a1 1 0 1 0 2 0v-2a3 3 0 0 0 3-3V6a3 3 0 0 0-3-3H6zm0 2h12a1 1 0 0 1 1 1v6H5V6a1 1 0 0 1 1-1zm1.5 12a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm9 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/>
          </svg>
          {{ ptLoading ? 'Routing…' : 'OneMap PT (address)' }}
        </button>

        <span v-if="ptError" class="text-xs text-rose-600">{{ ptError }}</span>
      </div>
    </div>

    <div v-if="store.selectedStopLoading" class="text-sm text-gray-500">
      Loading stop details...
    </div>

    <div v-else-if="!store.selectedStop">
      <div class="text-sm text-gray-500">Click a stop on the map to see details here.</div>
    </div>

    <div v-else>
      <div class="flex items-center justify-between mb-2">
        <div>
          <div class="font-semibold">
            {{ (store.selectedStop as any)?.name || (store.selectedStop as any)?.stop_name || 'Stop details' }}
          </div>
        </div>
        <button class="text-xs text-gray-500 hover:text-gray-700" @click="store.clearSelection()">clear</button>
      </div>

      <div v-if="Array.isArray((store.selectedStop as any)?.service_routes)" class="mt-2">
        <div class="text-sm font-medium mb-1">Service routes</div>
        <ul class="space-y-1">
          <li v-for="(r, i) in (store.selectedStop as any).service_routes" :key="i" class="text-sm">
            {{ r?.name || r?.route_short_name || r?.route_long_name || r?.id || 'route' }}
          </li>
        </ul>
      </div>

      <div v-if="arrivalsLoading" class="text-sm text-gray-500 mt-3">Loading arrivals…</div>
      <div v-else-if="arrivalsError" class="text-sm text-rose-600 mt-3">{{ arrivalsError }}</div>

      <div v-else-if="arrivals && arrivals.length" class="mt-3">
        <div v-if="(store as any).serviceRouteOverlay" class="mt-4">
          <div class="rounded-xl border border-gray-200 bg-white/80 backdrop-blur shadow-sm p-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-600/10">
                  Best route
                </span>
                <div class="text-base font-semibold">
                  {{ (store as any).serviceRouteOverlay.serviceNo }}
                </div>
              </div>
              <button
                class="rounded-md border px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
                @click="store.fitToOverlayBounds()"
                title="Zoom to route"
              >
                Fit to route
              </button>
            </div>

            <div v-for="(d, i) in (store as any).serviceRouteOverlay.directions" :key="i" class="mt-3">
              <div class="flex items-center gap-2 text-sm">
                <div class="font-medium">Direction {{ d.dir }}</div>
                <div class="text-gray-400">•</div>
                <div v-if="Number.isFinite(d.distance_m)" class="text-gray-700">
                  ~ {{ (d.distance_m / 1000).toFixed(2) }} km
                </div>
                <div v-if="Number.isFinite(d.duration_s)" class="text-gray-700">
                  • ~ {{ Math.round(d.duration_s / 60) }} min
                </div>
                <div class="text-gray-400">•</div>
                <div class="text-gray-700">
                  {{ Array.isArray(d.stopCodes) ? (d.stopCodes.length - 1) : 0 }} stops
                </div>
                <div class="ml-auto text-xs text-gray-500">
                  geometry: {{ d.roadPath ? 'OSRM road' : 'stop-to-stop' }}
                </div>
              </div>

              <details class="mt-2 rounded-md bg-gray-50 p-3 open:bg-gray-100">
                <summary class="cursor-pointer select-none text-sm text-gray-700">Show stops</summary>
                <ol class="mt-2 space-y-1">
                  <li v-for="(code, idx) in (d.stopCodes || [])" :key="code" class="flex items-center gap-2 text-sm">
                    <span class="inline-flex h-5 w-5 items-center justify-center rounded-full bg-blue-600 text-white text-[11px]">{{ idx + 1 }}</span>
                    <span class="truncate">{{ stopIndexByCode[code]?.name || 'Stop' }}</span>
                    <span class="text-xs text-gray-500">({{ code }})</span>
                  </li>
                </ol>
              </details>

              <div class="mt-3 flex items-center gap-2">
                <button
                  class="inline-flex items-center gap-1 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 active:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2"
                  @click="store.fitToOverlayBounds()"
                >
                  View on map
                </button>
                <button
                  class="inline-flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 active:bg-gray-100"
                  @click="copyItinerary(d)"
                >
                  Copy itinerary
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="text-sm font-medium mb-2">Live arrivals</div>
        <div class="space-y-2">
          <div
            v-for="svc in arrivals"
            :key="svc.no"
            class="border rounded-md p-2 flex items-center justify-between"
          >
            <div class="flex items-center gap-3">
              <div class="text-base font-semibold tabular-nums">{{ svc.no }}</div>
              <div class="text-xs text-gray-500">
                <div>{{ svc.operator }}</div>
                <div v-if="svc.next?.time" class="text-[11px]">
                  ETA: {{ mins((svc.next?.duration_ms ?? 0) / 1000 * 60) }}
                </div>
              </div>
              <button
                class="inline-flex items-center gap-1.5 rounded-md bg-yellow-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:bg-yellow-700 active:bg-yellow-800 focus:outline-none focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2 transition-colors"
                title="Show this service route on map"
                @click="drawServiceRoute(svc.no)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 3a3 3 0 0 0-3 3v8a3 3 0 0 0 3 3v2a1 1 0 1 0 2 0v-2h8v2a1 1 0 1 0 2 0v-2a3 3 0 0 0 3-3V6a3 3 0 0 0-3-3H6zm0 2h12a1 1 0 0 1 1 1v6H5V6a1 1 0 0 1 1-1zm1.5 12a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm9 0a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/>
                </svg>
                Show route
              </button>
            </div>

            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 rounded text-[11px] bg-gray-100 text-gray-600">
                {{ (svc.next?.load || '-').toUpperCase() }}
              </span>
              <span v-if="svc.next?.feature === 'WAB'" class="px-2 py-0.5 rounded bg-blue-100 text-blue-700 text-[11px]" title="Wheelchair Accessible">
                WAB
              </span>
              <span class="text-[11px] text-gray-500">
                {{ svc.next?.type || '-' }}
              </span>
            </div>
          </div>
        </div>

        <details class="mt-2">
          <summary class="text-xs text-gray-500 cursor-pointer">More times</summary>
          <ul class="mt-2 space-y-1 text-xs text-gray-700">
            <li v-for="svc in arrivals" :key="svc.no + '-more'">
              <span class="font-medium">{{ svc.no }}</span> →
              <span>next2: {{ Math.round((svc.next2?.duration_ms ?? 0) / 60000) }} min</span>,
              <span>next3: {{ Math.round((svc.next3?.duration_ms ?? 0) / 60000) }} min</span>
            </li>
          </ul>
        </details>
      </div>

      <div v-else class="text-sm text-gray-500 mt-3">No live arrivals.</div>

      <details class="mt-3">
        <summary class="cursor-pointer text-xs text-gray-500">Raw</summary>
        <pre class="text-[11px] bg-gray-50 p-2 rounded overflow-auto">{{ JSON.stringify(store.selectedStop, null, 2) }}</pre>
      </details>
    </div>
  </div>
</template>

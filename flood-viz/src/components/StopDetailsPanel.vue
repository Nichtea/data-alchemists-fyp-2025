<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAppStore } from '@/store/app'
import { geocodeSG, type Coords, type BusStop } from '@/lib/geocode'
import { getAllBusStops, getBusStopByCode, getBusTripsDelay } from '@/api/api'

const store = useAppStore()

let BUS_ROUTES_CACHE: any[] | null = null
let BUS_ROUTES_PROMISE: Promise<any[]> | null = null

type ServiceDirStops = Record<string, Record<number, string[]>>   // serviceNo -> dir -> stopCodes[]
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
  const line = route?.geometry?.coordinates // [[lon,lat],...]
  if (!Array.isArray(line)) return null
  return {
    path: line.map(([lon, lat]: [number, number]) => [lat, lon]) as [number, number][],
    distance_m: Number(route?.distance ?? 0),
    duration_s: Number(route?.duration ?? 0),
  }
}

async function osrmRouteViaChunked(points: [number,number][], chunkSize = 90, signal?: AbortSignal): Promise<OsrmRoute | null> {
  if (points.length <= chunkSize) {
    return await osrmRouteVia(points, signal)
  }
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
  const coords = route?.geometry?.coordinates // [ [lon,lat], ... ]
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
      if (iA >= 0 && iB > iA) {
        out.push({ serviceNo: svc, dir, stopCodes: seq, iA, iB, hops: iB - iA })
      }
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

async function fetchRoadPathByStops(aCode: string, bCode: string) {
  const a = stopIndexByCode.value[aCode]
  const b = stopIndexByCode.value[bCode]
  if (!a || !b) return null

  const key = `${aCode}->${bCode}`
  if (roadSegCache.has(key)) return roadSegCache.get(key)!

  // OSRM: lon,lat;lon,lat
  const url = `https://router.project-osrm.org/route/v1/driving/${a.lon},${a.lat};${b.lon},${b.lat}?overview=full&geometries=geojson`
  const r = await fetch(url)
  if (!r.ok) return null
  const j = await r.json()
  const coords = j?.routes?.[0]?.geometry?.coordinates // [[lon,lat], ...]
  if (!Array.isArray(coords)) return null

  const latlngs: [number, number][] = coords.map(([lon, lat]: [number, number]) => [lat, lon])
  roadSegCache.set(key, latlngs)
  return latlngs
}

type ServiceRouteOverlay = {
  serviceNo: string
  directions: Array<{
    dir: number
    points: [number, number][]
    stopCodes: string[]
    roadPath?: [number, number][]
  }>
}

async function drawServiceRoute(serviceNo: string) {
  if (!serviceNo) return

  if (currentRouteAbort) currentRouteAbort.abort()
  currentRouteAbort = new AbortController()
  const { signal } = currentRouteAbort

  const routes = await getBusRoutes(serviceNo)
  if (!Array.isArray(routes) || routes.length === 0) {
    alert(`No route found for service ${serviceNo}`)
    return
  }

  const byDir = new Map<number, any[]>()
  for (const r of routes) {
    const dir = Number(r.Direction ?? r.direction ?? 1)
    if (!byDir.has(dir)) byDir.set(dir, [])
    byDir.get(dir)!.push(r)
  }

  const directions: ServiceRouteOverlay['directions'] = []
  for (const [dir, arr] of byDir.entries()) {
    arr.sort((a,b) => Number(a.StopSequence) - Number(b.StopSequence))
    const points: [number,number][] = []
    const stopCodes: string[] = []
    for (const row of arr) {
      const code = String(row.BusStopCode ?? row.busStopCode ?? '')
      const p = stopIndexByCode.value[code]
      if (p && Number.isFinite(p.lat) && Number.isFinite(p.lon)) {
        points.push([p.lat, p.lon])
        stopCodes.push(code)
      }
    }
    if (points.length >= 2) directions.push({ dir, points, stopCodes })
  }

  if (!directions.length) {
    alert(`Service ${serviceNo}: no plottable points`)
    return
  }

  ;(store as any).setServiceRouteOverlay?.({ serviceNo, directions })

  await Promise.all(directions.map(async (d) => {
    try {
      const estimatedLen = d.points.length * 24
      const useChunked = estimatedLen > 7000
      const res = useChunked
        ? await osrmRouteViaChunked(d.points, 90, signal)
        : await osrmRouteVia(d.points, signal).catch(() => osrmRouteViaChunked(d.points, 90, signal))

      if (res && res.path.length >= 2) {
        // 存回
        (d as any).roadPath = res.path
        ;(d as any).distance_m = res.distance_m
        ;(d as any).duration_s = res.duration_s
      }
    } catch {}
  }))


  ;(store as any).setServiceRouteOverlay?.({
    serviceNo,
    directions: directions.map(d => ({ ...d }))
  })
}

/** Existing stop details */
const title = computed(() => {
  const s: any = store.selectedStop
  return s?.name || s?.stop_name || 'Stop details'
})
const code = computed(() => {
  const s: any = store.selectedStop
  return s?.stop_code ?? s?.code ?? s?.stop_id ?? ''
})
const lat = computed(() => {
  const s: any = store.selectedStop
  return s?.lat ?? s?.latitude ?? s?.stop_lat
})
const lon = computed(() => {
  const s: any = store.selectedStop
  return s?.lon ?? s?.lng ?? s?.longitude ?? s?.stop_lon
})


type StopIdx = { id: string; code: string; name: string; lat: number; lon: number; q: string }
const allStops = ref<StopIdx[]>([])
const loaded = ref(false)

function norm(s: any) {
  return String(s ?? '')
    .toLowerCase()
    .normalize('NFKD')        // 去掉重音
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
}


onMounted(async () => {
  const rows = await getAllBusStops()
  allStops.value = rows
    .map(pickStopFields)
    .filter(s => Number.isFinite(s.lat) && Number.isFinite(s.lon) && s.code)
    .map(s => ({ ...s, q: norm(`${s.name} ${s.code}`) }))
  loaded.value = true
  buildServiceIndex().catch(() => {})
})

/** Origin/Destination inputs */
const originText = ref<string>('')
const destText = ref<string>('')
const originHover = ref(0)
const destHover   = ref(0)

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


function searchStops(query: string) {
  const q = norm(query)
  if (!q) return []
  // 简单包含匹配，优先 code 完全前缀 > 名称包含；再按名称长度和 code 排序
  const scored = []
  for (const s of allStops.value) {
    const inName = s.q.includes(q)
    const codePrefix = s.code.startsWith(query.trim())
    if (inName || codePrefix) {
      const score =
        (codePrefix ? 100 : 0) +
        (s.name.toLowerCase().startsWith(q) ? 50 : 0) -
        s.name.length
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

const locating = ref<{ origin: boolean; dest: boolean }>({ origin: false, dest: false })

const arrivals = ref<any[] | null>(null)
const arrivalsLoading = ref(false)
const arrivalsError = ref<string | null>(null)




function msToMins(ms?: number) {
  if (!ms && ms !== 0) return '-'
  const m = Math.floor(ms / 60000)
  const s = Math.round((ms % 60000) / 1000)
  if (m <= 0 && s <= 0) return 'Arr'
  if (m <= 0) return `${s}s`
  return `${m} min`
}

function loadBadge(load?: string) {
  // SEA = Seats Available, SDA = Standing Available, LSE = Limited Standing
  switch ((load || '').toUpperCase()) {
    case 'SEA': return { text: 'Seats',    cls: 'bg-emerald-100 text-emerald-700' }
    case 'SDA': return { text: 'Standing', cls: 'bg-amber-100 text-amber-700' }
    case 'LSE': return { text: 'Limited',  cls: 'bg-rose-100 text-rose-700' }
    default:    return { text: '-',        cls: 'bg-gray-100 text-gray-600' }
  }
}

async function fetchArrivalsForSelected() {
  const s: any = store.selectedStop
  const stopId = s?.stop_code ?? s?.stop_id ?? s?.code
  if (!stopId) { arrivals.value = null; return }

  arrivalsLoading.value = true
  arrivalsError.value = null
  try {
    // const data = await fetchArrivalsRaw(String(stopId))
    const data = await fetchArrivalsRaw(String(stopId))  // 走代理的版本
    arrivals.value = Array.isArray(data?.services) ? data.services : []
  } catch (e: any) {
    arrivalsError.value = e?.message || 'Failed to load arrivals'
    arrivals.value = null
  } finally {
    arrivalsLoading.value = false
  }
}

watch(() => store.selectedStop, () => {
  fetchArrivalsForSelected()
}, { immediate: true })





let _stopsCache: any[] | null = null

function haversine(a: Coords, b: Coords) {
  const toRad = (x: number) => x * Math.PI / 180
  const R = 6371000 // m
  const dLat = toRad(b.lat - a.lat)
  const dLon = toRad(b.lon - a.lon)
  const lat1 = toRad(a.lat), lat2 = toRad(b.lat)
  const h = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2
  return 2 * R * Math.asin(Math.sqrt(h)) // meters
}

function pickStopFields(s: any) {

  // {
  //   "geom": "0101000020E61000000466589120F95940EFF5BAAEC5D2F53F",
  //   "stop_code": "63249",
  //   "stop_id": "63249",
  //   "stop_lat": 1.36395805601148,
  //   "stop_lon": 103.892612778021,
  //   "stop_name": "Blk 1",
  //   "stop_url": "https://busrouter.sg/#/stops/63249",
  //   "wheelchair_boarding": 1
  // },

  const lat = s.lat ?? s.latitude ?? s.stop_lat
  const lon = s.lon ?? s.lng ?? s.longitude ?? s.stop_lon
  const name = s.name ?? s.stop_name ?? s.description ?? s.stop_desc ?? ''
  const code = s.stop_code ?? s.code ?? s.id ?? s.stop_id ?? ''
  const id = s.stop_id ?? s.id  
  return { lat: Number(lat), lon: Number(lon), name: String(name), code: String(code), id }
}

async function findNearestStop(coords: Coords) {
  if (!_stopsCache) _stopsCache = await getAllBusStops()
  let best: { stop: any; dist: number } | null = null
  for (const raw of _stopsCache!) {
    const s = pickStopFields(raw)
    if (!isFinite(s.lat) || !isFinite(s.lon)) continue
    const d = haversine(coords, { lat: s.lat, lon: s.lon })
    if (!best || d < best.dist) best = { stop: s, dist: d }
  }
  return best // { stop, dist } | null
}

async function locate(which: 'origin' | 'dest') {
  const isOrigin = which === 'origin'
  const value = isOrigin ? originText.value : destText.value
  if (!value) return

  locating.value[which] = true
  try {
   
    const coords = await geocodeSG(value)
    if (!coords) {
      alert('Address not found…')
      return
    }

 
    if (isOrigin) (store as any).setOrigin?.(coords)
    else          (store as any).setDestination?.(coords)
    ;(store as any).flyTo?.(coords)

 
    const found = await findNearestStop(coords)
    if (!found) { alert('No bus stops found nearby.'); return }

    console.log(found)

    const stopCode = String(found.stop.code || found.stop.id) // ← 先算出来

 
    store.setLayerVisible('stops', true)
    store.setActiveTab('stops')

    if (isOrigin) (store as any).setOriginStopCode?.(stopCode)
    else          (store as any).setDestStopCode?.(stopCode)

 
    ;(store as any).highlightStop?.({
      role: isOrigin ? 'origin' : 'dest',
      stop: {
        lat: found.stop.lat,
        lon: found.stop.lon,
        code: stopCode,
        name: found.stop.name
      }
    })

    store.selectStop(stopCode)
    const detail = await getBusStopByCode(stopCode)
    store.setSelectedStop(detail)

    console.log(
      `Nearest stop: ${detail?.name ?? 'Stop'} (${detail?.stop_code ?? ''}) • ${(found.dist/1000).toFixed(2)} km`
    )
  } finally {
    locating.value[which] = false
  }
}

async function fetchArrivalsRaw(stopId: string) {
  const url = `https://arrivelah2.busrouter.sg/?id=${encodeURIComponent(stopId)}`
  const r = await fetch(url, { method: 'GET' })
  if (!r.ok) throw new Error(`arrivelah2 ${r.status}`)
  return await r.json()
}


const hasOrigin = computed(() => Boolean((store as any).origin?.lat && (store as any).origin?.lon))
const hasDest = computed(() => Boolean((store as any).destination?.lat && (store as any).destination?.lon))



/** Find best bus route: originStopCode -> destStopCode
 *  Priority: 1) direct service on the same line (correct direction, A before B)
 *            2) fallback to OSRM road route from A→B (still shows distance/time)
 *  Writes the result into store.serviceRouteOverlay and triggers fitToOverlayBounds.
 */
 async function queryBestBusRoute() {
  // If inputs are typed but store has no stop codes yet, try geocoding to nearest stops.
  if (!store.originStopCode || !store.destStopCode) {
    if (!hasOrigin.value && originText.value) await locate('origin')
    if (!hasDest.value && destText.value)     await locate('dest')
  }

  const aCode = store.originStopCode
  const bCode = store.destStopCode
  if (!aCode || !bCode) {
    alert('Please set both origin and destination (nearest stops).')
    return
  }
  if (aCode === bCode) {
    alert('Origin and destination are the same stop.')
    return
  }

  // 1) Try to find direct candidates (same service, A appears before B).
  const candidates = await findDirectCandidates(String(aCode), String(bCode))

  // 1.1 No direct service: fallback to OSRM from A to B (road-following polyline).
  if (!candidates.length) {
    const a = stopIndexByCode.value[aCode]
    const b = stopIndexByCode.value[bCode]
    const res = a && b ? await osrmRouteTwoStops(a, b) : null

    if (res && res.path.length >= 2) {
      ;(store as any).setServiceRouteOverlay?.({
        serviceNo: `${aCode} → ${bCode}`,   // fallback title uses stop codes
        directions: [{
          dir: 1,
          points: res.path,                 // used by the map
          stopCodes: [aCode, bCode],        // just A→B for display
          roadPath: res.path,               // map should prefer roadPath when present
          distance_m: res.distance_m,       // approx distance (meters)
          duration_s: res.duration_s,       // approx duration (seconds)
        }]
      })

      ;(store as any).setActiveTab?.('stops')
      ;(store as any).fitToOverlayBounds?.()
      return
    }

    alert('No direct service found between the two stops. (Transfers not implemented yet)')
    return
  }

  // 1.2 Pick the best direct candidate (fewest hops).
  const best = candidates[0]

  // All stop codes within the direct segment (inclusive).
  const segmentCodes = best.stopCodes.slice(best.iA, best.iB + 1)

  // OSRM snap-to-road for that segment; may chunk when there are many waypoints.
  const osrmRes = await computeRoadPathForSegment(segmentCodes)

  // Also keep the plain stop coordinates sequence as a fallback/for tooltip.
  const points: [number,number][] = segmentCodes
    .map(c => latLonFromCode(c))
    .filter(Boolean) as [number,number][]

  ;(store as any).setServiceRouteOverlay?.({
    serviceNo: best.serviceNo,                  // e.g., "14", "196", etc.
    directions: [{
      dir: best.dir,                            // 1 or 2
      points,                                   // fallback polyline built from stop coords
      stopCodes: segmentCodes,                  // list of stop codes
      roadPath: osrmRes?.path ?? undefined,     // road-following polyline if available
      distance_m: osrmRes?.distance_m,          // approx distance (meters)
      duration_s: osrmRes?.duration_s,          // approx duration (seconds)
    }]
  } as any)

  ;(store as any).setActiveTab?.('stops')
  ;(store as any).fitToOverlayBounds?.()
}




</script>

<template>
  <div class="bg-white rounded shadow p-3">
    <div class="text-base font-semibold mb-2">Stops</div>

    <div class="space-y-2 mb-3">
      <!-- <label class="block">
        <div class="text-xs text-gray-600 mb-1">Starts At</div>
        <div class="flex items-stretch gap-2">
          <input
            v-model="originText"
            type="text"
            placeholder='Enter address or "lat, lon"'
            class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          />
          <button
            class="shrink-0 inline-flex items-center gap-1 rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-60"
            @click="locate('origin')"
            :disabled="locating.origin"
            title="Locate origin"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
                 viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 8v4l3 3M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <span v-if="!locating.origin">Locate</span>
            <span v-else>Locating…</span>
          </button>
        </div>
      </label>

      <label class="block">
        <div class="text-xs text-gray-600 mb-1">Ends At</div>
        <div class="flex items-stretch gap-2">
          <input
            v-model="destText"
            type="text"
            placeholder='Enter address or "lat, lon"'
            class="flex-1 rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          />
          <button
            class="shrink-0 inline-flex items-center gap-1 rounded border border-gray-300 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-60"
            @click="locate('dest')"
            :disabled="locating.dest"
            title="Locate destination"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
                 viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                    d="M12 8v4l3 3M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <span v-if="!locating.dest">Locate</span>
            <span v-else>Locating…</span>
          </button>
        </div>
      </label> -->



      <!-- Starts At -->
      <label class="block relative">
        <div class="text-xs text-gray-600 mb-1">Starts At</div>
        <input
          v-model="originText"
          type="text"
          placeholder="Type stop name or code (e.g. 21161)"
          class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          @keydown="onKeyNav($event, 'origin')"
          @focus="originHover = 0"
          autocomplete="off"
        />
        <!-- 建议下拉 -->
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
          placeholder="Type stop name or code (e.g. 21161)"
          class="w-full rounded border border-gray-300 px-2 py-1 text-sm focus:outline-none focus:ring focus:ring-blue-200"
          @keydown="onKeyNav($event, 'dest')"
          @focus="destHover = 0"
          autocomplete="off"
        />
        <!-- 建议下拉 -->
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


      <div>
        <button
          class="inline-flex items-center gap-2 rounded bg-blue-600 text-white px-3 py-1.5 text-sm hover:bg-blue-700 disabled:opacity-60"
          @click="queryBestBusRoute"
          :disabled="locating.origin || locating.dest"
          title="Find best bus route"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4"
               viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M5 6h14a2 2 0 012 2v7a3 3 0 01-3 3h-1l1 2m-8-2H8l-1 2M5 6V4a2 2 0 012-2h10a2 2 0 012 2v2M5 6h14"/>
          </svg>
          Find best bus route
        </button>
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
          <div class="font-semibold">{{ title }}</div>
          <!-- <div class="text-xs text-gray-500" v-if="code">Code: {{ code }}</div> -->
        </div>
        <button class="text-xs text-gray-500 hover:text-gray-700" @click="store.clearSelection()">clear</button>
      </div>

      <!-- <div class="text-xs text-gray-600 space-y-1 mb-2">
        <div v-if="lat != null && lon != null">Location: {{ lat }}, {{ lon }}</div>
      </div> -->

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
         <!-- Best Route Card -->
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

                <!-- Stop list (collapsible) -->
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

                <!-- Action buttons -->
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
                  ETA: {{ msToMins(svc.next?.duration_ms) }}
                </div>
              </div>
              <button
                class="inline-flex items-center gap-1.5 rounded-md  bg-yellow-600 px-3 py-1.5 text-sm font-medium text-white
                      shadow-sm hover:bg-yellow-700 active:bg-yellow-800
                      focus:outline-none focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2
                      transition-colors"
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
              <span
                class="px-2 py-0.5 rounded text-[11px]"
                :class="loadBadge(svc.next?.load).cls"
              >
                {{ loadBadge(svc.next?.load).text }}
              </span>
              <span
                v-if="svc.next?.feature === 'WAB'"
                class="px-2 py-0.5 rounded bg-blue-100 text-blue-700 text-[11px]"
                title="Wheelchair Accessible"
              >
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
              <span>next2: {{ msToMins(svc.next2?.duration_ms) }}</span>,
              <span>next3: {{ msToMins(svc.next3?.duration_ms) }}</span>
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
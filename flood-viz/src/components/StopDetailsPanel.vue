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

/* ---------------- Flood timing helpers ---------------- */
function toNumOrUndefined(val: unknown): number | undefined {
  if (typeof val === 'number' && Number.isFinite(val)) return val
  if (Array.isArray(val) && val.length && Number.isFinite(val[0] as any)) return Number(val[0])
  return undefined
}

function legIsFlooded(leg: any): boolean {
  if (!leg || leg.mode !== 'BUS') return false
  // prefer explicit flag
  const flag = String(leg?.overall_bus_route_status || '').toLowerCase()
  if (flag === 'flooded') return true
  if (flag === 'clear') return false

  const base = toNumOrUndefined(leg.non_flooded_bus_duration)
  if (!Number.isFinite(base)) return false
  const candidates = [
    toNumOrUndefined(leg['5kmh_flooded_bus_duration']),
    toNumOrUndefined(leg['12kmh_flooded_bus_duration']),
    toNumOrUndefined(leg['30kmh_flooded_bus_duration']),
    toNumOrUndefined(leg['48kmh_flooded_bus_duration']),
  ].filter((x): x is number => Number.isFinite(x as any))
  return candidates.some(v => v! > (base as number))
}

/** Aggregate non-flooded & flooded durations (seconds) across all BUS legs */
function summarizeFloodDurations(legs: any[]) {
  let baseline_s = 0
  let anyBaseline = false
  const map = new Map<string, number>() // scenario -> seconds

  for (const leg of legs ?? []) {
    if (leg?.mode !== 'BUS') continue

    // baseline (non-flooded)
    const base = toNumOrUndefined((leg as any).non_flooded_bus_duration)
    if (Number.isFinite(base)) {
      baseline_s += base!
      anyBaseline = true
    }

    // flooded scenarios
    const pairs: Array<[label: string, key: string]> = [
      ['5 km/h flooded',  '5kmh_flooded_bus_duration'],
      ['12 km/h flooded', '12kmh_flooded_bus_duration'],
      ['30 km/h flooded', '30kmh_flooded_bus_duration'],
      ['48 km/h flooded', '48kmh_flooded_bus_duration'],
    ]
    for (const [label, key] of pairs) {
      const v = toNumOrUndefined((leg as any)[key])
      if (Number.isFinite(v)) {
        map.set(label, (map.get(label) ?? 0) + (v as number))
      }
    }
  }

  return {
    baseline_s: anyBaseline ? baseline_s : undefined,
    scenarios: Array.from(map.entries()).map(([scenario, duration_s]) => ({ scenario, duration_s }))
      .sort((a,b) => a.duration_s - b.duration_s),
  }
}



/* -------- NEW: helpers for route chips & stop lists -------- */
function legStops(leg: any): string[] {
  if (!leg?.transitLeg || leg?.mode !== 'BUS') return []
  const arr: string[] = []
  const a = leg?.from?.stopCode && String(leg.from.stopCode)
  const b = leg?.to?.stopCode && String(leg.to.stopCode)
  if (a) arr.push(a)
  if (Array.isArray(leg?.intermediateStops)) {
    for (const st of leg.intermediateStops) {
      if (st?.stopCode) arr.push(String(st.stopCode))
    }
  }
  if (b) arr.push(b)
  return arr.filter((c, i) => i === 0 || c !== arr[i - 1])
}
function legStatus(leg: any): 'flooded' | 'clear' {
  const flag = String(leg?.overall_bus_route_status || '').toLowerCase()
  if (flag === 'flooded') return 'flooded'
  if (flag === 'clear') return 'clear'
  return legIsFlooded(leg) ? 'flooded' : 'clear'
}
function legChipStyle(leg: any) {
  const s = legStatus(leg)
  return s === 'flooded'
    ? { bg: '#fee2e2', text: '#b91c1c', ring: 'rgba(239,68,68,.25)' }
    : { bg: '#dbeafe', text: '#1d4ed8', ring: 'rgba(59,130,246,.25)' }
}
function routeLabel(leg: any) {
  return leg?.routeShortName || leg?.route || 'BUS'
}

/* -------- Build colored polylines (red if leg is flooded) -------- */
const BASE_COLOR = '#2563eb'      // blue
const FLOODED_COLOR = '#dc2626'   // red

async function buildColoredPolylinesFromItinerary(it: any) {
  const legs: any[] = Array.isArray(it?.legs) ? it.legs : []
  const busLegs = legs.filter(l => l?.mode === 'BUS')

  const polylines: Array<{ path: [number,number][], color: string, flooded: boolean }> = []
  const segments: Array<{ points: [number,number][], flooded: boolean }> = []

  for (const leg of busLegs) {
    // collect stop codes along this leg
    const codes: string[] = []
    const a = leg?.from?.stopCode
    const b = leg?.to?.stopCode
    if (a) codes.push(String(a))
    const interm = Array.isArray(leg?.intermediateStops) ? leg.intermediateStops : []
    for (const st of interm) {
      if (st?.stopCode) codes.push(String(st.stopCode))
    }
    if (b && (!codes.length || codes[codes.length - 1] !== String(b))) codes.push(String(b))

    // make a polyline for the whole leg
    let path: [number,number][] | undefined
    if (codes.length >= 2) {
      const osrm = await computeRoadPathForSegment(codes)
      path = osrm?.path
    }
    if (!path || path.length < 2) {
      const pts = [a, b].map((c:string)=>latLonFromCode(String(c))).filter(Boolean) as [number,number][]
      if (pts.length >= 2) path = pts
    }
    if (!path || path.length < 2) continue

    const flooded = legIsFlooded(leg)
    const color = flooded ? FLOODED_COLOR : BASE_COLOR

    polylines.push({ path, color, flooded })
    segments.push({ points: path, flooded })
  }

  // Build a combined unique stop sequence for info box
  const stopCodes: string[] = []
  for (const leg of busLegs) {
    const a = leg?.from?.stopCode
    const b = leg?.to?.stopCode
    if (a) stopCodes.push(String(a))
    if (Array.isArray(leg?.intermediateStops)) {
      for (const st of leg.intermediateStops) if (st?.stopCode) stopCodes.push(String(st.stopCode))
    }
    if (b) stopCodes.push(String(b))
  }
  const seen = new Set<string>()
  const segmentCodes = stopCodes.filter(c => !seen.has(c) && seen.add(c))
  const points: [number, number][] = segmentCodes.map(c => latLonFromCode(c)).filter(Boolean) as [number, number][]

  // NEW: merge all OSRM segments into a single roadPath
  const roadPath: [number, number][] =
    polylines.length
      ? polylines.flatMap((pl, i) => (i === 0 ? pl.path : pl.path.slice(1)))
      : []

  return { polylines, segments, stopCodes: segmentCodes, points, roadPath }
}

/** ------------ Hold all built itineraries and selection ------------ */
type BuiltItinerary = {
  duration_s: number
  transfers: number
  floodSummary: { baseline_s?: number, scenarios: {scenario:string; duration_s:number}[] }
  polylines: Array<{ path:[number,number][], color:string, flooded:boolean }>
  segments: Array<{ points:[number,number][], flooded:boolean }>
  stopCodes: string[]
  points: [number,number][]
  legs: any[]
  // NEW
  roadPath?: [number, number][]
}
const ptItins = ref<BuiltItinerary[]>([])
const selectedItinIdx = ref<number>(0)

function applyItineraryToMap(i: number) {
  const it = ptItins.value[i]
  if (!it) return
  ;(store as any).setServiceRouteOverlay?.({
    serviceNo: `OneMap PT • Option ${i+1}`,
    directions: [{
      dir: 1,
      points: it.points,
      stopCodes: it.stopCodes,
      duration_s: it.duration_s,
      floodSummary: it.floodSummary,
      segments: it.segments,
      // NEW: draw OSRM road geometry when available
      roadPath: (it.roadPath && it.roadPath.length >= 2) ? it.roadPath : undefined,
    }],
    polylines: it.polylines,
    baseColor: BASE_COLOR,
    floodedColor: FLOODED_COLOR,
  })
  ;(store as any).setColoredPolylines?.(it.polylines)
  ;(store as any).setActiveTab?.('stops')
  ;(store as any).fitToOverlayBounds?.()
}

/** ---------- OneMap PT: top-level function (now builds ALL itineraries) ---------- */
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
      time: '07:00:00',
    })

    const itins: any[] = Array.isArray(res?.plan?.itineraries) ? res.plan.itineraries : []
    if (!itins.length) {
      alert('No PT itinerary found.')
      return
    }

    // Build ALL itineraries
    const built: BuiltItinerary[] = []
    for (const it of itins) {
      const duration_s = Number(it?.duration ?? 0)
      const transfers = Number(it?.transfers ?? 0)
      const floodSummary = summarizeFloodDurations(it?.legs || [])
      const { polylines, segments, stopCodes, points, roadPath } = await buildColoredPolylinesFromItinerary(it)
      built.push({ duration_s, transfers, floodSummary, polylines, segments, stopCodes, points, legs: it?.legs || [], roadPath })
    }
    ptItins.value = built
    selectedItinIdx.value = 0
    applyItineraryToMap(0)

    ;(store as any).oneMapLegs = built[0]?.legs
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

    <!-- ====== Itinerary list (ALL options) ====== -->
    <div v-if="ptItins.length" class="mb-4">
      <div class="text-sm font-semibold mb-2">Itineraries ({{ ptItins.length }})</div>

      <div class="space-y-3">
        <div
          v-for="(it, idx) in ptItins"
          :key="'it-' + idx"
          :class="['rounded-xl border p-3 shadow-sm', selectedItinIdx === idx ? 'border-blue-400 ring-2 ring-blue-200' : 'border-gray-200']"
        >
          <div class="flex items-center gap-3">
            <div class="text-base font-semibold">Option {{ idx + 1 }}</div>
            <div class="text-sm text-gray-700">
              ~ {{ Math.round(it.duration_s / 60) }} min
              <span class="text-gray-400">•</span>
              {{ it.transfers }} transfer{{ it.transfers === 1 ? '' : 's' }}
            </div>
            <div class="ml-auto">
              <button
                class="rounded-md border px-2 py-1 text-xs"
                :class="selectedItinIdx === idx ? 'bg-blue-600 text-white border-blue-600' : 'text-gray-700 hover:bg-gray-50'"
                @click="selectedItinIdx = idx; applyItineraryToMap(idx)"
                title="Show this itinerary on the map"
              >
                {{ selectedItinIdx === idx ? 'Shown on map' : 'Show on map' }}
              </button>
            </div>
          </div>

          <!-- NEW: Route ribbon (bus legs) -->
          <div class="mt-2 flex flex-wrap items-center gap-2">
            <template v-for="(L, li) in it.legs.filter(x => x.mode==='BUS')" :key="'r-'+li">
              <span
                class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ring-1"
                :style="{ backgroundColor: legChipStyle(L).bg, color: legChipStyle(L).text, boxShadow: `0 0 0 1px ${legChipStyle(L).ring} inset` }"
                :title="legStatus(L)==='flooded' ? 'Flooded segment' : 'Clear segment'"
              >
                {{ routeLabel(L) }}
                <span v-if="li < it.legs.filter(x=>x.mode==='BUS').length-1" class="text-gray-400">→</span>
              </span>
            </template>
          </div>

          <!-- Flood timings / delays -->
          <div class="mt-2 rounded-md bg-gray-50 p-3 text-sm">
            <div class="font-medium mb-1">Travel time scenarios</div>

            <div v-if="it.floodSummary?.baseline_s !== undefined" class="text-gray-700">
              Non-flooded: ~ {{ Math.round(it.floodSummary.baseline_s / 60) }} min
            </div>

            <template v-if="it.floodSummary?.scenarios?.length">
              <ul class="mt-1 text-xs text-gray-600 space-y-0.5">
                <li
                  v-for="sc in it.floodSummary.scenarios"
                  :key="sc.scenario"
                >
                  {{ sc.scenario }}: ~ {{ Math.round(sc.duration_s / 60) }} min
                  <template v-if="it.floodSummary?.baseline_s !== undefined">
                    <span class="text-[11px] text-gray-500">
                      (Δ {{ Math.round((sc.duration_s - it.floodSummary.baseline_s) / 60) }} min)
                    </span>
                  </template>
                </li>
              </ul>
            </template>

            <div v-else class="text-xs text-gray-500">
              No travel delay
            </div>

            <!-- Legend for polyline colors -->
            <div class="mt-2 flex items-center gap-4 text-xs text-gray-600">
              <span class="inline-flex items-center gap-1">
                <span class="inline-block h-2 w-6 rounded" :style="{ backgroundColor: '#2563eb' }"></span>
                Normal
              </span>
              <span class="inline-flex items-center gap-1">
                <span class="inline-block h-2 w-6 rounded" :style="{ backgroundColor: '#dc2626' }"></span>
                Flooded segment
              </span>
            </div>
          </div>

          <!-- NEW: Stops & segments per bus leg -->
          <details class="mt-2 rounded-md bg-gray-50 p-3 open:bg-gray-100">
            <summary class="cursor-pointer select-none text-sm text-gray-700">Stops & segments</summary>

            <div class="space-y-4 mt-2">
              <div
                v-for="(L, li) in it.legs.filter(x => x.mode==='BUS')"
                :key="'legstops-'+li"
                class="rounded-md border p-2"
                :style="{ borderColor: legStatus(L)==='flooded' ? '#fecaca' : '#bfdbfe' }"
              >
                <div class="flex items-center gap-2 text-sm mb-2">
                  <span
                    class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1"
                    :style="{ backgroundColor: legChipStyle(L).bg, color: legChipStyle(L).text, boxShadow: `0 0 0 1px ${legChipStyle(L).ring} inset` }"
                  >
                    Route {{ routeLabel(L) }}
                  </span>
                  <span class="text-xs"
                        :class="legStatus(L)==='flooded' ? 'text-rose-600' : 'text-blue-600'">
                    {{ legStatus(L)==='flooded' ? 'Flooded' : 'Clear' }}
                  </span>
                </div>

                <ol class="space-y-1">
                  <li
                    v-for="(code, si) in legStops(L)"
                    :key="code + '-' + si"
                    class="flex items-center gap-2 text-sm"
                  >
                    <span
                      class="inline-flex h-5 w-5 items-center justify-center rounded-full text-white text-[11px]"
                      :style="{ backgroundColor: legStatus(L)==='flooded' ? '#dc2626' : '#2563eb' }"
                    >
                      {{ si + 1 }}
                    </span>
                    <span class="truncate">{{ stopIndexByCode[code]?.name || 'Stop' }}</span>
                    <span class="text-xs text-gray-500">({{ code }})</span>
                  </li>
                </ol>
              </div>
            </div>
          </details>
        </div>
      </div>
    </div>

    <!-- ====== Selected stop detail + arrivals (unchanged) ====== -->
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
                  Selected route
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

              <!-- Flood timings / delays for the SELECTED itinerary -->
              <div class="mt-2 rounded-md bg-gray-50 p-3 text-sm">
                <div class="font-medium mb-1">Travel time scenarios</div>

                <div v-if="d.floodSummary?.baseline_s !== undefined" class="text-gray-700">
                  Non-flooded: ~ {{ Math.round(d.floodSummary.baseline_s / 60) }} min
                </div>

                <template v-if="d.floodSummary?.scenarios?.length">
                  <ul class="mt-1 text-xs text-gray-600 space-y-0.5">
                    <li
                      v-for="sc in d.floodSummary.scenarios"
                      :key="sc.scenario"
                    >
                      {{ sc.scenario }}: ~ {{ Math.round(sc.duration_s / 60) }} min
                      <template v-if="d.floodSummary?.baseline_s !== undefined">
                        <span class="text-[11px] text-gray-500">
                          (Δ {{ Math.round((sc.duration_s - d.floodSummary.baseline_s) / 60) }} min)
                        </span>
                      </template>
                    </li>
                  </ul>
                </template>

                <div v-else class="text-xs text-gray-500">
                  No travel delay
                </div>

                <!-- Legend for polyline colors -->
                <div class="mt-2 flex items-center gap-4 text-xs text-gray-600">
                  <span class="inline-flex items-center gap-1">
                    <span class="inline-block h-2 w-6 rounded" :style="{ backgroundColor: (store as any).serviceRouteOverlay?.baseColor || '#2563eb' }"></span>
                    Normal
                  </span>
                  <span class="inline-flex items-center gap-1">
                    <span class="inline-block h-2 w-6 rounded" :style="{ backgroundColor: (store as any).serviceRouteOverlay?.floodedColor || '#dc2626' }"></span>
                    Flooded segment
                  </span>
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
                  ETA: {{ Math.round((svc.next?.duration_ms ?? 0) / 60000) }} min
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

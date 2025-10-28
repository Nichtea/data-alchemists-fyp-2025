<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import * as L from 'leaflet'
import proj4 from 'proj4'
import {
  getAllFloodEvents,
  getFloodEventById,
  getFloodLocations,
  getFloodEventsByDateRange,
  getCriticalSegmentsNearFlood,
  type CriticalSegmentsNearFloodResponse
} from '@/api/api'

type Tab = 'locations' | 'critical'
const activeTab = ref<Tab>('locations')

/* ─────────── EPSG:3414 (SVY21) → WGS84 ─────────── */
proj4.defs(
  'EPSG:3414',
  '+proj=tmerc +lat_0=1.36666666666667 +lon_0=103.833333333333 +k=1 +x_0=28001.642 +y_0=38744.572 +ellps=WGS84 +units=m +no_defs'
)
const toWGS84 = (x: number, y: number): [number, number] => {
  const [lon, lat] = proj4('EPSG:3414', 'WGS84', [x, y]) as [number, number]
  return [lat, lon]
}

/* ─────────── Types ─────────── */
type FloodRow = { location: string; count: number; time_travel_delay_min?: number }

/* ─────────── Map refs ─────────── */
const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map
let markersLayer: L.LayerGroup | null = null
let segmentLayer: L.LayerGroup | null = null
let criticalLayer: L.LayerGroup | null = null
let highlighted: L.Polyline | null = null
let drawEpoch = 0

/* ─────────── Data ─────────── */
const eventsMaster    = ref<any[]>([])  // all events (never filtered) — used by Critical tab
const eventsLocations = ref<any[]>([])  // Locations tab working set (may be date-filtered)

const locationsMasterAgg = ref<FloodRow[]>([]) // pristine aggregation from API (has delay)
const floodLocations     = ref<FloodRow[]>([]) // current list shown in Locations tab

const loadingLocations = ref(true)
const loadingEvents    = ref(true)

/* ─────────── Date filter (Locations tab ONLY) ─────────── */
const startDate = ref<string>('')
const endDate   = ref<string>('')
const filteringByDate = ref(false)

const lastAppliedRange = computed(() =>
  filteringByDate.value && startDate.value && endDate.value
    ? `${startDate.value} → ${endDate.value}`
    : ''
)

function isValidDateStr(s: string) { return /^\d{4}-\d{2}-\d{2}$/.test(s) }

function buildLocationCounts(events: any[]): FloodRow[] {
  const byLoc = new Map<string, FloodRow>()
  for (const e of events) {
    const name =
      e.flooded_location ?? e.name ?? e.location ?? e.site ?? e.place ?? ''
    if (!name) continue
    const cur = byLoc.get(name) || { location: String(name), count: 0, time_travel_delay_min: undefined }
    cur.count += 1
    // Try several possible delay fields from event payloads
    const d = Number(
      e.time_travel_delay_min ?? e.delay_min ?? e.delay ?? e.travel_delay_min
    )
    if (Number.isFinite(d)) {
      cur.time_travel_delay_min = Math.max(cur.time_travel_delay_min ?? -Infinity, d)
    }
    byLoc.set(name, cur)
  }
  return [...byLoc.values()]
}

async function applyDateFilter() {
  if (!isValidDateStr(startDate.value) || !isValidDateStr(endDate.value)) {
    alert('Please enter dates as YYYY-MM-DD.')
    return
  }
  loadingLocations.value = true
  filteringByDate.value = true
  try {
    const rangeEvents = await getFloodEventsByDateRange({
      start_date: startDate.value, end_date: endDate.value
    }) as any[]
    eventsLocations.value = Array.isArray(rangeEvents) ? rangeEvents : []
    // For filtered mode we derive the aggregation from events (may lack delay → show "—" gracefully)
    floodLocations.value = buildLocationCounts(eventsLocations.value)
    if (activeTab.value === 'locations') rerenderMarkersForActiveTab()
    clearSegments(); clearCritical()
  } catch (e) {
    console.error(e); alert('Failed to fetch events for date range.')
  } finally {
    loadingLocations.value = false
  }
}

async function clearDateFilter() {
  startDate.value = ''; endDate.value = ''
  filteringByDate.value = false
  loadingLocations.value = true
  try {
    // Restore Locations dataset and aggregation to the master (which contains delays)
    eventsLocations.value = eventsMaster.value.slice()
    floodLocations.value  = locationsMasterAgg.value.slice()
    if (activeTab.value === 'locations') rerenderMarkersForActiveTab()
    clearSegments(); clearCritical()
  } finally {
    loadingLocations.value = false
  }
}

/* ─────────── Locations tab filters ─────────── */
const q = ref(''); const minCount = ref(1)
const sortBy = ref<'count' | 'name' | 'delay'>('count')
const sortDir = ref<'desc' | 'asc'>('desc')
const topN = ref(10)

const filteredLocations = computed(() => {
  const query = q.value.trim().toLowerCase()
  let rows = floodLocations.value
  if (query) rows = rows.filter(r => (r.location || '').toLowerCase().includes(query))
  rows = rows.filter(r => (r.count ?? 0) >= (minCount.value || 0))
  rows = [...rows].sort((a, b) => {
    if (sortBy.value === 'count') return sortDir.value === 'desc' ? b.count - a.count : a.count - b.count
    if (sortBy.value === 'delay') {
      const A = Number.isFinite(a.time_travel_delay_min as number) ? (a.time_travel_delay_min as number) : -Infinity
      const B = Number.isFinite(b.time_travel_delay_min as number) ? (b.time_travel_delay_min as number) : -Infinity
      return sortDir.value === 'desc' ? B - A : A - B
    }
    const A = (a.location || '').toLowerCase(), B = (b.location || '').toLowerCase()
    const cmp = A === B ? 0 : (A > B ? 1 : -1)
    return sortDir.value === 'desc' ? -cmp : cmp
  })
  return rows.slice(0, Math.max(1, Number(topN.value) || 0))
})

function resetFilters() {
  q.value=''; minCount.value=1; sortBy.value='count'; sortDir.value='desc'; topN.value=20
}

/* ─────────── Critical tab state ─────────── */
const bufferM  = ref<number>(50)
const errorMsg = ref<string | null>(null)
const infoMsg  = ref<string | null>(null)
const selectedFloodId = ref<number | null>(null)
const lastPayload = ref<CriticalSegmentsNearFloodResponse | null>(null)

/* Flood list in Critical tab ALWAYS from eventsMaster */
const qEvents = ref(''); const topEvents = ref(500)
const filteredEvents = computed(() => {
  const query = qEvents.value.trim().toLowerCase()
  const rows = eventsMaster.value
  const filtered = query ? rows.filter(e => (e.flooded_location || e.name || '').toLowerCase().includes(query)) : rows
  return filtered.slice(0, Math.max(1, Number(topEvents.value) || 0))
})

/* ─────────── Detail cache ─────────── */
const detailCache = new Map<number, any>()
const detailPromise = new Map<number, Promise<any>>()
async function getDetailCached(id: number) {
  if (detailCache.has(id)) return detailCache.get(id)
  if (detailPromise.has(id)) return detailPromise.get(id)!
  const p = (async () => {
    const raw = await getFloodEventById(Number(id))
    const detail = Array.isArray(raw) ? raw[0] ?? raw : raw
    detailCache.set(id, detail); detailPromise.delete(id); return detail
  })().catch(e => { detailPromise.delete(id); throw e })
  detailPromise.set(id, p); return p
}

/* ─────────── Tooltip helpers ─────────── */
const fmt = {
  min: (n: any) => Number.isFinite(+n) ? `${(+n).toFixed(2)} min` : '—',
  km:  (m: any) => Number.isFinite(+m) ? `${(+m/1000).toFixed(3)} km` : '—',
  date: (s: any) => { if (!s) return '—'; try { return new Date(s).toLocaleString() } catch { return String(s) } }
}
function buildFloodTooltip(detail: any, fallback: { id?: any, name?: string } = {}) {
  const id = detail?.id ?? detail?.flood_id ?? fallback?.id ?? '—'
  const loc = detail?.flooded_location ?? detail?.name ?? fallback?.name ?? 'Flood event'
  const startedAt = detail?.started_at ?? detail?.start_time ?? detail?.timestamp
  const roadName = (typeof detail?.road_name === 'string' && detail.road_name.trim()) ? detail.road_name : 'Unnamed Road'
  const roadType = detail?.road_type ?? '—'
  const lenM = Number(detail?.length_m)
  const t20 = Number(detail?.time_20kmh_min)
  const t50 = Number(detail?.time_50kmh_min)
  const delay = Number(detail?.time_travel_delay_min ?? detail?.delay_min ?? detail?.delay)
  return `
    <div class="flood-tt">
      <div class="tt-title">Flood details</div>
      <div class="tt-subtle">ID: ${id}</div>
      <div class="tt-section">Location</div>
      <table class="tt-table"><tr><th>Name</th><td>${loc}</td></tr><tr><th>Start</th><td>${fmt.date(startedAt)}</td></tr></table>
      <div class="tt-section">Road segment</div>
      <table class="tt-table"><tr><th>Road name</th><td>${roadName}</td></tr><tr><th>Type</th><td>${roadType}</td></tr><tr><th>Length</th><td>${fmt.km(lenM)}</td></tr></table>
      <div class="tt-section">Traffic impact</div>
      <table class="tt-table"><tr><th>Time @ 20 km/h</th><td>${fmt.min(t20)}</td></tr><tr><th>Time @ 50 km/h</th><td>${fmt.min(t50)}</td></tr><tr><th>Travel delay</th><td>${fmt.min(delay)}</td></tr></table>
    </div>`
}

/* ─────────── Geometry helpers ─────────── */
function wktToLatLngs(wkt: string): [number, number][][] {
  const s = (wkt || '').trim(); if (!s) return []
  const upper = s.toUpperCase(); const isMulti = upper.startsWith('MULTILINESTRING')
  const extractLine = (inner: string) => {
    const pairs = inner.split(',').map(p => p.trim()).filter(Boolean)
    const latlngs: [number, number][] = []
    for (const pair of pairs) {
      const [xStr, yStr] = pair.split(/\s+/).filter(Boolean)
      const lon = Number(xStr), lat = Number(yStr)
      if (isFinite(lat) && isFinite(lon)) latlngs.push([lat, lon])
    } return latlngs
  }
  if (isMulti) {
    const groups = s.slice(s.indexOf('(')).match(/\(([^()]+)\)/g); if (!groups) return []
    return groups.map(g => g.replace(/^\(|\)$/g, '')).map(extractLine).filter(a => a.length > 0)
  } else {
    const start = s.indexOf('('), end = s.lastIndexOf(')'); if (start < 0 || end < 0 || end <= start) return []
    const arr = extractLine(s.substring(start + 1, end)); return arr.length ? [arr] : []
  }
}
function clearSegments() { if (segmentLayer) { map.removeLayer(segmentLayer); segmentLayer = null } }
function clearCritical() { if (criticalLayer) { map.removeLayer(criticalLayer); criticalLayer = null } if (highlighted) { map.removeLayer(highlighted); highlighted = null } }

/* ─────────── Map + markers ─────────── */
function ensureMap() {
  if (map) return
  const token = import.meta.env.VITE_MAPBOX_TOKEN
  const styleId = 'mapbox/streets-v12'
  map = L.map(mapEl.value as HTMLDivElement, { center: [1.3521, 103.8198], zoom: 12, zoomControl: true })
  const url = `https://api.mapbox.com/styles/v1/${styleId}/tiles/512/{z}/{x}/{y}@2x?access_token=${token}`
  L.tileLayer(url, { tileSize: 512, zoomOffset: -1, maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors &copy; <a href="https://www.mapbox.com/">Mapbox</a>' }).addTo(map)
}

function makeFloodIcon(selected: boolean) {
  const fill = selected ? '#dc2626' : '#2563eb'
  const stroke = selected ? '#991b1b' : '#1e3a8a'
  const svg = `<svg viewBox="0 0 32 40" width="32" height="40" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M16 0C8.28 0 2 6.28 2 14c0 8.28 9.1 18.22 13.08 22.07a1.5 1.5 0 0 0 2.06 0C20.1 32.22 30 22.28 30 14 30 6.28 23.72 0 16 0z" fill="${fill}" stroke="${stroke}" stroke-width="2" />
    <circle cx="16" cy="14" r="5.2" fill="white"/></svg>`
  return L.divIcon({ className: 'flood-pin', html: svg, iconSize: [32, 40], iconAnchor: [16, 40], popupAnchor: [0, -36], tooltipAnchor: [0, -36] })
}
const groupByLocation = new Map<string, L.LayerGroup>()

function baseMarkerForEvent(e: any, isSelected: boolean) {
  const name: string = e.flooded_location || e.name || ''
  const lat = e.latitude ?? e.lat ?? e.center_lat
  const lon = e.longitude ?? e.lon ?? e.center_lon ?? e.lng
  if (!Number.isFinite(+lat) || !Number.isFinite(+lon)) return null
  const id = Number(e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id)
  const marker = L.marker([+lat, +lon], { icon: makeFloodIcon(isSelected) })
    .bindTooltip(`<div class="flood-tt"><div class="tt-title">${name || 'Flood event'}</div><div class="tt-subtle">ID: ${id || '—'}</div></div>`,
      { sticky: true, direction: 'top', opacity: 0.95, className: 'flood-tooltip' })
    .on('mouseover', async (ev: L.LeafletMouseEvent) => {
      if (!Number.isFinite(id)) return
      const tt = (marker as any).getTooltip?.(); tt?.setContent(`<div class="flood-tt">Loading…</div>`); (marker as any).openTooltip?.(ev.latlng)
      try { const detail = await getDetailCached(id); tt?.setContent(buildFloodTooltip(detail, { id, name })); (marker as any).openTooltip?.(ev.latlng) }
      catch { tt?.setContent(`<div class="flood-tt">Failed to load details</div>`) }
    })
    .on('click', () => { onSelectFloodRow(e); activeTab.value = 'critical' })
  return { marker, lat, lon, name, id }
}

/* Helper: normalize strings for matching between sources */
function norm(s: any) {
  return String(s ?? '').trim().toLowerCase()
}

/* Choose dataset by tab:
   - Locations: eventsLocations
   - Critical : eventsMaster (and filtered by qEvents)
*/
function rerenderMarkersForActiveTab() {
  if (!map) return
  if (markersLayer) { map.removeLayer(markersLayer); markersLayer = null }
  markersLayer = L.layerGroup().addTo(map)
  groupByLocation.clear()
  const bounds = L.latLngBounds([])

  const usingLocations = activeTab.value === 'locations'
  const data = usingLocations ? eventsLocations.value : eventsMaster.value

  const nameSet = new Set<string>(
    usingLocations
      ? filteredLocations.value.map(r => r.location)
      : filteredEvents.value.map(e => (e.flooded_location || e.name || ''))
  )

  for (const e of data) {
    const name: string = e.flooded_location || e.name || e.location || e.site || e.place || ''
    if (!name || !nameSet.has(name)) continue
    const id = Number(e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id)
    const isSelected = selectedFloodId.value === id
    const built = baseMarkerForEvent(e, isSelected); if (!built) continue
    const { marker, lat, lon } = built
    markersLayer.addLayer(marker); bounds.extend([+lat, +lon])
    if (!groupByLocation.has(name)) groupByLocation.set(name, L.layerGroup())
    groupByLocation.get(name)!.addLayer(marker)
  }
  if (bounds.isValid()) map.fitBounds(bounds.pad(0.12))
}

/* Locations → draw flooded segments for a clicked row */
async function focusLocation(name: string) {
  if (!map) return
  const myEpoch = ++drawEpoch
  clearSegments(); clearCritical()
  segmentLayer = L.layerGroup().addTo(map)

  // Use the correct event set (filtered vs full)
  const pool = filteringByDate.value ? eventsLocations.value : eventsMaster.value

  // Robust match across several likely fields
  const targetKey = norm(name)
  const evts = pool.filter(e => {
    return [e.flooded_location, e.name, e.location, e.site, e.place]
      .some(v => norm(v) === targetKey)
  })

  if (!evts.length) return

  const bounds = L.latLngBounds([])
  const style: L.PathOptions = { color: '#1d4ed8', weight: 6, opacity: 0.92, dashArray: '8,6' }

  for (const e of evts) {
    if (myEpoch !== drawEpoch) return
    const id = e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id
    try {
      const detail = id != null ? await getDetailCached(Number(id)) : e
      if (myEpoch !== drawEpoch) return
      drawDetailGeometry(detail, style, bounds)
    } catch { /* ignore */ }
  }

  if (bounds.isValid()) {
    map.fitBounds(bounds.pad(0.15))
  } else {
    const g = groupByLocation.get(name)
    if (g) {
      const b = L.latLngBounds([])
      g.eachLayer((lyr: any) => { if (lyr.getLatLng) b.extend(lyr.getLatLng()) })
      if (b.isValid()) map.fitBounds(b.pad(0.2))
    }
  }
}

/* ─────────── Draw helpers ─────────── */
function drawDetailGeometry(detail: any, style: L.PathOptions, boundsAcc: L.LatLngBounds) {
  if (typeof detail?.geometry === 'string' && detail.geometry.trim()) {
    const groups = wktToLatLngs(detail.geometry)
    for (const latlngs of groups) {
      const poly = L.polyline(latlngs, style)
      ;(segmentLayer as L.LayerGroup).addLayer(poly)
      latlngs.forEach(([lat, lon]) => boundsAcc.extend([lat, lon]))
    }
    return
  }
  if (detail?.geom && typeof detail.geom === 'object') {
    const gj = L.geoJSON(detail.geom as any, { style: () => style })
    ;(segmentLayer as L.LayerGroup).addLayer(gj)
    try {
      const gjBounds = (gj as any).getBounds?.()
      if (gjBounds && gjBounds.isValid()) boundsAcc.extend(gjBounds)
    } catch {}
  }
}

/* ─────────── Critical segments (unchanged logic; minor tweaks) ─────────── */
function onSelectFloodRow(e: any) {
  const id = Number(e?.flood_id ?? e?.id ?? e?.flood_event_id ?? e?.event_id)
  if (!Number.isFinite(id) || id <= 0) { errorMsg.value = 'Invalid flood id.'; return }
  selectedFloodId.value = id
  lastPayload.value = null; infoMsg.value = null
  rerenderMarkersForActiveTab()
  fetchAndDrawCritical(id)
}

async function fetchAndDrawCritical(fid: number) {
  clearCritical(); errorMsg.value = null; infoMsg.value = null
  if (!Number.isFinite(fid) || fid <= 0) { errorMsg.value = 'Select a valid flood event (flood_id > 0).'; return }
  const buf = Math.max(1, Number(bufferM.value || 50))
  try {
    const payload = await getCriticalSegmentsNearFlood({ flood_id: fid, buffer_m: buf }) as (CriticalSegmentsNearFloodResponse & { message?: string })
    if (payload && typeof (payload as any).message === 'string') {
      lastPayload.value = { ...(payload as any), critical_segments: [], buffer_m: buf } as any
      infoMsg.value = (payload as any).message || 'No critical roads near flood.'
      drawOnlyFloodPoint(fid); return
    }
    lastPayload.value = payload; drawCritical(payload)
  } catch (e: any) {
    console.error(e); errorMsg.value = e?.message || 'Failed to fetch critical segments.'
  }
}

function drawOnlyFloodPoint(fid: number) {
  clearCritical(); criticalLayer = L.layerGroup().addTo(map)
  const evt = eventsMaster.value.find(e => Number(e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id) === Number(fid))
  const lat = evt?.latitude ?? evt?.lat ?? evt?.center_lat
  const lon = evt?.longitude ?? evt?.lon ?? evt?.center_lon ?? evt?.lng
  if (!Number.isFinite(+lat) || !Number.isFinite(+lon)) return
  const m = L.circleMarker([+lat, +lon], { radius: 5, color: '#991b1b', weight: 2, fillColor: '#ef4444', fillOpacity: 0.9, interactive: false })
  criticalLayer.addLayer(m); map.fitBounds(L.latLngBounds([[+lat, +lon]]).pad(0.25))
}

function drawCritical(p: CriticalSegmentsNearFloodResponse) {
  clearCritical(); criticalLayer = L.layerGroup().addTo(map)
  const bounds = L.latLngBounds([])
  const fp = (p as any).flood_point
  if (fp?.type === 'Point' && Array.isArray(fp.coordinates) && fp.coordinates.length === 2) {
    const [lon, lat] = fp.coordinates
    const m = L.circleMarker([lat, lon], { radius: 5, color: '#991b1b', weight: 2, fillColor: '#ef4444', fillOpacity: 0.9, interactive: false })
    criticalLayer.addLayer(m); bounds.extend([lat, lon])
  }
  for (const seg of (p as any).critical_segments || []) {
    const coords: [number, number][] = seg?.geometry?.coordinates || []
    const latlngs: [number, number][] = []
    for (const [x, y] of coords) { const [lat, lon] = toWGS84(x, y); latlngs.push([lat, lon]); bounds.extend([lat, lon]) }
    if (!latlngs.length) continue
    const safeName = (typeof seg.road_name === 'string' && seg.road_name.trim()) ? seg.road_name : 'Unnamed Road'
    const poly = L.polyline(latlngs, { color: '#dc2626', weight: 6, opacity: 0.95, dashArray: '4,6' })
      .bindTooltip(`
        <div class="flood-tt">
          <div class="tt-title">${safeName}</div>
          <div class="tt-subtle">${seg.road_type || '—'}</div>
          <table class="tt-table" style="margin-top:6px;">
            <tr><th>Length</th><td>${Number(seg.length_m).toFixed(2)} m</td></tr>
            <tr><th>Centrality</th><td>${Number(seg.centrality_score).toFixed(6)}</td></tr>
            <tr><th>Buffer</th><td>${(p as any).buffer_m} m</td></tr>
          </table>
        </div>`, { sticky: true, direction: 'top', opacity: 0.95, className: 'flood-tooltip' })
    ;(poly as any).__meta = { seg }; criticalLayer.addLayer(poly)
  }
  if (bounds.isValid()) map.fitBounds(bounds.pad(0.12))
}

function highlightSegmentAt(idx: number) {
  if (!criticalLayer) return
  if (highlighted) { map.removeLayer(highlighted); highlighted = null }
  let i = 0; let target: L.Polyline | null = null
  criticalLayer.eachLayer((l: any) => { if (l instanceof L.Polyline) { if (i === idx) target = l; i++ } })
  if (target) {
    const latlngs = (target as any).getLatLngs?.() as L.LatLng[] | L.LatLng[][]
    const flat = Array.isArray(latlngs?.[0]) ? (latlngs as L.LatLng[][]).flat() : (latlngs as L.LatLng[])
    if (flat?.length) { highlighted = L.polyline(flat, { color: '#7c3aed', weight: 7, opacity: 0.95 }).addTo(map)
      map.fitBounds(L.latLngBounds(flat as any).pad(0.2)) }
  }
}

/* ─────────── Reactive hooks ─────────── */
watch([filteredLocations, filteredEvents, activeTab], () => { rerenderMarkersForActiveTab() })

let bufTimer: number | undefined
watch(bufferM, () => {
  if (!selectedFloodId.value) return
  window.clearTimeout(bufTimer)
  bufTimer = window.setTimeout(() => fetchAndDrawCritical(selectedFloodId.value!), 400)
})

watch(activeTab, () => {
  // hard cleanup on tab switch
  clearCritical(); clearSegments()
  selectedFloodId.value = null
  lastPayload.value = null
  infoMsg.value = null
  rerenderMarkersForActiveTab()
})

/* ─────────── lifecycle ─────────── */
onMounted(async () => {
  ensureMap()
  try {
    const [events, locations] = await Promise.all([
      getAllFloodEvents().catch(() => []),
      getFloodLocations().catch(() => []),
    ])

    // Master events (Critical tab dataset)
    eventsMaster.value = Array.isArray(events) ? events : []

    // Locations tab starts with full master events …
    eventsLocations.value = eventsMaster.value.slice()

    // … but list/aggregation comes from the locations API (has delay)
    locationsMasterAgg.value = (Array.isArray(locations) ? locations : []).map((r: any) => ({
      location: String(r.location),
      count: Number(r.count) || 0,
      time_travel_delay_min: Number(r.time_travel_delay_min),
    }))
    floodLocations.value = locationsMasterAgg.value.slice()
  } finally {
    loadingLocations.value = false
    loadingEvents.value    = false
    await nextTick(); rerenderMarkersForActiveTab()
  }

  // deep links (?flood_id=&buffer_m=)
  const qs = new URLSearchParams(window.location.search)
  const fid = Number(qs.get('flood_id'))
  const buf = Number(qs.get('buffer_m'))
  if (Number.isFinite(buf) && buf >= 1) bufferM.value = buf
  if (Number.isFinite(fid) && fid > 0) {
    selectedFloodId.value = fid
    activeTab.value = 'critical'
    await nextTick()
    rerenderMarkersForActiveTab()
    fetchAndDrawCritical(fid)
  }
})
</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-4">
    <!-- LEFT: tabbed sidebar -->
    <aside class="col-span-4 space-y-3">
      <div class="bg-white rounded shadow">
        <div class="flex">
          <button
            class="flex-1 px-4 py-2 text-sm font-medium border-b"
            :class="activeTab==='locations' ? 'text-blue-700 border-blue-600' : 'text-gray-600 border-transparent'"
            @click="activeTab='locations'">Locations</button>
          <button
            class="flex-1 px-4 py-2 text-sm font-medium border-b"
            :class="activeTab==='critical' ? 'text-blue-700 border-blue-600' : 'text-gray-600 border-transparent'"
            @click="activeTab='critical'">Critical Roads</button>
        </div>
      </div>

      <!-- LOCATIONS TAB -->
      <div v-if="activeTab==='locations'" class="space-y-4">
        <div class="bg-white rounded shadow p-2">
          <div class="text-sm font-semibold">Flood-Prone Locations</div>
          <div class="text-xs text-gray-500">
            <span v-if="!filteringByDate">Showing top {{ topN }}</span>
            <span v-else>Date range: {{ lastAppliedRange }}</span>
          </div>
        </div>

        <!-- Date filter -->
        <div class="bg-white rounded shadow p-3 space-y-2">
          <div class="grid grid-cols-2 gap-2 items-center">
            <label class="text-xs text-gray-600">Start date</label>
            <input v-model="startDate" type="date" class="px-2 py-1 border rounded text-sm" />
            <label class="text-xs text-gray-600">End date</label>
            <input v-model="endDate" type="date" class="px-2 py-1 border rounded text-sm" />
          </div>
          <div class="flex gap-2">
            <button class="px-2 py-1 border rounded hover:bg-gray-50" @click="applyDateFilter">Apply</button>
            <button class="px-2 py-1 border rounded hover:bg-gray-50" @click="clearDateFilter" :disabled="!filteringByDate">Clear</button>
          </div>
          <div class="text-xs text-gray-500" v-if="filteringByDate">Filtering by server-side date range.</div>
        </div>

        <!-- Location Filters -->
        <div class="bg-white rounded shadow p-3 space-y-3">
          <input v-model="q" type="text" placeholder="Search location…" class="w-full px-2 py-1 border rounded text-sm" />
          <div class="grid grid-cols-2 gap-2">
            <div class="flex items-center gap-2">
              <label class="text-xs text-gray-600 whitespace-nowrap">Min count</label>
              <input v-model.number="minCount" type="number" min="0" class="w-20 px-2 py-1 border rounded text-sm" />
            </div>
            <div class="flex items-center gap-2">
              <label class="text-xs text-gray-600 whitespace-nowrap">Top N</label>
              <input v-model.number="topN" type="number" min="1" class="w-20 px-2 py-1 border rounded text-sm" />
            </div>
            <div class="flex items-center gap-2">
              <label class="text-xs text-gray-600">Sort by</label>
              <select v-model="sortBy" class="px-2 py-1 border rounded text-sm">
                <option value="count">Count</option>
                <option value="name">Name</option>
                <option value="delay">Delay</option>
              </select>
            </div>
            <div class="flex items-center gap-2">
              <label class="text-xs text-gray-600">Direction</label>
              <select v-model="sortDir" class="px-2 py-1 border rounded text-sm">
                <option value="desc">Desc</option>
                <option value="asc">Asc</option>
              </select>
            </div>
          </div>
          <div class="flex items-center justify-between text-xs text-gray-500">
            <span>Matches: {{ filteredLocations.length }}</span>
            <button class="px-2 py-1 border rounded hover:bg-gray-50" @click="resetFilters">Reset</button>
          </div>
        </div>

        <!-- Location Results -->
        <div class="bg-white rounded shadow p-3">
          <div v-if="loadingLocations" class="text-gray-500 text-sm">Loading…</div>
          <div v-else-if="!floodLocations.length" class="text-gray-500 text-sm">No flood data available.</div>
          <div v-else class="overflow-x-auto">
            <table class="min-w-full text-sm border">
              <thead class="bg-gray-100 text-gray-700">
                <tr>
                  <th class="px-2 py-1 text-left border">Location</th>
                  <th class="px-2 py-1 text-right border">Count</th>
                  <th class="px-2 py-1 text-right border">Time Travel Delay (min)</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="loc in filteredLocations" :key="loc.location"
                    class="hover:bg-gray-50 cursor-pointer"
                    @click="focusLocation(loc.location)"
                    title="Draw flooded segments & zoom to this location">
                  <td class="px-2 py-1 border">{{ loc.location }}</td>
                  <td class="px-2 py-1 border text-right">{{ loc.count }}</td>
                  <td class="px-2 py-1 border text-right">
                    {{ Number.isFinite(loc.time_travel_delay_min)
                        ? (loc.time_travel_delay_min as number).toFixed(2)
                        : '—' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- CRITICAL TAB -->
      <div v-else class="space-y-4">
        <div class="bg-white rounded shadow p-3 space-y-3">
          <div class="text-sm font-semibold">Critical Roads Near Flood</div>
          <div class="grid grid-cols-2 gap-2">
            <label class="text-xs text-gray-600 self-center">Buffer (m)</label>
            <input v-model.number="bufferM" type="number" min="1" step="1" class="px-2 py-1 border rounded text-sm" />
            <label class="text-xs text-gray-600 self-center">Filter events</label>
            <input v-model="qEvents" type="text" placeholder="e.g. Yishun" class="px-2 py-1 border rounded text-sm" />
          </div>
          <div class="text-xs text-gray-600">
            <div>Events loaded: <span class="font-medium">{{ eventsMaster.length }}</span></div>
            <div>Showing: <span class="font-medium">{{ filteredEvents.length }}</span></div>
            <div v-if="lastPayload">Selected Flood: <span class="font-medium">{{ (lastPayload as any).flood_id }}</span> • Segments: <span class="font-medium">{{ (lastPayload as any).count_critical_segments }}</span></div>
          </div>
          <div v-if="errorMsg" class="text-xs text-red-600">{{ errorMsg }}</div>
        </div>

        <div class="bg-white rounded shadow p-3">
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm font-semibold">Flood Events</div>
            <div class="text-xs text-gray-500">Click a row to draw critical segments</div>
          </div>

          <div v-if="loadingEvents" class="text-gray-500 text-sm">Loading…</div>
          <div v-else-if="!eventsMaster.length" class="text-gray-500 text-sm">No flood events.</div>

          <div v-else class="max-h-[40vh] overflow-auto">
            <table class="min-w-full text-sm border">
              <thead class="bg-gray-100 text-gray-700 sticky top-0">
                <tr>
                  <th class="px-2 py-1 border text-left">Location</th>
                  <th class="px-2 py-1 border text-right">ID</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="e in filteredEvents"
                    :key="e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id"
                    class="hover:bg-gray-50 cursor-pointer"
                    @click="onSelectFloodRow(e)"
                    :title="`Zoom & draw critical segments for Flood ${e.flood_id ?? e.id}`">
                  <td class="px-2 py-1 border">{{ e.flooded_location || e.name || 'Flood event' }}</td>
                  <td class="px-2 py-1 border text-right">{{ e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Critical Segments card -->
        <div v-if="selectedFloodId !== null" class="bg-white rounded shadow p-3">
          <div class="flex items-center justify-between mb-2">
            <div class="text-sm font-semibold">Critical Segments</div>
            <div class="text-xs text-gray-500">Click a row to zoom</div>
          </div>

          <div v-if="lastPayload && !(lastPayload as any).critical_segments?.length"
               class="text-sm text-amber-700">
            {{ infoMsg || 'No critical roads near flood.' }}
          </div>

          <div v-else-if="lastPayload && (lastPayload as any).critical_segments?.length" class="max-h-[40vh] overflow-auto">
            <table class="min-w-full text-sm border">
              <thead class="bg-gray-100 text-gray-700 sticky top-0">
                <tr>
                  <th class="px-2 py-1 border text-left">Road</th>
                  <th class="px-2 py-1 border text-left">Type</th>
                  <th class="px-2 py-1 border text-right">Len (m)</th>
                  <th class="px-2 py-1 border text-right">Centrality</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(seg, idx) in (lastPayload as any).critical_segments"
                    :key="idx"
                    class="hover:bg-gray-50 cursor-pointer"
                    @click="highlightSegmentAt(idx)">
                  <td class="px-2 py-1 border">{{ (typeof seg.road_name === 'string' && seg.road_name.trim()) ? seg.road_name : 'Unnamed Road' }}</td>
                  <td class="px-2 py-1 border">{{ seg.road_type || '—' }}</td>
                  <td class="px-2 py-1 border text-right">{{ Number(seg.length_m).toFixed(2) }}</td>
                  <td class="px-2 py-1 border text-right">{{ Number(seg.centrality_score).toFixed(6) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else class="text-sm text-gray-500">Select a flood event to see critical segments.</div>
        </div>
      </div>
    </aside>

    <!-- RIGHT: map -->
    <main class="col-span-8">
      <div class="bg-white rounded shadow h-[calc(100vh-2.5rem)] p-2">
        <div ref="mapEl" class="w-full h-full"></div>
      </div>
    </main>
  </div>
</template>

<style>
.flood-tooltip { padding: 0 !important; border: 0; background: transparent; box-shadow: none; }
.flood-tt {
  background:#fff; border:1px solid #e5e7eb; border-radius:8px;
  box-shadow:0 8px 24px rgba(0,0,0,.12); padding:10px 12px;
  font:12px/1.35 system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial,sans-serif;
  color:#111827; max-width:260px;
}
.flood-tt .tt-title { font-weight:600; margin-bottom:2px; }
.flood-tt .tt-subtle { color:#6b7280; font-size:11px; margin-bottom:8px; }
.flood-tt .tt-section { margin-top:8px; font-weight:600; color:#374151; }
.flood-tt .tt-table { width:100%; border-collapse:collapse; margin-top:4px; }
.flood-tt .tt-table th, .flood-tt .tt-table td { border:1px solid #e5e7eb; padding:4px 6px; vertical-align:top; font-size:12px; }
.flood-tt .tt-table th { width:48%; background:#f9fafb; color:#374151; font-weight:600; }
.leaflet-marker-icon.flood-pin { filter: drop-shadow(0 2px 6px rgba(0,0,0,.25)); }
</style>

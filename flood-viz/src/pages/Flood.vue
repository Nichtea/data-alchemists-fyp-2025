<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import * as L from 'leaflet'
import {
  getAllFloodEvents,
  getFloodEventById,
  getFloodLocations,
  getFloodEventsByDateRange, // ⬅️ NEW
} from '@/api/api'

/* ===================== Map refs ===================== */
const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map
let visibleLayer: L.LayerGroup | null = null
let segmentLayer: L.LayerGroup | null = null
let drawEpoch = 0 // ensure only one route is drawn at a time

/* ===================== Data ===================== */
const eventsAll = ref<any[]>([]) // current dataset (either ALL or date-filtered)
const floodLocations = ref<{ location: string; count: number }[]>([])
const loadingLocations = ref(true)

/* ===================== Date filter ===================== */
const startDate = ref<string>('') // format: YYYY-MM-DD
const endDate   = ref<string>('') // format: YYYY-MM-DD
const filteringByDate = ref(false)

function isValidDateStr(s: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(s)
}

// recompute location->count from events (used when date filter is active)
function buildLocationCounts(events: any[]): { location: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const e of events) {
    const name = e.flooded_location || e.name || ''
    if (!name) continue
    counts.set(name, (counts.get(name) || 0) + 1)
  }
  return [...counts.entries()].map(([location, count]) => ({ location, count }))
}

async function applyDateFilter() {
  if (!isValidDateStr(startDate.value) || !isValidDateStr(endDate.value)) {
    alert('Please enter dates as YYYY-MM-DD.')
    return
  }
  loadingLocations.value = true
  filteringByDate.value = true
  try {
    const data = await getFloodEventsByDateRange({
      start_date: startDate.value,
      end_date: endDate.value,
    })
    // replace current dataset
    eventsAll.value = Array.isArray(data) ? data : []
    // rebuild left table counts from filtered events
    floodLocations.value = buildLocationCounts(eventsAll.value)
    // re-render markers for the current (filtered) left list
    const set = new Set(filteredLocations.value.map(r => r.location))
    renderMarkersFor(set)
    // also clear any drawn routes (new dataset)
    clearSegments()
  } catch (e) {
    console.error('Date filter fetch failed', e)
    alert('Failed to fetch events for date range.')
  } finally {
    loadingLocations.value = false
  }
}

async function clearDateFilter() {
  startDate.value = ''
  endDate.value = ''
  filteringByDate.value = false
  loadingLocations.value = true
  try {
    // restore default: use pre-aggregated locations + all events
    const [events, locations] = await Promise.all([
      getAllFloodEvents().catch(() => []),
      getFloodLocations().catch(() => []),
    ])
    eventsAll.value = events
    floodLocations.value = locations
    const set = new Set(filteredLocations.value.map(r => r.location))
    renderMarkersFor(set)
    clearSegments()
  } finally {
    loadingLocations.value = false
  }
}

/* ===================== Filters / Search ===================== */
const q = ref('')
const minCount = ref(1)
const sortBy = ref<'count' | 'name'>('count')
const sortDir = ref<'desc' | 'asc'>('desc')
const topN = ref(20)

const filteredLocations = computed(() => {
  const query = q.value.trim().toLowerCase()
  let rows = floodLocations.value

  if (query) rows = rows.filter(r => (r.location || '').toLowerCase().includes(query))
  rows = rows.filter(r => (r.count ?? 0) >= (minCount.value || 0))

  rows = [...rows].sort((a, b) => {
    if (sortBy.value === 'count') return sortDir.value === 'desc' ? b.count - a.count : a.count - b.count
    const A = (a.location || '').toLowerCase()
    const B = (b.location || '').toLowerCase()
    return sortDir.value === 'desc' ? (B > A ? 1 : -1) : (A > B ? 1 : -1)
  })

  const n = Math.max(1, Number(topN.value) || 0)
  return rows.slice(0, n)
})

function resetFilters() {
  q.value = ''
  minCount.value = 1
  sortBy.value = 'count'
  sortDir.value = 'desc'
  topN.value = 20
}

/* ===================== Tooltip helpers ===================== */
let openFloodTooltipOwner: L.Layer | null = null
function openExclusiveTooltip(owner: L.Layer, html: string, latlng?: L.LatLng) {
  if (openFloodTooltipOwner && openFloodTooltipOwner !== owner) {
    (openFloodTooltipOwner as any).closeTooltip?.()
  }
  openFloodTooltipOwner = owner
  const tt = (owner as any).getTooltip?.()
  if (tt) tt.setContent(html)
  if (latlng) (owner as any).openTooltip?.(latlng)
  else (owner as any).openTooltip?.()
}
function closeTooltipOwner(owner: L.Layer) {
  if (openFloodTooltipOwner === owner) openFloodTooltipOwner = null
  ;(owner as any).closeTooltip?.()
}

// cache details for hovers & drawing
const detailCache = new Map<number, any>()
const detailPromise = new Map<number, Promise<any>>()
async function getDetailCached(id: number) {
  if (detailCache.has(id)) return detailCache.get(id)
  if (detailPromise.has(id)) return detailPromise.get(id)!
  const p = (async () => {
    const raw = await getFloodEventById(Number(id))
    const detail = Array.isArray(raw) ? raw[0] ?? raw : raw
    detailCache.set(id, detail)
    detailPromise.delete(id)
    return detail
  })().catch(e => { detailPromise.delete(id); throw e })
  detailPromise.set(id, p)
  return p
}

// tooltip content
const fmt = {
  min: (n: any) => Number.isFinite(+n) ? `${(+n).toFixed(2)} min` : '-',
  km:  (m: any) => Number.isFinite(+m) ? `${(+m/1000).toFixed(3)} km` : '-',
}
function buildTooltip(detail: any, fallback: { id?: any, name?: string } = {}) {
  const id = detail?.id ?? detail?.flood_id ?? fallback?.id ?? '-'
  const loc = detail?.flooded_location ?? fallback?.name ?? 'Flood event'
  const road = detail?.road_name ?? '-'
  const lenM = detail?.length_m
  const delay = detail?.time_travel_delay_min ?? detail?.delay_min ?? detail?.delay

  return `
    <div class="flood-tt">
      <div class="tt-title">${loc}</div>
      <div class="tt-subtle">ID: ${id}</div>
      <div class="tt-section">Road segment</div>
      <table class="tt-table">
        <tr><th>Road</th><td>${road}</td></tr>
        <tr><th>Length</th><td>${fmt.km(lenM)}</td></tr>
        <tr><th>Travel delay</th><td>${fmt.min(delay)}</td></tr>
      </table>
    </div>`
}

/* ===================== Geometry helpers ===================== */
function wktToLatLngs(wkt: string): [number, number][][] {
  const s = (wkt || '').trim()
  if (!s) return []
  const upper = s.toUpperCase()
  const isMulti = upper.startsWith('MULTILINESTRING')
  const extractLine = (inner: string) => {
    const pairs = inner.split(',').map(p => p.trim()).filter(Boolean)
    const latlngs: [number, number][] = []
    for (const pair of pairs) {
      const [xStr, yStr] = pair.split(/\s+/).filter(Boolean)
      const lon = Number(xStr), lat = Number(yStr)
      if (isFinite(lat) && isFinite(lon)) latlngs.push([lat, lon])
    }
    return latlngs
  }
  if (isMulti) {
    const groups = s.slice(s.indexOf('(')).match(/\(([^()]+)\)/g)
    if (!groups) return []
    return groups.map(g => g.replace(/^\(|\)$/g, '')).map(extractLine).filter(a => a.length > 0)
  } else {
    const start = s.indexOf('('), end = s.lastIndexOf(')')
    if (start < 0 || end < 0 || end <= start) return []
    const arr = extractLine(s.substring(start + 1, end))
    return arr.length ? [arr] : []
  }
}

function clearSegments() {
  if (segmentLayer) { map.removeLayer(segmentLayer); segmentLayer = null }
}

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
      const gjBounds = gj.getBounds?.()
      if (gjBounds && gjBounds.isValid()) boundsAcc.extend(gjBounds)
    } catch {}
  }
}

/* ===================== Map rendering ===================== */
function ensureMap() {
  if (map) return
  map = L.map(mapEl.value as HTMLDivElement, { center: [1.3521, 103.8198], zoom: 12, zoomControl: true })
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  maxZoom: 19,
  }).addTo(map)
}

// index to “zoom to location”
const groupByLocation = new Map<string, L.LayerGroup>()

function renderMarkersFor(locationsSet: Set<string>) {
  if (!map) return
  if (visibleLayer) { map.removeLayer(visibleLayer); visibleLayer = null }
  groupByLocation.clear()

  const container = L.layerGroup()
  const bounds: L.LatLngExpression[] = []

  for (const e of eventsAll.value) {
    const name: string = e.flooded_location || e.name || ''
    if (!name || !locationsSet.has(name)) continue

    const lat = e.latitude ?? e.lat ?? e.center_lat
    const lon = e.longitude ?? e.lon ?? e.center_lon ?? e.lng
    if (!Number.isFinite(+lat) || !Number.isFinite(+lon)) continue

    const marker = L.circleMarker([+lat, +lon], {
      radius: 6, color: '#ef4444', weight: 2, fillColor: '#fca5a5', fillOpacity: 0.9
    }).bindTooltip('Loading…', { sticky: true, direction: 'top', opacity: 0.95, className: 'flood-tooltip' })

    marker.on('mouseover', async (ev: L.LeafletMouseEvent) => {
      openExclusiveTooltip(marker, 'Loading…', ev.latlng)
      try {
        const id = e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id
        const detail = id != null ? await getDetailCached(Number(id)) : e
        openExclusiveTooltip(marker, buildTooltip(detail, { id, name }), ev.latlng)
      } catch {
        openExclusiveTooltip(marker, `<div class="flood-tt">Failed to load details</div>`, ev.latlng)
      }
    })
    marker.on('mouseout', () => closeTooltipOwner(marker))

    container.addLayer(marker)
    bounds.push([+lat, +lon])

    if (!groupByLocation.has(name)) groupByLocation.set(name, L.layerGroup())
    groupByLocation.get(name)!.addLayer(marker)
  }

  visibleLayer = container.addTo(map)
  if (bounds.length) map.fitBounds(L.latLngBounds(bounds as any).pad(0.12))
}

/* Clicking a row → draw routes for that location + zoom (only one at a time) */
async function focusLocation(name: string) {
  if (!map) return
  const myEpoch = ++drawEpoch
  clearSegments()
  segmentLayer = L.layerGroup().addTo(map)

  const evts = eventsAll.value.filter(e => (e.flooded_location || e.name || '') === name)
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
    } catch { /* ignore individual failures */ }
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

/* Re-render markers when left list changes */
watch(filteredLocations, (rows) => {
  const set = new Set(rows.map(r => r.location))
  renderMarkersFor(set)
})

/* ===================== Lifecycle ===================== */
onMounted(async () => {
  ensureMap()
  const [events, locations] = await Promise.all([
    getAllFloodEvents().catch(() => []),
    getFloodLocations().catch(() => []),
  ])
  eventsAll.value = events
  floodLocations.value = locations
  loadingLocations.value = false

  await nextTick()
  const initSet = new Set(filteredLocations.value.map(r => r.location))
  renderMarkersFor(initSet)
})
</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-4">
    <!-- LEFT: sidebar -->
    <aside class="col-span-3 space-y-4">
      <div class="bg-white rounded shadow p-2">
        <div class="text-sm font-semibold">Flood-Prone Locations</div>
        <div class="text-xs text-gray-500">
          <span v-if="!filteringByDate">Showing top {{ topN }}</span>
          <span v-else>Date range: {{ startDate || '—' }} → {{ endDate || '—' }}</span>
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
          <button class="px-2 py-1 border rounded hover:bg-gray-50" @click="clearDateFilter" :disabled="!filteringByDate">
            Clear
          </button>
        </div>
        <div class="text-xs text-gray-500" v-if="filteringByDate">
          Filtering by server-side date range.
        </div>
      </div>

      <!-- Filters -->
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

      <!-- Results table -->
      <div class="bg-white rounded shadow p-3">
        <div v-if="loadingLocations" class="text-gray-500 text-sm">Loading…</div>
        <div v-else-if="!floodLocations.length" class="text-gray-500 text-sm">No flood data available.</div>
        <div v-else class="overflow-x-auto">
          <table class="min-w-full text-sm border">
            <thead class="bg-gray-100 text-gray-700">
              <tr>
                <th class="px-2 py-1 text-left border">Location</th>
                <th class="px-2 py-1 text-right border">Count</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="loc in filteredLocations"
                :key="loc.location"
                class="hover:bg-gray-50 cursor-pointer"
                @click="focusLocation(loc.location)"
                title="Draw & zoom to this location"
              >
                <td class="px-2 py-1 border">{{ loc.location }}</td>
                <td class="px-2 py-1 border text-right">{{ loc.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </aside>

    <!-- RIGHT: map -->
    <main class="col-span-9">
      <div class="bg-white rounded shadow h-[calc(100vh-2.5rem)] p-2 flex flex-col">
        <div class="flex-1 min-h-0">
          <div ref="mapEl" class="w-full h-full"></div>
        </div>
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
</style>

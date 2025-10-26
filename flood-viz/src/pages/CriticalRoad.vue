<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import * as L from 'leaflet'
import proj4 from 'proj4'
import {
  getAllFloodEvents,
  getCriticalSegmentsNearFlood,
  getFloodEventById,
  type CriticalSegmentsNearFloodResponse
} from '@/api/api'

// ─────────────────────────────────────────────────────────────
// EPSG:3414 (SVY21) → WGS84
// ─────────────────────────────────────────────────────────────
proj4.defs(
  'EPSG:3414',
  '+proj=tmerc +lat_0=1.36666666666667 +lon_0=103.833333333333 +k=1 +x_0=28001.642 +y_0=38744.572 +ellps=WGS84 +units=m +no_defs'
)
const toWGS84 = (x: number, y: number): [number, number] => {
  const [lon, lat] = proj4('EPSG:3414', 'WGS84', [x, y]) as [number, number]
  return [lat, lon]
}

// ─────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────
const loading = ref(true)
const errorMsg = ref<string | null>(null)
const infoMsg = ref<string | null>(null)        // e.g., "No critical roads near flood"
const bufferM = ref<number>(50)

const eventsAll = ref<any[]>([])
const q = ref('')
const topN = ref(500)
const filteredEvents = computed(() => {
  const query = q.value.trim().toLowerCase()
  const rows = Array.isArray(eventsAll.value) ? eventsAll.value : []
  const filtered = query
    ? rows.filter(e => (e.flooded_location || e.name || '').toLowerCase().includes(query))
    : rows
  return filtered.slice(0, Math.max(1, Number(topN.value) || 0))
})

const selectedFloodId = ref<number | null>(null)
const lastPayload = ref<CriticalSegmentsNearFloodResponse | null>(null)

// ─────────────────────────────────────────────────────────────
// Tooltip helpers for flood markers (detail on hover)
// ─────────────────────────────────────────────────────────────
const detailCache = new Map<number, any>()
const detailPromise = new Map<number, Promise<any>>()

async function getDetailCached(id: number) {
  if (detailCache.has(id)) return detailCache.get(id)
  if (detailPromise.has(id)) return detailPromise.get(id)!
  const p = (async () => {
    const raw = await getFloodEventById(id)
    const detail = Array.isArray(raw) ? raw[0] ?? raw : raw
    detailCache.set(id, detail)
    detailPromise.delete(id)
    return detail
  })().catch(e => { detailPromise.delete(id); throw e })
  detailPromise.set(id, p)
  return p
}

const fmt = {
  min: (n: any) => Number.isFinite(+n) ? `${(+n).toFixed(2)} min` : '—',
  km:  (m: any) => Number.isFinite(+m) ? `${(+m/1000).toFixed(3)} km` : '—',
  date: (s: any) => {
    if (!s) return '—'
    try { return new Date(s).toLocaleString() } catch { return String(s) }
  }
}

function buildFloodTooltip(detail: any, fallback: { id?: any, name?: string } = {}) {
  // Safe field extraction with fallbacks
  const id       = detail?.id ?? detail?.flood_id ?? fallback?.id ?? '—'
  const loc      = detail?.flooded_location ?? detail?.name ?? fallback?.name ?? 'Flood event'
  const startedAt= detail?.started_at ?? detail?.start_time ?? detail?.timestamp

  const roadName = (typeof detail?.road_name === 'string' && detail.road_name.trim())
    ? detail.road_name
    : 'Unnamed Road'
  const roadType = detail?.road_type ?? '—'
  const lenM     = Number(detail?.length_m)

  // Traffic metrics (minutes)
  const t20  = Number(detail?.time_20kmh_min)
  const t50  = Number(detail?.time_50kmh_min)
  const delay= Number(detail?.time_travel_delay_min ?? detail?.delay_min ?? detail?.delay)

  // Small helpers
  const fmtMin = (n: any) => Number.isFinite(+n) ? `${(+n).toFixed(2)} min` : '—'
  const fmtKm  = (m: any) => Number.isFinite(+m) ? `${(+m/1000).toFixed(3)} km` : '—'
  const fmtDate= (s: any) => {
    if (!s) return '—'
    try { return new Date(s).toLocaleString() } catch { return String(s) }
  }

  return `
    <div class="flood-tt">
      <div class="tt-title">Flood details</div>
      <div class="tt-subtle">ID: ${id}</div>

      <div class="tt-section">Location</div>
      <table class="tt-table">
        <tr><th>Name</th><td>${loc}</td></tr>
        <tr><th>Start</th><td>${fmtDate(startedAt)}</td></tr>
      </table>

      <div class="tt-section">Road segment</div>
      <table class="tt-table">
        <tr><th>Road name</th><td>${roadName}</td></tr>
        <tr><th>Type</th><td>${roadType}</td></tr>
        <tr><th>Length</th><td>${fmtKm(lenM)}</td></tr>
      </table>

      <div class="tt-section">Traffic impact</div>
      <table class="tt-table">
        <tr><th>Time @ 20 km/h</th><td>${fmtMin(t20)}</td></tr>
        <tr><th>Time @ 50 km/h</th><td>${fmtMin(t50)}</td></tr>
        <tr><th>Travel delay</th><td>${fmtMin(delay)}</td></tr>
      </table>
    </div>`
}

// ─────────────────────────────────────────────────────────────
// Map + layers
// ─────────────────────────────────────────────────────────────
const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map
let markersLayer: L.LayerGroup | null = null
let criticalLayer: L.LayerGroup | null = null
let highlighted: L.Polyline | null = null

/* Map init */
function ensureMap() {
  if (map) return

  const token = import.meta.env.VITE_MAPBOX_TOKEN
  const styleId = 'mapbox/streets-v12' // you can switch to 'mapbox/dark-v11', etc.

  map = L.map(mapEl.value as HTMLDivElement, {
    center: [1.3521, 103.8198],
    zoom: 12,
    zoomControl: true,
  })

  // ✅ Correct, type-safe way to inject the token into the URL
  const url = `https://api.mapbox.com/styles/v1/${styleId}/tiles/512/{z}/{x}/{y}@2x?access_token=${token}`

  L.tileLayer(url, {
    tileSize: 512,
    zoomOffset: -1,
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors ' +
      '&copy; <a href="https://www.mapbox.com/">Mapbox</a>',
  }).addTo(map)
}

function clearCritical() {
  if (criticalLayer) { map.removeLayer(criticalLayer); criticalLayer = null }
  if (highlighted) { map.removeLayer(highlighted); highlighted = null }
}

function renderFloodMarkers() {
  if (!map) return
  if (markersLayer) { map.removeLayer(markersLayer); markersLayer = null }
  markersLayer = L.layerGroup().addTo(map)

  const bounds = L.latLngBounds([])

  for (const e of filteredEvents.value) {
    const name: string = e.flooded_location || e.name || ''
    const lat = e.latitude ?? e.lat ?? e.center_lat
    const lon = e.longitude ?? e.lon ?? e.center_lon ?? e.lng
    if (!Number.isFinite(+lat) || !Number.isFinite(+lon)) continue

    const marker = L.circleMarker([+lat, +lon], {
      radius: 7, color: '#1e40af', weight: 3, fillColor: '#3b82f6', fillOpacity: 0.95,
      className: 'flood-marker',
    })
    .bindTooltip(
      `<div class="flood-tt"><div class="tt-title">${name || 'Flood event'}</div><div class="tt-subtle">ID: ${e.flood_id ?? e.id ?? '—'}</div></div>`,
      { sticky: true, direction: 'top', opacity: 0.95, className: 'flood-tooltip' }
    )
    .on('mouseover', async (ev: L.LeafletMouseEvent) => {
      try {
        const id = Number(e.flood_id ?? e.id)
        if (!Number.isFinite(id)) return
        const tt = (marker as any).getTooltip?.()
        tt?.setContent(`<div class="flood-tt">Loading…</div>`)
        ;(marker as any).openTooltip?.(ev.latlng)
        const detail = await getDetailCached(id)
        tt?.setContent(buildFloodTooltip(detail, { id, name }))
        ;(marker as any).openTooltip?.(ev.latlng)
      } catch {
        (marker as any).getTooltip?.()?.setContent(`<div class="flood-tt">Failed to load details</div>`)
      }
    })
    .on('click', () => {
      onSelectFloodRow(e)
    })

    markersLayer.addLayer(marker)
    bounds.extend([+lat, +lon])
  }

  if (bounds.isValid()) map.fitBounds(bounds.pad(0.12))
}

// Row click handler (avoid inline .value errors)
function onSelectFloodRow(e: any) {
  const id = Number(e?.flood_id ?? e?.id)
  if (!Number.isFinite(id) || id <= 0) {
    errorMsg.value = 'Invalid flood id.'
    return
  }
  selectedFloodId.value = id
  fetchAndDrawCritical(id)
}

async function fetchAndDrawCritical(fid: number) {
  clearCritical()
  errorMsg.value = null
  infoMsg.value = null

  if (!Number.isFinite(fid) || fid <= 0) {
    errorMsg.value = 'Select a valid flood event (flood_id > 0).'
    return
  }
  const buf = Math.max(1, Number(bufferM.value || 50))

  try {
    const payload = await getCriticalSegmentsNearFlood({
      flood_id: fid,
      buffer_m: buf,
    }) as unknown as (CriticalSegmentsNearFloodResponse & { message?: string })

    if (payload && typeof (payload as any).message === 'string') {
      // Backend returned: { "message": "No critical roads near flood" }
      lastPayload.value = null
      infoMsg.value = (payload as any).message || 'No critical roads near this flood.'
      // Still draw the flood point if available from events list
      drawOnlyFloodPoint(fid)
      return
    }

    lastPayload.value = payload
    drawCritical(payload)
  } catch (e: any) {
    console.error(e)
    errorMsg.value = e?.message || 'Failed to fetch critical segments.'
  }
}

function drawOnlyFloodPoint(fid: number) {
  clearCritical()
  criticalLayer = L.layerGroup().addTo(map)

  const evt = eventsAll.value.find(e => Number(e.flood_id ?? e.id) === Number(fid))
  const lat = evt?.latitude ?? evt?.lat ?? evt?.center_lat
  const lon = evt?.longitude ?? evt?.lon ?? evt?.center_lon ?? evt?.lng
  if (!Number.isFinite(+lat) || !Number.isFinite(+lon)) return

  // dot only, no tooltip
  const m = L.circleMarker([+lat, +lon], {
    radius: 6,
    color: '#991b1b',
    weight: 3,
    fillColor: '#ef4444',
    fillOpacity: 0.95,
    interactive: false,        // <- disables hover/click & tooltips
  })
  criticalLayer.addLayer(m)

  map.fitBounds(L.latLngBounds([[+lat, +lon]]).pad(0.25))
}

function drawCritical(p: CriticalSegmentsNearFloodResponse) {
  clearCritical()
  criticalLayer = L.layerGroup().addTo(map)
  const bounds = L.latLngBounds([])

  const fp = (p as any).flood_point
    if (fp?.type === 'Point' && Array.isArray(fp.coordinates) && fp.coordinates.length === 2) {
    const [lon, lat] = fp.coordinates
    const m = L.circleMarker([lat, lon], {
        radius: 6,
        color: '#991b1b',
        weight: 3,
        fillColor: '#ef4444',
        fillOpacity: 0.95,
        interactive: false,        // <- disables hover/click & tooltips
    })
    criticalLayer.addLayer(m)
    bounds.extend([lat, lon])
    }

  // critical segments (EPSG:3414 → WGS84)
  for (const seg of (p as any).critical_segments || []) {
    const coords: [number, number][] = seg?.geometry?.coordinates || []
    const latlngs: [number, number][] = []
    for (const [x, y] of coords) {
      const [lat, lon] = toWGS84(x, y)
      latlngs.push([lat, lon])
      bounds.extend([lat, lon])
    }
    if (!latlngs.length) continue

    const safeName =
      (typeof seg.road_name === 'string' && seg.road_name.trim())
        ? seg.road_name
        : 'Unnamed Road'

    const poly = L.polyline(latlngs, {
      color: '#dc2626', weight: 6, opacity: 0.95, dashArray: '4,6',
    }).bindTooltip(`
      <div class="flood-tt">
        <div class="tt-title">${safeName}</div>
        <div class="tt-subtle">${seg.road_type || '—'}</div>
        <table class="tt-table" style="margin-top:6px;">
          <tr><th>Length</th><td>${Number(seg.length_m).toFixed(2)} m</td></tr>
          <tr><th>Centrality</th><td>${Number(seg.centrality_score).toFixed(6)}</td></tr>
          <tr><th>Buffer</th><td>${(p as any).buffer_m} m</td></tr>
        </table>
      </div>
    `, { sticky: true, direction: 'top', opacity: 0.95, className: 'flood-tooltip' })

    ;(poly as any).__meta = { seg }
    criticalLayer.addLayer(poly)
  }

  if (bounds.isValid()) map.fitBounds(bounds.pad(0.12))
}

function highlightSegmentAt(idx: number) {
  if (!criticalLayer) return
  if (highlighted) { map.removeLayer(highlighted); highlighted = null }

  let i = 0; let target: L.Polyline | null = null
  criticalLayer.eachLayer((l: any) => {
    if (l instanceof L.Polyline) {
      if (i === idx) target = l
      i++
    }
  })
  if (target) {
    const latlngs = (target as any).getLatLngs?.() as L.LatLng[] | L.LatLng[][]
    const flat = Array.isArray(latlngs?.[0]) ? (latlngs as L.LatLng[][]).flat() : (latlngs as L.LatLng[])
    if (flat?.length) {
      highlighted = L.polyline(flat, { color: '#7c3aed', weight: 7, opacity: 0.95 }).addTo(map)
      map.fitBounds(L.latLngBounds(flat as any).pad(0.2))
    }
  }
}

// re-render markers when list changes
watch([filteredEvents], () => { renderFloodMarkers() })

// debounce refetch on buffer change (if a flood already selected)
let bufTimer: number | undefined
watch(bufferM, () => {
  if (!selectedFloodId.value) return
  window.clearTimeout(bufTimer)
  bufTimer = window.setTimeout(() => fetchAndDrawCritical(selectedFloodId.value!), 400)
})

// lifecycle
onMounted(async () => {
  ensureMap()
  try {
    const events = await getAllFloodEvents()
    eventsAll.value = Array.isArray(events) ? events : []
  } catch (e: any) {
    console.error(e)
    errorMsg.value = e?.message || 'Failed to load flood events.'
  } finally {
    loading.value = false
    await nextTick()
    renderFloodMarkers()
  }

  // deep links (?flood_id=&buffer_m=)
  const qs = new URLSearchParams(window.location.search)
  const fid = Number(qs.get('flood_id'))
  const buf = Number(qs.get('buffer_m'))
  if (Number.isFinite(buf) && buf >= 1) bufferM.value = buf
  if (Number.isFinite(fid) && fid > 0) {
    selectedFloodId.value = fid
    fetchAndDrawCritical(fid)
  }
})
</script>

<template>
  <div class="h-full grid grid-cols-12 gap-4 p-4">
    <!-- LEFT: controls & lists -->
    <aside class="col-span-4 space-y-4">
      <div class="bg-white rounded shadow p-3 space-y-3">
        <div class="text-sm font-semibold">Critical Roads Near Flood</div>

        <div class="grid grid-cols-2 gap-2">
          <label class="text-xs text-gray-600 self-center">Buffer (m)</label>
          <input v-model.number="bufferM" type="number" min="1" step="1" class="px-2 py-1 border rounded text-sm" />
          <label class="text-xs text-gray-600 self-center">Filter by location</label>
          <input v-model="q" type="text" placeholder="e.g. Yishun Ave 2" class="px-2 py-1 border rounded text-sm" />
        </div>

        <div v-if="errorMsg" class="text-xs text-red-600">{{ errorMsg }}</div>
        <div v-if="infoMsg" class="text-xs text-amber-700">{{ infoMsg }}</div>

        <div class="text-xs text-gray-600">
          <div>Events loaded: <span class="font-medium">{{ eventsAll.length }}</span></div>
          <div>Showing: <span class="font-medium">{{ filteredEvents.length }}</span></div>
          <div v-if="lastPayload">Selected Flood: <span class="font-medium">{{ lastPayload.flood_id }}</span> • Segments: <span class="font-medium">{{ lastPayload.count_critical_segments }}</span></div>
        </div>
      </div>

      <div class="bg-white rounded shadow p-3">
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm font-semibold">Flood Events</div>
          <div class="text-xs text-gray-500">Click a row to draw critical segments</div>
        </div>

        <div v-if="loading" class="text-gray-500 text-sm">Loading…</div>
        <div v-else-if="!eventsAll.length" class="text-gray-500 text-sm">No flood events.</div>

        <div v-else class="max-h-[50vh] overflow-auto">
          <table class="min-w-full text-sm border">
            <thead class="bg-gray-100 text-gray-700 sticky top-0">
              <tr>
                <th class="px-2 py-1 border text-left">Location</th>
                <th class="px-2 py-1 border text-right">ID</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="e in filteredEvents"
                :key="e.flood_id ?? e.id"
                class="hover:bg-gray-50 cursor-pointer"
                @click="onSelectFloodRow(e)"
                :title="`Zoom & draw critical segments for Flood ${e.flood_id ?? e.id}`"
              >
                <td class="px-2 py-1 border">{{ e.flooded_location || e.name || 'Flood event' }}</td>
                <td class="px-2 py-1 border text-right">{{ e.flood_id ?? e.id }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="lastPayload && lastPayload.critical_segments?.length" class="bg-white rounded shadow p-3">
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm font-semibold">Critical Segments</div>
          <div class="text-xs text-gray-500">Click a row to zoom</div>
        </div>
        <div class="max-h-[40vh] overflow-auto">
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
              <tr
                v-for="(seg, idx) in lastPayload.critical_segments"
                :key="idx"
                class="hover:bg-gray-50 cursor-pointer"
                @click="highlightSegmentAt(idx)"
              >
                <td class="px-2 py-1 border">{{ (typeof seg.road_name === 'string' && seg.road_name.trim()) ? seg.road_name : 'Unnamed Road' }}</td>
                <td class="px-2 py-1 border">{{ seg.road_type || '—' }}</td>
                <td class="px-2 py-1 border text-right">{{ Number(seg.length_m).toFixed(2) }}</td>
                <td class="px-2 py-1 border text-right">{{ Number(seg.centrality_score).toFixed(6) }}</td>
              </tr>
            </tbody>
          </table>
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
.flood-marker path {
  filter: drop-shadow(0 0 6px rgba(59,130,246,0.45));
  animation: pulse-blue 2.1s ease-in-out infinite;
}
@keyframes pulse-blue {
  0%, 100% { transform: scale(1);   opacity: 1; }
  50%      { transform: scale(1.08); opacity: 0.85; }
}
</style>

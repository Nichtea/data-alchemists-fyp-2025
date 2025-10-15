<script setup lang="ts">
import { onMounted, watch, ref } from 'vue'
import * as L from 'leaflet'
import { useAppStore } from '@/store/app'
import {
  getAllBusStops, getBusStopByCode,
  getAllFloodEvents, getFloodEventById,
} from '@/api/api'

const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map

// Layers
let stopsLayer: L.LayerGroup | null = null
let floodEventsLayer: L.LayerGroup | null = null
let driveRouteLayer: L.LayerGroup | null = null
let roadSegmentLayer: L.LayerGroup | null = null
let busRouteLayer: L.LayerGroup | null = null
let serviceRouteLayer: L.LayerGroup | null = null

const store = useAppStore()

/* ================= Flood hover: cache + single-owner tooltip ================= */
const floodDetailCache = new Map<number, any>()
const floodDetailPromise = new Map<number, Promise<any>>() // dedupe fetches

// only one tooltip open at a time
let openFloodTooltipOwner: L.Layer | null = null
let floodHoverEpoch = 0 // increments on every hover to cancel stale responses

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

async function getFloodDetailCached(id: number) {
  if (floodDetailCache.has(id)) return floodDetailCache.get(id)
  if (floodDetailPromise.has(id)) return floodDetailPromise.get(id)!
  const p = (async () => {
    const raw = await getFloodEventById(Number(id))
    const detail = Array.isArray(raw) ? raw[0] ?? raw : raw
    floodDetailCache.set(id, detail)
    floodDetailPromise.delete(id)
    return detail
  })().catch((e) => { floodDetailPromise.delete(id); throw e })
  floodDetailPromise.set(id, p)
  return p
}

/* ================= Helpers (robust parsing + nested key search) ================= */
function parseMaybeMinutes(val: any): number | undefined {
  if (val == null) return undefined
  if (typeof val === 'number' && Number.isFinite(val)) return val
  const s = String(val).trim().toLowerCase()
  if (!s) return undefined
  // "1.18 min" -> 1.18
  const m = s.match(/^(-?\d+(\.\d+)?)\s*(m|min|mins|minute|minutes)$/)
  if (m) return Number(m[1])
  // "00:01:11" -> minutes
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(s)) {
    const parts = s.split(':').map(Number)
    if (parts.length === 2) return parts[0] + parts[1] / 60
    if (parts.length === 3) return parts[0] * 60 + parts[1] + parts[2] / 60
  }
  const n = Number(s)
  return Number.isFinite(n) ? n : undefined
}

// recursively look for the first matching key (case-insensitive)
function pickNumNested(obj: any, keys: string[]): number | undefined {
  const seen = new Set<any>()
  function dfs(o: any): number | undefined {
    if (!o || typeof o !== 'object' || seen.has(o)) return undefined
    seen.add(o)
    // direct keys first
    for (const k of keys) {
      // try exact, then case-insensitive scan
      if (o?.[k] != null) {
        const n = parseMaybeMinutes(o[k])
        if (n != null) return n
      }
    }
    for (const [kk, vv] of Object.entries(o)) {
      if (keys.some(k => k.toLowerCase() === kk.toLowerCase())) {
        const n = parseMaybeMinutes(vv)
        if (n != null) return n
      }
    }
    // traverse arrays/objects
    for (const v of Object.values(o)) {
      const cand = dfs(v)
      if (cand != null) return cand
    }
    return undefined
  }
  return dfs(obj)
}

function fmtMinutes(val: any) {
  const n = Number(val)
  if (!Number.isFinite(n)) return '-'
  return `${n.toFixed(2)} min`
}
function fmtMinutesForce(val: any) {
  if (val === 0) return '0.00 min'
  const n = Number(val)
  if (!Number.isFinite(n)) return '-'
  return `${n.toFixed(2)} min`
}
function fmtKmFromMeters(m: any) {
  const n = Number(m)
  if (!Number.isFinite(n)) return '-'
  return `${(n / 1000).toFixed(3)} km`
}

/* ============== Tooltip content (with robust delay fallback) ============== */
function buildFloodTooltip(detail: any, fallback: { id?: any, name?: string } = {}) {
  const id = detail?.id ?? detail?.flood_id ?? fallback?.id ?? '-'
  const roadName = detail?.road_name ?? 'Unknown'
  const roadType = detail?.road_type ?? 'unclassified'
  const lengthM  = detail?.length_m

  // Try a wide set of names, search nested, and parse strings
  const t20 = pickNumNested(detail, [
    'time_20kmh_min','time_at_20_kmh_min','eta_20kmh_min','t_20min','time20','t20'
  ])
  const t50 = pickNumNested(detail, [
    'time_50kmh_min','time_at_50_kmh_min','eta_50kmh_min','t_50min','time50','t50'
  ])

  // Common baseline/flooded ETA keys
  const flooded = pickNumNested(detail, [
    'flooded_time_min','eta_flooded_min','flood_time_min','eta_flooded'
  ])
  const baseline = pickNumNested(detail, [
    'baseline_time_min','eta_baseline_min','normal_time_min','eta_baseline'
  ])

  // Primary attempt: direct travel delay keys anywhere in object
  let delay = pickNumNested(detail, [
    'travel_delay_min','travel_delay','delay_min','delay','extra_time_min',
    'additional_delay_min','impact_delay','traffic_delay'
  ])

  // Fallbacks: compute if possible
  if (delay == null && flooded != null && baseline != null) {
    delay = flooded - baseline
  }
  if (delay == null && t20 != null && t50 != null) {
    // Last-resort heuristic (still better than blank)
    delay = Math.max(0, t20 - t50)
  }

  return `
  <div class="flood-tt">
    <div class="tt-title">Flood details</div>
    <div class="tt-subtle">ID: ${id}</div>

    <div class="tt-section">Event</div>

    <div class="tt-section">Road segment</div>
    <table class="tt-table">
      <tr><th>Road name</th><td>${roadName}</td></tr>
      <tr><th>Type</th><td>${roadType}</td></tr>
      <tr><th>Length</th><td>${fmtKmFromMeters(lengthM)}</td></tr>
    </table>

    <div class="tt-section">Traffic impact</div>
    <table class="tt-table">
      <tr><th>Time @ 20 km/h</th><td>${fmtMinutes(t20)}</td></tr>
      <tr><th>Time @ 50 km/h</th><td>${fmtMinutes(t50)}</td></tr>
      <tr><th>Travel delay</th><td>${fmtMinutesForce(delay)}</td></tr>
    </table>
  </div>`
}

/* ================= Colored service polylines ================= */
let coloredPolylinesGroup: L.LayerGroup | null = null
function ensureColoredGroup() {
  if (!coloredPolylinesGroup) coloredPolylinesGroup = L.layerGroup().addTo(map)
}
function clearColoredPolylines() { if (coloredPolylinesGroup) coloredPolylinesGroup.clearLayers() }
function setColoredPolylines(pl: Array<{ path:[number,number][], color:string, flooded:boolean }>) {
  ensureColoredGroup()
  clearColoredPolylines()
  if (!pl?.length) return
  const all: L.LatLngExpression[] = []
  for (const seg of pl) {
    const latlngs = seg.path.map(([lat, lon]) => [lat, lon] as [number, number])
    L.polyline(latlngs, { color: seg.color, weight: 8, opacity: 0.92, lineCap: 'round', lineJoin: 'round' })
      .addTo(coloredPolylinesGroup!)
    all.push(...latlngs)
  }
  const b = all.length ? L.latLngBounds(all as any) : null
  if (b && b.isValid()) map.fitBounds(b.pad(0.12))
}
;(store as any).setColoredPolylines = setColoredPolylines
;(store as any).clearColoredPolylines = clearColoredPolylines
/* ============================================================ */

const STOP_STYLE_DEFAULT: L.CircleMarkerOptions = {
  radius: 3, color: '#0ea5e9', weight: 2, fillColor: '#38bdf8', fillOpacity: 0.9,
}
const STOP_STYLE_ACTIVE: L.CircleMarkerOptions = {
  radius: 4, color: '#ef4444', weight: 3, fillColor: '#fca5a5', fillOpacity: 0.95,
}
let lastSelectedStopMarker: L.CircleMarker | null = null
function activateStopMarker(m: L.CircleMarker) {
  if (lastSelectedStopMarker && lastSelectedStopMarker !== m) {
    lastSelectedStopMarker.setStyle(STOP_STYLE_DEFAULT)
  }
  m.setStyle(STOP_STYLE_ACTIVE)
  m.bringToFront()
  lastSelectedStopMarker = m
}

function ensureMap() {
  if (map) return
  map = L.map(mapEl.value as HTMLDivElement, { center: [1.3521, 103.8198], zoom: 12, zoomControl: true })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap', maxZoom: 19,
  }).addTo(map)
}

function clearLayer(layer: L.Layer | null) { if (layer && map) map.removeLayer(layer) }
function clearStopsOverlays() {
  if (stopsLayer) { map.removeLayer(stopsLayer); stopsLayer = null }
  if (lastSelectedStopMarker) lastSelectedStopMarker = null
  map?.closePopup?.()
}
function clearFloodOverlays() {
  if (floodEventsLayer) { map.removeLayer(floodEventsLayer); floodEventsLayer = null }
  if (roadSegmentLayer) { map.removeLayer(roadSegmentLayer); roadSegmentLayer = null }
  map?.closePopup?.()
  ++detailEpoch
}
function clearAllRouteOverlays() {
  if (busRouteLayer) { map.removeLayer(busRouteLayer); busRouteLayer = null }
  if (serviceRouteLayer) { map.removeLayer(serviceRouteLayer); serviceRouteLayer = null }
  if (driveRouteLayer) { map.removeLayer(driveRouteLayer); driveRouteLayer = null }
  clearColoredPolylines()
  if (roadSegmentLayer) { map.removeLayer(roadSegmentLayer); roadSegmentLayer = null }
}

/* ---------------- WKT helpers ---------------- */
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
function renderRoadSegmentFromDetail(detail: any) {
  if (!detail || typeof detail.geometry !== 'string') return
  const lineGroups = wktToLatLngs(detail.geometry)
  if (!lineGroups.length) return
  const group = L.layerGroup()
  const baseStyle: L.PolylineOptions = { color: '#1d4ed8', weight: 8, opacity: 0.9, dashArray: '8,6' }
  const roadName = detail.road_name ?? 'Road segment'
  const roadType = detail.road_type ?? '-'
  const lengthM  = Number(detail.length_m ?? 0)
  for (const latlngs of lineGroups) {
    const poly = L.polyline(latlngs, baseStyle)
    poly.bindTooltip(`${roadName}`, { sticky: true })
    poly.bindPopup(`
      <div style="font-weight:600;margin-bottom:4px">${roadName}</div>
      <div>Type: ${roadType}</div>
      <div>Length: ${isFinite(lengthM) ? (lengthM/1000).toFixed(3) + ' km' : '-'}</div>
    `)
    group.addLayer(poly)
  }
  roadSegmentLayer = group.addTo(map)
}

/* ---------------- Pickers ---------------- */
function pickStopFields(s: any) {
  const lat = s.lat ?? s.latitude ?? s.stop_lat
  const lon = s.lon ?? s.lng ?? s.longitude ?? s.stop_lon
  const name = s.name ?? s.stop_name ?? s.description ?? s.stop_desc ?? ''
  const code = s.stop_code ?? s.code ?? s.id ?? s.stop_id ?? ''
  const id = s.id ?? s.stop_id ?? code
  return { lat: Number(lat), lon: Number(lon), name: String(name), code: String(code), id }
}
function pickFloodFields(e: any) {
  const id = e.flood_id ?? e.id ?? e.flood_event_id ?? e.event_id ?? e.pk ?? null
  const name = e.flooded_location ?? e.name ?? e.title ?? `Flood ${id ?? ''}`
  let lat = e.latitude ?? e.lat ?? e.center_lat
  let lon = e.longitude ?? e.lon ?? e.center_lon ?? e.lng
  if ((lat == null || lon == null) && e?.geom?.type && Array.isArray(e.geom.coordinates)) {
    const [lonC, latC] = e.geom.coordinates; lat = latC; lon = lonC
  }
  return { id, name, lat: lat != null ? Number(lat) : undefined, lon: lon != null ? Number(lon) : undefined, hasGeometry: !!e?.geom, geometry: e?.geom ?? null, raw: e }
}

/* ===================================================================== */
/*                   E P O C H  –  C A N C E L  S T A L E                */
/* ===================================================================== */
let renderEpoch = 0
let detailEpoch = 0
type Mode = 'stops' | 'flood' | null
const getMode = (): Mode => (store.layers.stops ? 'stops' : store.layers.floodEvents ? 'flood' : null)

/* Async renders take an epoch and bail if it changed */
async function renderStops(epoch: number) {
  clearStopsOverlays()
  if (!store.layers.stops) return
  const stops = await getAllBusStops()
  if (epoch !== renderEpoch) return
  const group = L.layerGroup()
  for (const raw of stops as any[]) {
    const { lat, lon, name, code } = pickStopFields(raw)
    if (!isFinite(lat) || !isFinite(lon)) continue
    const marker = L.circleMarker([lat, lon], STOP_STYLE_DEFAULT)
    marker.bindTooltip(`<strong>${name || 'Stop'}</strong><br/>Code: ${code || '-'}`, { sticky: true })
    marker.on('click', async () => {
      activateStopMarker(marker)
      try {
        store.setSelectedStopLoading(true)
        store.selectStop(code || null)
        const detail = await getBusStopByCode(String(code))
        if (epoch !== renderEpoch) return
        store.setSelectedStop(detail)
        store.setActiveTab('stops')
      } finally {
        store.setSelectedStopLoading(false)
      }
    })
    group.addLayer(marker)
  }
  if (epoch !== renderEpoch) return
  stopsLayer = group.addTo(map)
}

async function renderFloodEvents(epoch: number) {
  clearFloodOverlays()
  if (!store.layers.floodEvents) return

  const events = await getAllFloodEvents()
  if (epoch !== renderEpoch) return

  const group = L.layerGroup()

  for (const ev of events as any[]) {
    const picked = pickFloodFields(ev)
    if (!picked.id) continue

    // =========== Area GeoJSON =========== //
    if (picked.hasGeometry && picked.geometry) {
      const feature = { type: 'Feature', geometry: picked.geometry, properties: { id: picked.id, name: picked.name } }
      const geo = L.geoJSON(feature as any, {
        style: (): L.PathOptions => ({ color: '#ef4444', weight: 3, opacity: 0.9, fillOpacity: 0.25 }),
      })

      geo.eachLayer((child: any) => {
        child.bindTooltip('<div class="flood-tt">Loading…</div>', {
          sticky: true, direction: 'top', opacity: 0.95, className: 'flood-tooltip'
        })

        child.on('mouseover', async (e: L.LeafletMouseEvent) => {
          const myEpoch = ++floodHoverEpoch
          openExclusiveTooltip(child, '<div class="flood-tt">Loading…</div>', e.latlng)
          try {
            const detail = await getFloodDetailCached(Number(picked.id))
            if (myEpoch !== floodHoverEpoch || epoch !== renderEpoch) return
            const html = buildFloodTooltip(detail, { id: picked.id, name: picked.name })
            openExclusiveTooltip(child, html, e.latlng)
          } catch {
            if (myEpoch !== floodHoverEpoch) return
            openExclusiveTooltip(child, '<div class="flood-tt">Failed to load details</div>', e.latlng)
          }
        })

        child.on('mouseout', () => closeTooltipOwner(child))
      })

      // click still drives left panel + road segment
      geo.on('click', async () => {
        store.setSelectedFloodLoading(true)
        const dEpoch = detailEpoch
        try {
          store.selectFlood(picked.id)
          const detail = await getFloodEventById(Number(picked.id))
          if (dEpoch !== detailEpoch) return
          store.setSelectedFlood(detail)
          store.setActiveTab('flood')
          renderRoadSegmentFromDetail(Array.isArray(detail) ? detail[0] : detail)
        } finally {
          store.setSelectedFloodLoading(false)
        }
      })

      group.addLayer(geo)
      continue
    }

    // =========== Point marker =========== //
    if (!Number.isFinite(picked.lat!) || !Number.isFinite(picked.lon!)) continue

    const marker = L.circleMarker([picked.lat!, picked.lon!], {
      radius: 6, color: '#ef4444', weight: 2, fillColor: '#fca5a5', fillOpacity: 0.9,
    }).bindTooltip('<div class="flood-tt">Loading…</div>', {
      sticky: true, direction: 'top', opacity: 0.95, className: 'flood-tooltip'
    })

    marker.on('mouseover', async () => {
      const myEpoch = ++floodHoverEpoch
      openExclusiveTooltip(marker, '<div class="flood-tt">Loading…</div>')
      try {
        const detail = await getFloodDetailCached(Number(picked.id))
        if (myEpoch !== floodHoverEpoch || epoch !== renderEpoch) return
        const html = buildFloodTooltip(detail, { id: picked.id, name: picked.name })
        openExclusiveTooltip(marker, html)
      } catch {
        if (myEpoch !== floodHoverEpoch) return
        openExclusiveTooltip(marker, '<div class="flood-tt">Failed to load details</div>')
      }
    })
    marker.on('mouseout', () => closeTooltipOwner(marker))

    marker.on('click', async () => {
      store.setSelectedFloodLoading(true)
      const dEpoch = detailEpoch
      try {
        store.selectFlood(picked.id)
        const detail = await getFloodEventById(Number(picked.id))
        if (dEpoch !== detailEpoch) return
        store.setSelectedFlood(detail)
        store.setActiveTab('flood')
        renderRoadSegmentFromDetail(Array.isArray(detail) ? detail[0] : detail)
      } finally {
        store.setSelectedFloodLoading(false)
      }
    })

    group.addLayer(marker)
  }

  if (epoch !== renderEpoch) return
  floodEventsLayer = group.addTo(map)
}

/* Central authoritative renderer */
async function renderLayers() {
  ensureMap()
  const epoch = ++renderEpoch
  ++detailEpoch

  clearAllRouteOverlays()
  clearStopsOverlays()
  clearFloodOverlays()

  if (store.layers.stops) {
    store.layers.floodEvents = false
    await renderStops(epoch)
  } else if (store.layers.floodEvents) {
    store.layers.stops = false
    await renderFloodEvents(epoch)
  }
}

/* =================== Layer toggle Leaflet control =================== */
let uiCheckboxStops: HTMLInputElement | null = null
function addLayerToggleControl() {
  const C = L.Control.extend({
    onAdd: () => {
      const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control')
      div.style.background = '#fff'
      div.style.padding = '8px 10px'
      div.style.boxShadow = '0 1px 4px rgba(0,0,0,.2)'
      div.style.font = '12px/1.2 system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial'

      const label = document.createElement('label')
      label.style.display = 'flex'
      label.style.alignItems = 'center'
      label.style.gap = '6px'
      label.style.cursor = 'pointer'

      const cb = document.createElement('input')
      cb.type = 'checkbox'
      cb.checked = !!store.layers.stops
      uiCheckboxStops = cb

      const span = document.createElement('span')
      span.textContent = 'Bus stops'

      label.appendChild(cb)
      label.appendChild(span)
      div.appendChild(label)

      L.DomEvent.disableClickPropagation(div)

      cb.addEventListener('change', () => {
        const on = cb.checked
        store.layers.stops = on
        if (on) store.layers.floodEvents = false
      })

      return div
    },
    onRemove: () => {}
  })
  new C({ position: 'topleft' }).addTo(map)
}
watch(() => store.layers.stops, (v) => {
  if (uiCheckboxStops && uiCheckboxStops.checked !== v) uiCheckboxStops.checked = v
})

/* ========================= Reactivity glue ========================= */
onMounted(async () => {
  renderLayers()
  addLayerToggleControl()
})
watch(() => ({ ...store.layers }), () => renderLayers(), { deep: true })
watch(() => store.activeTab, (tab) => {
  if (tab === 'stops') {
    store.layers.stops = true
    store.layers.floodEvents = false
  } else if (tab === 'flood') {
    store.layers.floodEvents = true
    store.layers.stops = false
  }
  renderLayers()
})

/* ======= Other optional overlays ======= */
let originMarker: L.Layer | null = null
let destMarker: L.Layer | null = null
function clear(l: L.Layer | null) { if (l && map) map.removeLayer(l) }

watch(() => store.highlightOrigin, (v) => {
  clear(originMarker)
  if (!v) return
  originMarker = L.circleMarker([v.lat, v.lon], {
    radius: 7, weight: 3, color: '#2563eb', fillColor: '#93c5fd', fillOpacity: 0.95
  }).bindTooltip(`Origin stop${v.code ? ` (${v.code})` : ''}`, { sticky: true })
  originMarker.addTo(map)
}, { deep: true })

watch(() => store.highlightDest, (v) => {
  clear(destMarker)
  if (!v) return
  destMarker = L.circleMarker([v.lat, v.lon], {
    radius: 7, weight: 3, color: '#16a34a', fillColor: '#86efac', fillOpacity: 0.95
  }).bindTooltip(`Destination stop${v.code ? ` (${v.code})` : ''}`, { sticky: true })
  destMarker.addTo(map)
}, { deep: true })

watch(() => store.busTripOverlay, (o) => {
  if (busRouteLayer) { map.removeLayer(busRouteLayer); busRouteLayer = null }
  if (!o) return
  const group = L.layerGroup()
  const start = L.circleMarker([o.start.lat, o.start.lon], { radius: 6, color:'#2563eb', weight:2, fillOpacity:0.9 }).bindTooltip('Trip start', { sticky: true })
  const end   = L.circleMarker([o.end.lat, o.end.lon],   { radius: 6, color:'#16a34a', weight:2, fillOpacity:0.9 }).bindTooltip('Trip end', { sticky: true })
  group.addLayer(start); group.addLayer(end)
  for (const seg of o.lines) {
    const poly = L.polyline([[seg.from[0], seg.from[1]], [seg.to[0], seg.to[1]]], {
      color: '#111827', weight: 6, opacity: 0.9, dashArray: '6,6'
    })
    poly.bindTooltip(`Seg ${seg.meta?.id ?? ''}`, { sticky: true })
    group.addLayer(poly)
  }
  busRouteLayer = group.addTo(map)
}, { deep: true })

watch(() => (store as any)._fitBoundsCoords, (coords) => {
  if (!coords || !Array.isArray(coords) || !coords.length) return;
  try {
    const b = L.latLngBounds(coords as any);
    if (b.isValid()) map.fitBounds(b.pad(0.12));
  } finally {
    (store as any)._fitBoundsCoords = null;
  }
}, { deep: false })

watch(() => (store as any).serviceRouteOverlay, (o) => {
  if (!o) {
    if (serviceRouteLayer) { map.removeLayer(serviceRouteLayer); serviceRouteLayer = null }
    clearColoredPolylines()
    return
  }
  if (Array.isArray(o?.polylines) && o.polylines.length) {
    setColoredPolylines(o.polylines)
    if (serviceRouteLayer) { map.removeLayer(serviceRouteLayer); serviceRouteLayer = null }
    return
  }
  if (serviceRouteLayer) { map.removeLayer(serviceRouteLayer); serviceRouteLayer = null }
  const group = L.layerGroup()
  const colors = ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444']
  o.directions.forEach((d: any, idx: number) => {
    const color = colors[idx % colors.length]
    const latlngs = (d.roadPath ?? d.points).map((p: [number, number]) => L.latLng(p[0], p[1]))
    if (Array.isArray(d.roadPath) && d.roadPath.length >= 2) {
      group.addLayer(L.polyline(latlngs, { color, weight: 5, opacity: 0.96 }))
    } else if (latlngs.length >= 2) {
      group.addLayer(L.polyline(latlngs, { color, weight: 4, opacity: 0.85, dashArray: '6,6' }))
    }
    if (latlngs.length) {
      group.addLayer(L.circleMarker(latlngs[0], { radius: 5, color: '#2563eb', weight: 2 }))
      group.addLayer(L.circleMarker(latlngs[latlngs.length-1], { radius: 5, color: '#16a34a', weight: 2 }))
    }
  })
  serviceRouteLayer = group.addTo(map)
}, { deep: true })
</script>

<template>
  <div ref="mapEl" class="w-full h-full"></div>
</template>

<!-- Global styles (not scoped) so Leaflet tooltips render correctly -->
<style>
.flood-tooltip {
  padding: 0 !important;
  border: 0;
  background: transparent;
  box-shadow: none;
}
.flood-tt {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,.12);
  padding: 10px 12px;
  font: 12px/1.35 system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial, sans-serif;
  color: #111827;
  max-width: 260px;
}
.flood-tt .tt-title { font-weight: 600; margin-bottom: 2px; }
.flood-tt .tt-subtle { color: #6b7280; font-size: 11px; margin-bottom: 8px; }
.flood-tt .tt-section { margin-top: 8px; font-weight: 600; color: #374151; }
.flood-tt .tt-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 4px;
}
.flood-tt .tt-table th,
.flood-tt .tt-table td {
  border: 1px solid #e5e7eb;
  padding: 4px 6px;
  vertical-align: top;
  font-size: 12px;
}
.flood-tt .tt-table th {
  width: 48%;
  background: #f9fafb;
  color: #374151;
  font-weight: 600;
}
</style>

<style scoped>
div { height: 100%; }
</style>

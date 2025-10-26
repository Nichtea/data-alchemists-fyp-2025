<script setup lang="ts">
import { onMounted, watch, ref } from 'vue'
import * as L from 'leaflet'
import { useAppStore } from '@/store/app'
import {
  getAllBusStops, getBusStopByCode,
  getAllFloodEvents, getFloodEventById,
} from '@/api/api'

/* ========== Emits ========== */
const emit = defineEmits<{
  (e: 'flood-click', payload: { floodId: number }): void
}>()

const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map

/* Layers */
let stopsLayer: L.LayerGroup | null = null
let floodEventsLayer: L.LayerGroup | null = null
let driveRouteLayer: L.LayerGroup | null = null
let roadSegmentLayer: L.LayerGroup | null = null
let busRouteLayer: L.LayerGroup | null = null
let serviceRouteLayer: L.LayerGroup | null = null

const store = useAppStore()

/* ================= Flood hover: cache + single-owner tooltip ================= */
const floodDetailCache = new Map<number, any>()
const floodDetailPromise = new Map<number, Promise<any>>()

let openFloodTooltipOwner: L.Layer | null = null
let floodHoverEpoch = 0

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
  const m = s.match(/^(-?\d+(\.\d+)?)\s*(m|min|mins|minute|minutes)$/)
  if (m) return Number(m[1])
  if (/^\d{1,2}:\d{2}(:\d{2})?$/.test(s)) {
    const parts = s.split(':').map(Number)
    if (parts.length === 2) return parts[0] + parts[1] / 60
    if (parts.length === 3) return parts[0] * 60 + parts[1] + parts[2] / 60
  }
  const n = Number(s)
  return Number.isFinite(n) ? n : undefined
}
function pickNumNested(obj: any, keys: string[]): number | undefined {
  const seen = new Set<any>()
  function dfs(o: any): number | undefined {
    if (!o || typeof o !== 'object' || seen.has(o)) return undefined
    seen.add(o)
    for (const k of keys) {
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
    for (const v of Object.values(o)) {
      const cand = dfs(v)
      if (cand != null) return cand
    }
    return undefined
  }
  return dfs(obj)
}
const fmtMinutes = (n: any) => Number.isFinite(+n) ? `${(+n).toFixed(2)} min` : '-'
const fmtMinutesForce = (n: any) => n === 0 || Number.isFinite(+n) ? `${(+n).toFixed(2)} min` : '-'
const fmtKm = (m: any) => Number.isFinite(+m) ? `${(+m/1000).toFixed(3)} km` : '-'

/* ============== Tooltip content ============== */
function buildFloodTooltip(detail: any, fallback: { id?: any, name?: string } = {}) {
  const id = detail?.id ?? detail?.flood_id ?? fallback?.id ?? '-'
  const roadName = detail?.road_name ?? 'Unknown'
  const roadType = detail?.road_type ?? 'unclassified'
  const lengthM  = detail?.length_m

  const t20 = pickNumNested(detail, ['time_20kmh_min','time_at_20_kmh_min','eta_20kmh_min','t20','time20'])
  const t50 = pickNumNested(detail, ['time_50kmh_min','time_at_50_kmh_min','eta_50kmh_min','t50','time50'])
  let delay = pickNumNested(detail, ['travel_delay_min','travel_delay','delay_min','delay','additional_delay_min'])
  if (delay == null && t20 != null && t50 != null) delay = Math.max(0, t20 - t50)

  return `
  <div class="flood-tt">
    <div class="tt-title">Flood details</div>
    <div class="tt-subtle">ID: ${id}</div>
    <div class="tt-section">Road segment</div>
    <table class="tt-table">
      <tr><th>Road name</th><td>${roadName}</td></tr>
      <tr><th>Type</th><td>${roadType}</td></tr>
      <tr><th>Length</th><td>${fmtKm(lengthM)}</td></tr>
    </table>
    <div class="tt-section">Traffic impact</div>
    <table class="tt-table">
      <tr><th>Time @ 20 km/h</th><td>${fmtMinutes(t20)}</td></tr>
      <tr><th>Time @ 50 km/h</th><td>${fmtMinutes(t50)}</td></tr>
      <tr><th>Travel delay</th><td>${fmtMinutesForce(delay)}</td></tr>
    </table>
  </div>`
}

/* ================= Colored service polylines (kept intact) ================= */
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

/* Stops styles + selection (kept) */
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

/* Clearers */
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
  clearRouteEndpoints()
}

/* WKT → latlngs (used elsewhere) */
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

/* Draw flooded road segment(s) from detail.geometry; returns bounds if drawn */
function renderRoadSegmentFromDetail(detail: any): L.LatLngBounds | null {
  if (!detail || typeof detail.geometry !== 'string') return null
  const lineGroups = wktToLatLngs(detail.geometry)
  if (!lineGroups.length) return null

  // clear previous
  if (roadSegmentLayer) { map.removeLayer(roadSegmentLayer); roadSegmentLayer = null }

  const group = L.layerGroup()
  // 🔴 Flooded segments styled in red, bold line
  const baseStyle: L.PolylineOptions = { color: '#dc2626', weight: 8, opacity: 0.95, lineCap: 'round', lineJoin: 'round' }
  const roadName = detail.road_name ?? 'Flooded road'
  const roadType = detail.road_type ?? '-'
  const lengthM  = Number(detail.length_m ?? 0)

  const all: L.LatLng[] = []
  for (const latlngs of lineGroups) {
    const poly = L.polyline(latlngs, baseStyle)
    poly.bindTooltip(`${roadName}`, { sticky: true })
    poly.bindPopup(`
      <div style="font-weight:600;margin-bottom:4px">${roadName}</div>
      <div>Type: ${roadType}</div>
      <div>Length: ${isFinite(lengthM) ? (lengthM/1000).toFixed(3) + ' km' : '-'}</div>
    `)
    group.addLayer(poly)
    all.push(...latlngs.map(([la, lo]) => L.latLng(la, lo)))
  }
  roadSegmentLayer = group.addTo(map)

  const b = all.length ? L.latLngBounds(all) : null
  if (b && b.isValid()) return b
  return null
}

/* Helper to fetch detail by id and draw flooded roads on click */
let clickEpoch = 0
async function drawFloodSegmentById(floodId: number) {
  const myEpoch = ++clickEpoch
  try {
    const detail = await getFloodDetailCached(Number(floodId))
    if (myEpoch !== clickEpoch) return
    const bounds = renderRoadSegmentFromDetail(detail)
    if (bounds && bounds.isValid()) map.fitBounds(bounds.pad(0.12))
  } catch {
    // swallow; tooltip already shows failure if hover triggered
  }
}

/* Pickers */
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
let renderEpoch = 0
let detailEpoch = 0

/* Async renders with epoch */
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

    // GeoJSON flood shapes
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

      // ✅ Emit flood id on click AND draw flooded roads
      geo.on('click', async () => {
        if (picked.id) {
          emit('flood-click', { floodId: Number(picked.id) })
          await drawFloodSegmentById(Number(picked.id))
        }
      })

      group.addLayer(geo)
      continue
    }

    // Point fallback
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

    // ✅ Emit flood id on click AND draw flooded roads
    marker.on('click', async () => {
      if (picked.id) {
        emit('flood-click', { floodId: Number(picked.id) })
        await drawFloodSegmentById(Number(picked.id))
      }
    })

    group.addLayer(marker)
  }

  if (epoch !== renderEpoch) return
  floodEventsLayer = group.addTo(map)
}

/* -------------------- Route endpoints (kept) -------------------- */
let routeStartMarker: L.Marker | null = null
let routeEndMarker: L.Marker | null = null
function createEndpointIcon(label: 'START' | 'END', variant: 'start' | 'end') {
  const html = `
    <div class="ep ${variant}">
      <div class="pulse"></div>
      <svg class="pin-svg" viewBox="0 0 52 72" aria-hidden="true">
        <path d="M26 0c-13.3 0-24 10.7-24 24 0 18 24 48 24 48s24-30 24-48C50 10.7 39.3 0 26 0z" />
        <circle cx="26" cy="24" r="10"></circle>
      </svg>
      <div class="badge">${label}</div>
    </div>`
  return L.divIcon({ className: 'ep-wrap', html, iconSize: [1, 1], iconAnchor: [16, 44] })
}
const startIcon = createEndpointIcon('START', 'start')
const endIcon   = createEndpointIcon('END', 'end')
function clearRouteEndpoints() {
  if (routeStartMarker) { routeStartMarker.remove(); routeStartMarker = null }
  if (routeEndMarker)   { routeEndMarker.remove();   routeEndMarker = null }
}
function setRouteEndpoints(start: {lat:number, lon:number} | null, end: {lat:number, lon:number} | null) {
  clearRouteEndpoints()
  if (start && Number.isFinite(start.lat) && Number.isFinite(start.lon)) {
    routeStartMarker = L.marker([start.lat, start.lon], {
      icon: startIcon, zIndexOffset: 1000, riseOnHover: true
    }).addTo(map).bindTooltip('Route start', { sticky: true })
  }
  if (end && Number.isFinite(end.lat) && Number.isFinite(end.lon)) {
    routeEndMarker = L.marker([end.lat, end.lon], {
      icon: endIcon, zIndexOffset: 1000, riseOnHover: true
    }).addTo(map).bindTooltip('Route end', { sticky: true })
  }
}

/* Render orchestrator */
async function renderLayers() {
  ensureMap()
  const epoch = ++renderEpoch
  ++detailEpoch

  if (store.layers.floodEvents) {
    // when flood layer on, clear other route overlays + chart
    clearAllRouteOverlays()
    ;(store as any).serviceRouteOverlay = null
    ;(store as any).showTravelTimeChart = false
  }

  if (store.layers.stops) await renderStops(epoch); else clearStopsOverlays()
  if (store.layers.floodEvents) await renderFloodEvents(epoch); else clearFloodOverlays()
}

/* Small UI control to toggle stops layer */
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
    }
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
  if (tab === 'stops') { store.layers.stops = true;  store.layers.floodEvents = false }
  else if (tab === 'flood') { store.layers.floodEvents = true; store.layers.stops = false }
  renderLayers()
})

/* ======= Other optional overlays (unchanged) ======= */
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
  clearRouteEndpoints()
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
  setRouteEndpoints({lat:o.start.lat, lon:o.start.lon}, {lat:o.end.lat, lon:o.end.lon})
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
  if (serviceRouteLayer) { map.removeLayer(serviceRouteLayer); serviceRouteLayer = null }
  clearRouteEndpoints()

  if (!o) { clearColoredPolylines(); return }

  if (Array.isArray(o?.polylines) && o.polylines.length) {
    setColoredPolylines(o.polylines)
    const first = o.polylines[0]?.path?.[0]
    const lastSeg = o.polylines[o.polylines.length - 1]
    const last = lastSeg?.path?.[lastSeg.path.length - 1]
    if (first && last) setRouteEndpoints({lat:first[0], lon:first[1]}, {lat:last[0], lon:last[1]})
    return
  }

  const group = L.layerGroup()
  const colors = ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444']
  let firstPoint: L.LatLng | null = null
  let lastPoint: L.LatLng | null = null

  o.directions.forEach((d: any, idx: number) => {
    const color = colors[idx % colors.length]
    const latlngs = (d.roadPath ?? d.points).map((p: [number, number]) => L.latLng(p[0], p[1]))
    if (!firstPoint && latlngs.length) firstPoint = latlngs[0]
    if (latlngs.length) lastPoint = latlngs[latlngs.length - 1]

    if (Array.isArray(d.roadPath) && d.roadPath.length >= 2) {
      group.addLayer(L.polyline(latlngs, { color, weight: 5, opacity: 0.96 }))
    } else if (latlngs.length >= 2) {
      group.addLayer(L.polyline(latlngs, { color, weight: 4, opacity: 0.85, dashArray: '6,6' }))
    }
  })

  serviceRouteLayer = group.addTo(map)

  if (firstPoint && lastPoint) {
    setRouteEndpoints(
      { lat: firstPoint.lat, lon: firstPoint.lng },
      { lat: lastPoint.lat,  lon: lastPoint.lng  },
    )
  }
}, { deep: true })
</script>

<template>
  <div ref="mapEl" class="w-full h-full"></div>
</template>

<style>
.flood-tooltip { padding: 0 !important; border: 0; background: transparent; box-shadow: none; }
.flood-tt {
  background: #ffffff; border: 1px solid #e5e7eb; border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,.12); padding: 10px 12px;
  font: 12px/1.35 system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial, sans-serif;
  color: #111827; max-width: 260px;
}
.flood-tt .tt-title { font-weight: 600; margin-bottom: 2px; }
.flood-tt .tt-subtle { color: #6b7280; font-size: 11px; margin-bottom: 8px; }
.flood-tt .tt-section { margin-top: 8px; font-weight: 600; color: #374151; }
.flood-tt .tt-table { width: 100%; border-collapse: collapse; margin-top: 4px; }
.flood-tt .tt-table th, .flood-tt .tt-table td { border: 1px solid #e5e7eb; padding: 4px 6px; vertical-align: top; font-size: 12px; }
.flood-tt .tt-table th { width: 48%; background: #f9fafb; color: #374151; font-weight: 600; }

/* START/END icons */
.ep-wrap { pointer-events: none; }
.ep { position: relative; transform: translate(-16px, -44px); filter: drop-shadow(0 6px 12px rgba(0,0,0,.25)); user-select: none; }
.ep .pin-svg { width: 32px; height: 44px; display: block; }
.ep.start .pin-svg path { fill: #2563eb; } .ep.start .pin-svg circle { fill: #dbeafe; }
.ep.end .pin-svg path { fill: #16a34a; } .ep.end .pin-svg circle { fill: #dcfce7; }
.ep .badge { margin-top: 4px; padding: 4px 10px; font: 12px/1.1 system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial; font-weight: 800; letter-spacing: .5px; border-radius: 999px; border: 1px solid rgba(17,24,39,.12); background: #fff; color: #111827; white-space: nowrap; text-transform: uppercase; display: inline-block; box-shadow: 0 2px 8px rgba(0,0,0,.12); }
.ep .pulse { position: absolute; left: 8px; top: 8px; width: 16px; height: 16px; border-radius: 999px; background: currentColor; opacity: .25; animation: ep-pulse 1.8s ease-out infinite; transform: scale(1); filter: blur(2px); }
.ep.start { color: #3b82f6; } .ep.end { color: #22c55e; }
@keyframes ep-pulse { 0% { opacity: .35; transform: scale(1); } 60% { opacity: .10; transform: scale(2.3); } 100% { opacity: 0; transform: scale(2.8); } }
</style>

<style scoped>
div { height: 100%; }
</style>

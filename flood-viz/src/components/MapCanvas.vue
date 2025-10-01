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

/* ================= Colored service polylines ================= */
let coloredPolylinesGroup: L.LayerGroup | null = null
function ensureColoredGroup() {
  if (!coloredPolylinesGroup) coloredPolylinesGroup = L.layerGroup().addTo(map)
}
function clearColoredPolylines() {
  if (coloredPolylinesGroup) coloredPolylinesGroup.clearLayers()
}
/** Expects [{ path:[[lat,lon],...], color:'#hex', flooded:boolean }, ... ] */
function setColoredPolylines(pl: Array<{ path:[number,number][], color:string, flooded:boolean }>) {
  ensureColoredGroup()
  clearColoredPolylines()
  if (!pl?.length) return
  const all: L.LatLngExpression[] = []
  for (const seg of pl) {
    const latlngs = seg.path.map(([lat, lon]) => [lat, lon] as [number, number])
    L.polyline(latlngs, {
      color: seg.color,
      weight: 8,
      opacity: 0.92,
      lineCap: 'round',
      lineJoin: 'round',
    }).addTo(coloredPolylinesGroup!)
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
}
function clearFloodOverlays() {
  if (floodEventsLayer) { map.removeLayer(floodEventsLayer); floodEventsLayer = null }
  if (roadSegmentLayer) { map.removeLayer(roadSegmentLayer); roadSegmentLayer = null }
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
type Mode = 'stops' | 'flood' | null
const getMode = (): Mode => (store.layers.stops ? 'stops' : store.layers.floodEvents ? 'flood' : null)

/* Async renders take an epoch and bail if it changed */
async function renderStops(epoch: number) {
  clearStopsOverlays()
  if (!store.layers.stops) return
  const stops = await getAllBusStops()
  if (epoch !== renderEpoch) return // stale result
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
    if (picked.hasGeometry && picked.geometry) {
      const feature = { type: 'Feature', geometry: picked.geometry, properties: { name: picked.name, id: picked.id } }
      const layer = L.geoJSON(feature as any, {
        style: (): L.PathOptions => ({ color: '#ef4444', weight: 3, opacity: 0.9, fillOpacity: 0.25 }),
      })
      layer.on('click', async () => {
        store.setSelectedFloodLoading(true)
        try {
          store.selectFlood(picked.id)
          const detail = await getFloodEventById(Number(picked.id))
          if (epoch !== renderEpoch) return
          store.setSelectedFlood(detail)
          store.setActiveTab('flood')
          renderRoadSegmentFromDetail(detail[0])
        } finally {
          store.setSelectedFloodLoading(false)
        }
      })
      group.addLayer(layer)
      continue
    }
    if (!isFinite(picked.lat!) || !isFinite(picked.lon!)) continue
    const marker = L.circleMarker([picked.lat!, picked.lon!], {
      radius: 6, color: '#ef4444', weight: 2, fillColor: '#fca5a5', fillOpacity: 0.9,
    }).bindTooltip(`<strong>${picked.name}</strong>`, { sticky: true })
    marker.on('click', async () => {
      store.setSelectedFloodLoading(true)
      try {
        store.selectFlood(picked.id)
        const detail = await getFloodEventById(Number(picked.id))
        if (epoch !== renderEpoch) return
        store.setSelectedFlood(detail)
        store.setActiveTab('flood')
        renderRoadSegmentFromDetail(detail)
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

  // Always clear everything first
  clearAllRouteOverlays()
  clearStopsOverlays()
  clearFloodOverlays()

  // Exclusivity: only one family active
  if (store.layers.stops) {
    store.layers.floodEvents = false
    await renderStops(epoch)
  } else if (store.layers.floodEvents) {
    store.layers.stops = false
    await renderFloodEvents(epoch)
  }
}

/* ========================= Reactivity glue ========================= */
onMounted(renderLayers)

// When either toggle changes, re-render (epoch cancels stale work)
watch(() => ({ ...store.layers }), () => renderLayers(), { deep: true })

// Also drive from tab if you use it
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

/* ======= Other optional overlays (kept; not central to this bug) ======= */
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

<style scoped>
div { height: 100%; }
</style>

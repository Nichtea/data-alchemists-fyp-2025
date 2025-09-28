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
let stopsLayer: L.LayerGroup | null = null
let floodEventsLayer: L.LayerGroup | null = null
let driveRouteLayer: L.LayerGroup | null = null

// Layer for the selected flood's road segment (from WKT)
let roadSegmentLayer: L.LayerGroup | null = null

const store = useAppStore()


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
  map = L.map(mapEl.value as HTMLDivElement, {
    center: [1.3521, 103.8198],
    zoom: 12,
    zoomControl: true,
  })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19,
  }).addTo(map)
}

function clearLayer(layer: L.Layer | null) {
  if (layer && map) map.removeLayer(layer)
}

function clearRoadSegment() {
  clearLayer(roadSegmentLayer)
  roadSegmentLayer = null
}

/**
 * Parse WKT LINESTRING/MULTILINESTRING string into Leaflet lat-lng arrays.
 * WKT order is "lon lat"; Leaflet needs [lat, lon].
 * Return: [ [ [lat,lon], ... ], ... ]
 */
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
      const lon = Number(xStr)
      const lat = Number(yStr)
      if (isFinite(lat) && isFinite(lon)) latlngs.push([lat, lon])
    }
    return latlngs
  }

  if (isMulti) {
    const inner = s.slice(s.indexOf('('))
    const groups = inner.match(/\(([^()]+)\)/g)
    if (!groups) return []
    return groups
      .map(g => g.replace(/^\(|\)$/g, ''))
      .map(extractLine)
      .filter(arr => arr.length > 0)
  } else {
    const start = s.indexOf('(')
    const end = s.lastIndexOf(')')
    if (start < 0 || end < 0 || end <= start) return []
    const inner = s.substring(start + 1, end)
    const arr = extractLine(inner)
    return arr.length ? [arr] : []
  }
}


function renderRoadSegmentFromDetail(detail: any) {
  clearRoadSegment()

  if (!detail || typeof detail.geometry !== 'string') return
  const lineGroups = wktToLatLngs(detail.geometry)
  if (!lineGroups.length) return

  const group = L.layerGroup()
  const baseStyle: L.PolylineOptions = {
    color: '#1d4ed8',
    weight: 5,
    opacity: 0.9,
    dashArray: '8,6',
  }

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

  try {
    const bounds = (group as any).getBounds?.()
    if (bounds && bounds.isValid()) map.fitBounds(bounds.pad(0.15))
  } catch {}
}

/** ---------------- Helpers for stops & floods ---------------- */

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

  // Fallback to GeoJSON point from "geom" if available
  if ((lat == null || lon == null) && e?.geom?.type && Array.isArray(e.geom.coordinates)) {
    const [lonC, latC] = e.geom.coordinates
    lat = latC
    lon = lonC
  }

  return {
    id,
    name,
    lat: lat != null ? Number(lat) : undefined,
    lon: lon != null ? Number(lon) : undefined,
    hasGeometry: Boolean(e?.geom),
    geometry: e?.geom ?? null,
    raw: e,
  }
}

/** ---------------- Mock route (kept; optional) ---------------- */

type DriveTripSegment = {
  segment_id: string
  road_name: string
  distance_m: number
  duration_s: number
  speed_limit_kmh?: number
  flooded?: boolean
  geometry: { type: 'LineString'; coordinates: [number, number][] } // [lon, lat]
}

type DriveTrip = {
  trip_id: string
  mode: 'car'
  origin: { name: string; lat: number; lon: number; time?: string | null }
  destination: { name: string; lat: number; lon: number; time?: string | null }
  segments: DriveTripSegment[]
  summary?: { distance_m?: number; duration_s?: number }
}

const mockDriveTrip: DriveTrip = {
  trip_id: 'drive_001',
  mode: 'car',
  origin: { name: 'Jurong East', lat: 1.3333, lon: 103.7430, time: '2025-09-21T02:00:00+08:00' },
  destination: { name: 'Raffles Place', lat: 1.2831, lon: 103.8510, time: null },
  segments: [
    {
      segment_id: 's1',
      road_name: 'Jurong Town Hall Rd',
      distance_m: 2200,
      duration_s: 300,
      speed_limit_kmh: 60,
      flooded: false,
      geometry: {
        type: 'LineString',
        coordinates: [
          [103.7430, 1.3333],
          [103.7465, 1.3310],
          [103.7485, 1.3285]
        ]
      }
    },
    {
      segment_id: 's2',
      road_name: 'AYE',
      distance_m: 10700,
      duration_s: 840,
      speed_limit_kmh: 80,
      flooded: true,
      geometry: {
        type: 'LineString',
        coordinates: [
          [103.7485, 1.3285],
          [103.7700, 1.3020],
          [103.8000, 1.2950],
          [103.8300, 1.2930]
        ]
      }
    },
    {
      segment_id: 's3',
      road_name: 'Shenton Way',
      distance_m: 1900,
      duration_s: 300,
      speed_limit_kmh: 50,
      flooded: false,
      geometry: {
        type: 'LineString',
        coordinates: [
          [103.8300, 1.2930],
          [103.8450, 1.2870],
          [103.8510, 1.2831]
        ]
      }
    }
  ],
  summary: { distance_m: 14800, duration_s: 1440 }
}

function toLatLngs(coords: [number, number][]): [number, number][] {
  return coords.map(([lon, lat]) => [lat, lon])
}

function escapeHtml(str: string): string {
  return str.replace(/[&<>"']/g, (m) => {
    switch (m) {
      case '&': return '&amp;'
      case '<': return '&lt;'
      case '>': return '&gt;'
      case '"': return '&quot;'
      case '\'': return '&#39;'
      default: return m
    }
  })
}

function clearDriveRoute() {
  clearLayer(driveRouteLayer)
  driveRouteLayer = null
}

function renderMockDriveRoute() {
  clearDriveRoute()
  const group = L.layerGroup()

  const start = L.circleMarker([mockDriveTrip.origin.lat, mockDriveTrip.origin.lon], {
    radius: 6, color: '#2563eb', weight: 2, fillColor: '#93c5fd', fillOpacity: 0.9,
  }).bindTooltip(`<strong>Start</strong><br/>${mockDriveTrip.origin.name}`, { sticky: true })
  group.addLayer(start)

  const end = L.circleMarker([mockDriveTrip.destination.lat, mockDriveTrip.destination.lon], {
    radius: 6, color: '#16a34a', weight: 2, fillColor: '#86efac', fillOpacity: 0.9,
  }).bindTooltip(`<strong>End</strong><br/>${mockDriveTrip.destination.name}`, { sticky: true })
  group.addLayer(end)

  for (const seg of mockDriveTrip.segments) {
    const latlngs = toLatLngs(seg.geometry.coordinates)
    const color = seg.flooded ? '#ef4444' : '#16a34a'
    const poly = L.polyline(latlngs, { color, weight: 5, opacity: 0.9 })

    const meta = {
      segment_id: seg.segment_id,
      road_name: seg.road_name,
      distance_m: seg.distance_m,
      duration_s: seg.duration_s,
      speed_limit_kmh: seg.speed_limit_kmh,
      flooded: Boolean(seg.flooded),
    }
    const jsonStr = JSON.stringify({ ...meta, geometry: seg.geometry }, null, 2)
    const html = `
      <div style="max-width:320px">
        <div style="font-weight:600;margin-bottom:4px">Segment: ${seg.segment_id}</div>
        <div>${seg.road_name}</div>
        <div>${(seg.distance_m/1000).toFixed(2)} km • ${Math.round(seg.duration_s/60)} min${seg.flooded ? ' • impacted' : ''}</div>
        <pre style="margin-top:6px;background:#f7fafc;padding:8px;border-radius:6px;max-height:200px;overflow:auto;font-size:12px">${escapeHtml(jsonStr)}</pre>
      </div>
    `
    poly.bindPopup(html)
    poly.bindTooltip(`${seg.road_name}`, { sticky: true })
    group.addLayer(poly)
  }

  driveRouteLayer = group.addTo(map)

  try {
    const bounds = (group as any).getBounds?.()
    if (bounds && bounds.isValid()) map.fitBounds(bounds.pad(0.1))
  } catch {}
}

/** ---------------- Core: render stops and floods ---------------- */

async function renderStops() {
  clearLayer(stopsLayer)
  if (!store.layers.stops) return

  const stops = await getAllBusStops()
  console.debug('[stops] fetched:', stops?.length)
  const group = L.layerGroup()

  for (const raw of stops as any[]) {
    const { lat, lon, name, code } = pickStopFields(raw)
    if (!isFinite(lat) || !isFinite(lon)) continue

    const marker = L.circleMarker([lat, lon], {
      radius: 3, color: '#0ea5e9', weight: 2, fillColor: '#38bdf8', fillOpacity: 0.9,
    })
    marker.bindTooltip(`<strong>${name || 'Stop'}</strong><br/>Code: ${code || '-'}`, { sticky: true })
    marker.on('click', async () => {
      activateStopMarker(marker)
      try {
        store.setSelectedStopLoading(true)
        store.selectStop(code || null)
        const detail = await getBusStopByCode(String(code))
        store.setSelectedStop(detail)
        store.setActiveTab('stops')
      } finally {
        store.setSelectedStopLoading(false)
      }
    })
    group.addLayer(marker)
  }
  stopsLayer = group.addTo(map)
}

async function renderFloodEvents() {
  clearLayer(floodEventsLayer)
  if (!store.layers.floodEvents) return

  const events = await getAllFloodEvents()
  console.debug('[flood] fetched events:', events?.length)
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
        try {
          store.setSelectedFloodLoading(true)
          store.selectFlood(picked.id)
          const detail = await getFloodEventById(Number(picked.id))
          console.debug('[flood] getFloodEventById detail:', detail)
          store.setSelectedFlood(detail)
          store.setActiveTab('flood')

          // Draw road segment from WKT
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
    })
    marker.bindTooltip(`<strong>${picked.name}</strong>`, { sticky: true })
    marker.on('click', async () => {
      try {
        store.setSelectedFloodLoading(true)
        store.selectFlood(picked.id)
        const detail = await getFloodEventById(Number(picked.id))
        console.debug('[flood] getFloodEventById detail:', detail)
        store.setSelectedFlood(detail)
        store.setActiveTab('flood')

        // Draw road segment from WKT
        renderRoadSegmentFromDetail(detail)
      } finally {
        store.setSelectedFloodLoading(false)
      }
    })
    group.addLayer(marker)
  }

  floodEventsLayer = group.addTo(map)
}

/**
 * Render all visible layers. This will:
 *  - ensure the map exists
 *  - (re)draw stops if enabled
 *  - (re)draw flood events if enabled
 *  - (optionally) draw the mocked route
 */
async function renderLayers() {
  ensureMap()
  await Promise.all([renderStops(), renderFloodEvents()])

  // Optional: keep the mocked driving route for demo
  //renderMockDriveRoute()
}

onMounted(renderLayers)

/**
 * Key watchers:
 * 1) When layer visibility toggles (Home.vue activateStops/activateFlood), re-render.
 * 2) When activeTab changes, also re-render (defensive: some flows only flip tab).
 * 3) When selection is cleared elsewhere, remove the road segment layer.
 */


let _mutex = false
watch(
  () => [store.layers.stops, store.layers.floodEvents] as const,
  ([stops, floods], [prevStops, prevFloods]) => {
    if (_mutex) return

    if (stops && floods) {
      _mutex = true
      if (stops !== prevStops) {
        store.layers.floodEvents = false
        floods = false
      } else if (floods !== prevFloods) {
        store.layers.stops = false
        stops = false
      } else {
        store.layers.floodEvents = false
        floods = false
      }
      _mutex = false
    }


    queueMicrotask(() => {
      console.debug('[layers] visibility changed:', { stops, floods })
      renderLayers()
    })
  },
  { flush: 'sync', deep: false }
)

watch(() => store.activeTab, () => {
  console.debug('[activeTab] changed:', store.activeTab)
  renderLayers()
}, { deep: false })

watch(() => store.selectedFlood, v => { if (!v) clearRoadSegment() }, { deep: false })




let originMarker: L.Layer | null = null
let destMarker: L.Layer | null = null
let busRouteLayer: L.LayerGroup | null = null

function clear(l: L.Layer | null) { if (l && map) map.removeLayer(l) }

// ==== 1) Highlight the nearest station to the starting/ending point
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

// ==== 2) Route coverage (connecting the start and end stations by segments)
watch(() => store.busTripOverlay, (o) => {
  if (busRouteLayer) { map.removeLayer(busRouteLayer); busRouteLayer = null }
  if (!o) return
  const group = L.layerGroup()

  // Starting and ending points
  const start = L.circleMarker([o.start.lat, o.start.lon], { radius: 6, color:'#2563eb', weight:2, fillOpacity:0.9 })
    .bindTooltip('Trip start', { sticky: true })
  const end = L.circleMarker([o.end.lat, o.end.lon], { radius: 6, color:'#16a34a', weight:2, fillOpacity:0.9 })
    .bindTooltip('Trip end', { sticky: true })
  group.addLayer(start); group.addLayer(end)

  // Draw a line for each segment
  for (const seg of o.lines) {
    const poly = L.polyline([[seg.from[0], seg.from[1]], [seg.to[0], seg.to[1]]], {
      color: '#111827', weight: 4, opacity: 0.9, dashArray: '6,6'
    })
    poly.bindTooltip(`Seg ${seg.meta?.id ?? ''}`, { sticky: true })
    group.addLayer(poly)
  }

  busRouteLayer = group.addTo(map)
}, { deep: true })


watch(() => store._mapFlyTo, (c) => {
  if (!c) return
  map.flyTo([c.lat, c.lon], Math.max(map.getZoom(), 14), { duration: 0.6 })
  // clear
  store._mapFlyTo = null as any
})

watch(() => store._fitOverlayTick, () => {
  if (!busRouteLayer) return
  const b = (busRouteLayer as any).getBounds?.()
  if (b && b.isValid()) map.fitBounds(b.pad(0.12))
})


// === 3) Bus service route (by ServiceNo, both directions)
let serviceRouteLayer: L.LayerGroup | null = null
function clearServiceRoute() {
  if (serviceRouteLayer && map) map.removeLayer(serviceRouteLayer)
  serviceRouteLayer = null
}

watch(() => (store as any).serviceRouteOverlay, (o) => {
  clearServiceRoute()
  if (!o) return
  const group = L.layerGroup()
  const colors = ['#0ea5e9', '#10b981', '#f59e0b', '#ef4444']

  o.directions.forEach((d: any, idx: number) => {
    
    const color = colors[idx % colors.length]
    const latlngs = (d.roadPath ?? d.points).map((p: [number, number]) => L.latLng(p[0], p[1]))

    if (Array.isArray(d.roadPath) && d.roadPath.length >= 2) {
      // latlngs = d.roadPath.map(([lat,lon]:[number,number]) => [lat,lon])
      group.addLayer(L.polyline(latlngs, { color, weight: 5, opacity: 0.96 }))
    } else {
      // latlngs = (d.points || []).map(([lat,lon]:[number,number]) => [lat,lon])
      if (latlngs.length >= 2) {
        group.addLayer(L.polyline(latlngs, { color, weight: 4, opacity: 0.85, dashArray: '6,6' }))
      }
    }

    // Start and end points (optional)
    if (latlngs.length) {
      group.addLayer(L.circleMarker(latlngs[0], { radius: 5, color: '#2563eb', weight: 2 }))
      group.addLayer(L.circleMarker(latlngs[latlngs.length-1], { radius: 5, color: '#16a34a', weight: 2 }))
    }
  })

  serviceRouteLayer = group.addTo(map)
  const b = (group as any).getBounds?.()
  if (b && b.isValid()) map.fitBounds(b.pad(0.12))
}, { deep: true })


</script>

<template>
  <div ref="mapEl" class="w-full h-full"></div>
</template>

<style scoped>
/* Ensure the map container fills its parent */
div { height: 100%; }
</style>

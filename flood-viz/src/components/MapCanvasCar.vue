<!-- File: src/components/MapCanvasCar.vue -->
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import * as L from 'leaflet'

interface CarRoute {
  idx: number
  label: string
  duration_s?: number
  distance_m?: number
  polylines: [number, number][][] // 多段 [[lat,lon], ...]
  flooded_segments?: [number, number][][] | null
}

const props = defineProps<{
  routes: CarRoute[]
  overallStatus?: 'clear' | 'flooded'
  simulation?: any | null
  endpoints?: { start: { lat: number, lon: number } | null, end: { lat: number, lon: number } | null }
}>()

const mapEl = ref<HTMLDivElement | null>(null)
let map: L.Map

let routesLayer: L.LayerGroup | null = null
let floodedLayer: L.LayerGroup | null = null
let endpointsLayer: L.LayerGroup | null = null

function ensureMap() {
  if (map) return
  map = L.map(mapEl.value as HTMLDivElement, { center: [1.3521, 103.8198], zoom: 12, zoomControl: true })
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap', maxZoom: 19,
  }).addTo(map)
}

function clearLayer(l: L.LayerGroup | null, assign?: (v: null) => void) {
  if (l) { map.removeLayer(l) }
  if (assign) assign(null)
}

function fmtTime(sec?: number) {
  if (!Number.isFinite(sec)) return '-'
  const m = Math.round((sec as number) / 60)
  return `${m} min`
}
function fmtDist(m?: number) {
  if (!Number.isFinite(m)) return '-'
  const k = (m as number) / 1000
  return `${k.toFixed(2)} km`
}

function renderRoutes() {
  clearLayer(routesLayer, v => routesLayer = v)
  clearLayer(floodedLayer, v => floodedLayer = v)
  clearLayer(endpointsLayer, v => endpointsLayer = v)

  const group = L.layerGroup()
  const floodGroup = L.layerGroup()
  const endGroup = L.layerGroup()

  const bounds: L.LatLng[] = []
  const palette = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']

  props.routes.forEach((r, idx) => {
    const color = palette[idx % palette.length]
    r.polylines.forEach(seg => {
      const latlngs = seg.map(([la, lo]) => L.latLng(la, lo))
      if (latlngs.length >= 2) {
        const isPrimary = idx === 0
        const line = L.polyline(latlngs, {
          color,
          weight: isPrimary ? 6 : 4,
          opacity: isPrimary ? 0.96 : 0.75,
          dashArray: isPrimary ? undefined : '6,6',
        })
        const label = `${r.label} · ${fmtTime(r.duration_s)} · ${fmtDist(r.distance_m)}`
        line.bindTooltip(label, { sticky: true })
        group.addLayer(line)
        bounds.push(...latlngs)
      }
    })

    if (r.flooded_segments && Array.isArray(r.flooded_segments)) {
      r.flooded_segments.forEach(seg => {
        const latlngs = seg.map(([la, lo]) => L.latLng(la, lo))
        if (latlngs.length >= 2) {
          floodGroup.addLayer(L.polyline(latlngs, {
            color: '#dc2626', weight: 8, opacity: 0.95
          }))
        }
      })
    }
  })

  // endpoints
  const mkEnd = (p: { lat: number, lon: number } | null, txt: string, color: string) => {
    if (!p || !Number.isFinite(p.lat) || !Number.isFinite(p.lon)) return
    const m = L.circleMarker([p.lat, p.lon], { radius: 7, weight: 3, color, fillOpacity: 0.95 })
      .bindTooltip(txt, { sticky: true })
    endGroup.addLayer(m)
    bounds.push(L.latLng(p.lat, p.lon))
  }
  mkEnd(props.endpoints?.start || null, 'Start', '#2563eb')
  mkEnd(props.endpoints?.end || null, 'End', '#16a34a')

  routesLayer = group.addTo(map)
  if (floodGroup.getLayers().length) floodedLayer = floodGroup.addTo(map)
  if (endGroup.getLayers().length) endpointsLayer = endGroup.addTo(map)

  if (bounds.length) {
    const b = L.latLngBounds(bounds)
    if (b.isValid()) map.fitBounds(b.pad(0.12))
  }
}

onMounted(() => {
  ensureMap()
  renderRoutes()
})

watch(() => [props.routes, props.overallStatus, props.endpoints], () => {
  renderRoutes()
}, { deep: true })
</script>

<template>
  <div ref="mapEl" class="w-full h-full"></div>
</template>

<style scoped>
div { height: 100%; }
</style>

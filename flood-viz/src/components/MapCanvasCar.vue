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

// 让选中路线（数组第 1 个）更突出
function polyStyle(isPrimary: boolean, color: string): L.PolylineOptions {
  return {
    color,
    weight: isPrimary ? 7 : 4,
    opacity: isPrimary ? 0.98 : 0.65,
    dashArray: isPrimary ? undefined : '6,6',
  }
}

function renderRoutes() {
  clearLayer(routesLayer, v => routesLayer = v)
  clearLayer(floodedLayer, v => floodedLayer = v)
  clearLayer(endpointsLayer, v => endpointsLayer = v)

  const group = L.layerGroup()
  const floodGroup = L.layerGroup()
  const endGroup = L.layerGroup()

  const bounds: L.LatLng[] = []
  const palette = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#0ea5e9']

  // 所有路线
  props.routes.forEach((r, idx) => {
    const color = palette[idx % palette.length]
    r.polylines.forEach(seg => {
      const latlngs = seg.map(([la, lo]) => L.latLng(la, lo))
      if (latlngs.length >= 2) {
        const isPrimary = idx === 0
        const line = L.polyline(latlngs, polyStyle(isPrimary, color))
        const label = `${r.label} · ${fmtTime(r.duration_s)} · ${fmtDist(r.distance_m)}`
        line.bindTooltip(label, { sticky: true })
        group.addLayer(line)
        bounds.push(...latlngs)

        // 若整体 flooded 但没有明确段落，则对“主路线”叠加红色提示层
        if (isPrimary && props.overallStatus === 'flooded' && !(r.flooded_segments && r.flooded_segments.length)) {
          const warn = L.polyline(latlngs, {
            color: '#dc2626',
            weight: 5,
            opacity: 0.7,
            dashArray: '2,8'
          })
          floodGroup.addLayer(warn)
        }
      }
    })

    // 明确的被淹路段（红色突出）
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

  // 起终点（更醒目的大图钉）
  const mkPin = (color: string, label: string) => L.divIcon({
    className: 'custom-pin',
    html: `
      <div style="
        display:flex;align-items:center;justify-content:center;
        width:28px;height:28px;border-radius:9999px;
        background:${color};color:#fff;font-weight:700;">
        ${label}
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14]
  })

  const mkEnd = (p: { lat: number, lon: number } | null, txt: string, color: string, label: string) => {
    if (!p || !Number.isFinite(p.lat) || !Number.isFinite(p.lon)) return
    const m = L.marker([p.lat, p.lon], { icon: mkPin(color, label) })
      .bindTooltip(txt, { sticky: true })
    endGroup.addLayer(m)
    bounds.push(L.latLng(p.lat, p.lon))
  }
  mkEnd(props.endpoints?.start || null, 'Start', '#2563eb', 'A')
  mkEnd(props.endpoints?.end || null, 'End', '#16a34a', 'B')

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
.custom-pin { filter: drop-shadow(0 2px 6px rgba(0,0,0,0.2)); border: 2px solid #fff; border-radius: 9999px; }
</style>

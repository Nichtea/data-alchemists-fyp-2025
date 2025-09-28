// src/store/app.ts
import { defineStore } from 'pinia'
import type { Mode } from '@/api/types'

export interface LayersState {
  stops: boolean
  floodEvents: boolean
  delay: boolean
  flooded: boolean
  criticality: boolean
}
export type ActiveTab = 'mobility' | 'stops' | 'routes' | 'flood'

type Coords = { lat:number; lon:number }
type HighlightRole = 'origin' | 'dest'
type HighlightStopPayload = {
  role: HighlightRole
  stop: { lat:number; lon:number; code?:string; id?:string; name?:string }
}
type BusTripOverlay = {
  tripId: number | string
  start: { lat:number; lon:number; stop_id?:string }
  end:   { lat:number; lon:number; stop_id?:string }
  lines: Array<{ from:[number,number]; to:[number,number]; meta?:any }>
  metrics?: any
} | null

export type ServiceRouteOverlay = {
  serviceNo: string
  directions: Array<{
    dir: number
    points: [number, number][]
    stopCodes: string[]
    roadPath?: [number, number][]
  }>
} | null


export const useAppStore = defineStore('app', {
  state: () => ({
    mode: 'car' as Mode,
    activeTab: 'stops' as ActiveTab,

    layers: {
      stops: true,
      floodEvents: false,
      delay: false,
      flooded: false,
      criticality: false,
    } as LayersState,

    // selections
    selectedStopCode: null as string | null,
    selectedStop: null as any | null,
    selectedStopLoading: false,

    selectedFloodId: null as number | string | null,
    selectedFlood: null as any | null,
    selectedFloodLoading: false,

    origin: null as Coords | null,
    destination: null as Coords | null,
    originStopCode: null as string | null,
    destStopCode: null as string | null,

    destinationAreaCode: null as string | null,

    // map control ticks / commands
    _mapFlyTo: null as Coords | null,
    _fitOverlayTick: 0,

    // highlights & overlays
    highlightOrigin: null as { lat:number; lon:number; name?:string; code?:string } | null,
    highlightDest:   null as { lat:number; lon:number; name?:string; code?:string } | null,
    busTripOverlay:  null as BusTripOverlay,

    serviceRouteOverlay: null as ServiceRouteOverlay,
  }),
  actions: {
    setMode(m: Mode) { this.mode = m },

    setActiveTab(t: ActiveTab) {
      this.activeTab = t
      if (t === 'stops')  this.setLayerVisible('stops', true)
      if (t === 'flood')  this.setLayerVisible('floodEvents', true)
    },

    setLayerVisible<K extends keyof LayersState>(key: K, visible: boolean) {
      if (visible) {
        if (key === 'stops')       this.layers.floodEvents = false
        if (key === 'floodEvents') this.layers.stops = false
      }
      this.layers[key] = visible
    },

    // selections
    selectStop(code: string | null) { this.selectedStopCode = code },
    setSelectedStop(data: any | null) { this.selectedStop = data },
    setSelectedStopLoading(v: boolean) { this.selectedStopLoading = v },

    selectFlood(id: number | string | null) { this.selectedFloodId = id },
    setSelectedFlood(data: any | null) { this.selectedFlood = data },
    setSelectedFloodLoading(v: boolean) { this.selectedFloodLoading = v },

    clearSelection() {
      this.selectedStopCode = null; this.selectedStop = null; this.selectedStopLoading = false
      this.selectedFloodId = null;  this.selectedFlood = null; this.selectedFloodLoading = false
    },

    // OD / area
    setOrigin(c: Coords) { this.origin = c },
    setDestination(c: Coords) { this.destination = c },
    setOriginStopCode(code: string) { this.originStopCode = code },
    setDestStopCode(code: string) { this.destStopCode = code },
    setDestinationAreaCode(area: string) { this.destinationAreaCode = area },

    // map controls
    flyTo(c: Coords) { this._mapFlyTo = c },
    fitToOverlayBounds() { this._fitOverlayTick++ },

    // highlight
    highlightStop(payload: HighlightStopPayload) {
      const { role, stop } = payload
      const v = { lat: stop.lat, lon: stop.lon, name: stop.name, code: stop.code ?? stop.id }
      if (role === 'origin') this.highlightOrigin = v
      else                   this.highlightDest = v
    },

    // overlays
    setBusTripOverlay(overlay: BusTripOverlay) { this.busTripOverlay = overlay },

    setServiceRouteOverlay(o: ServiceRouteOverlay) { this.serviceRouteOverlay = o },

    clearServiceRouteOverlay() {
      this.serviceRouteOverlay = null
    },

    clearOverlays() {
      this.highlightOrigin = null
      this.highlightDest = null
      this.busTripOverlay = null
      this.serviceRouteOverlay = null
    },
  },
})

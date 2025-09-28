// src/api/api.ts
import type {
  FeatureCollection,
  FeatureLineString,
  Scenario,
  Mode,
  DelayFeatureProps,
  CriticalityProps,
  BusImpactRow,
  SummaryKpi,
} from './types'

// ---------- configurable base & paths ----------
const API_BASE: string = "/api"

const PATHS = {
  // traffic & analytics (custom analytics endpoints; keep if your backend supports them)
  delay: '/traffic/delay',                 // GET ?mode=&scenario=&agg=&limit=
  floodedRoads: '/flood_events/roads',     // GET ?scenario=
  criticality: '/traffic/criticality',     // GET ?metric=
  busImpacts: '/bus/impacts',              // GET ?scenario=
  summary: '/traffic/summary',             // GET ?mode=&scenario=

  // bus data (your existing Flask routes)
  busStops: '/bus_stops',                                      // GET
  busStopByCode: (code: string) => `/bus_stops/${encodeURIComponent(code)}`, // GET
  busTrips: '/bus_trip',                                       // GET
  busTripById: (id: number) => `/bus_trip/${id}`,              // GET
  busTripSegments: '/bus_trip_segment',                        // GET
  busTripSegmentById: (id: number) => `/bus_trip_segment/${id}`, // GET

  // NEW: flood events (from flood_events_route)
  floodEvents: '/flood_events',                                // GET
  floodEventById: (id: number) => `/flood_events/${id}`,       // GET
  floodEventByIdLegacy: '/flood_events/id/',                   // GET

  // NEW: car trips flooded/dry (from car_trips_route)
  carTripsFlooded: '/car_trips_flooded',                       // GET
  carTripFloodedById: (id: number) => `/car_trips_flooded/${id}`, // GET
  carTripsDry: '/car_trips_dry',                               // GET
  carTripDryById: (id: number) => `/car_trips_dry/${id}`,      // GET

  // NEW: traffic max flow (from traffic_route)
  roadMaxTrafficFlow: '/road_max_traffic_flow',                // GET
  roadMaxTrafficFlowById: (id: number) => `/road_max_traffic_flow/${id}`, // GET


  busTripsDelay: '/bus_trips/delay',


  // mock fallbacks for local static files (optional)
  mockDelay: '/mock/delay_segments.json',
  mockFlooded: '/mock/flooded_roads.json',
  mockCriticality: '/mock/criticality.json',
  mockBusImpacts: '/mock/bus_impacts.json',
  mockSummary: '/mock/summary.json',
}

// ---------- tiny fetch utilities ----------
function joinURL(base: string, path: string) {
  const b = base.endsWith('/') ? base.slice(0, -1) : base
  const p = path.startsWith('/') ? path : `/${path}`
  return `${b}${p}`.replace(/([^:]\/)\/+/g, '$1')
}

function toURL(path: string, params?: Record<string, string | number | boolean | undefined>) {
  // keep /mock on the frontend (5173) so Vite serves static files
  const urlStr = path.startsWith('/mock')
    ? path                                   // same-origin, no proxy
    : joinURL(API_BASE, path)                // goes through /api proxy

  const url = new URL(urlStr, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null) url.searchParams.set(k, String(v))
    })
  }
  return url.toString()
}


async function getJSON<T>(path: string, params?: Record<string, any>): Promise<T> {
  const r = await fetch(toURL(path, params), { method: 'GET' })
  if (!r.ok) {
    const txt = await r.text().catch(() => '')
    throw new Error(`GET ${path} failed: ${r.status} ${txt}`)
  }
  return (await r.json()) as T
}

// ---------- traffic & analytics ----------
export async function getDelay(
  mode: Mode,
  scenario: Scenario,
  agg: 'segment' | 'node',
  limit: number
): Promise<{ data: FeatureCollection<FeatureLineString<DelayFeatureProps>> }> {
  try {
    const data = await getJSON<FeatureCollection<FeatureLineString<DelayFeatureProps>>>(PATHS.delay, {
      mode,
      scenario,
      agg,
      limit,
    })
    return { data }
  } catch {
    const data = await getJSON<FeatureCollection<FeatureLineString<DelayFeatureProps>>>(PATHS.mockDelay)
    return { data }
  }
}

export async function getFloodedRoads(scenario: Scenario) {
  try {
    const data = await getJSON<FeatureCollection<FeatureLineString>>(PATHS.floodedRoads, { scenario })
    return { data }
  } catch {
    const data = await getJSON<FeatureCollection<FeatureLineString>>(PATHS.mockFlooded)
    return { data }
  }
}

export async function getCriticality(metric: 'betweenness' | 'closeness') {
  try {
    const data = await getJSON<FeatureCollection<FeatureLineString<CriticalityProps>>>(PATHS.criticality, { metric })
    return { data }
  } catch {
    const data = await getJSON<FeatureCollection<FeatureLineString<CriticalityProps>>>(PATHS.mockCriticality)
    return { data }
  }
}

export async function getBusImpacts(scenario: Scenario) {
  try {
    const data = await getJSON<BusImpactRow[]>(PATHS.busImpacts, { scenario })
    return { data }
  } catch {
    const data = await getJSON<BusImpactRow[]>(PATHS.mockBusImpacts)
    return { data }
  }
}

export async function getSummary(mode: Mode, scenario: Scenario) {
  try {
    const data = await getJSON<SummaryKpi>(PATHS.summary, { mode, scenario })
    return { data }
  } catch {
    const data = await getJSON<SummaryKpi>(PATHS.mockSummary)
    return { data }
  }
}

// ---------- bus data ----------
export async function getAllBusStops() {
  return await getJSON<any[]>(PATHS.busStops)
}

export async function getBusStopByCode(stopCode: string) {
  return await getJSON<any>(PATHS.busStopByCode(stopCode))
}

export async function getAllBusTrips() {
  return await getJSON<any[]>(PATHS.busTrips)
}

export async function getBusTripById(id: number) {
  return await getJSON<any>(PATHS.busTripById(id))
}

export async function getAllBusTripSegments() {
  return await getJSON<any[]>(PATHS.busTripSegments)
}

export async function getBusTripSegmentById(id: number) {
  return await getJSON<any>(PATHS.busTripSegmentById(id))
}

// ---------- flood events ----------
export async function getAllFloodEvents() {
  return await getJSON<any[]>(PATHS.floodEvents)
}

export async function getFloodEventById(id: number) {
  try {
    return await getJSON<any>(PATHS.floodEventByIdLegacy, { flood_event_ids: id })
  } catch (e) {
    return await getJSON<any>(PATHS.floodEventById(id))
  }
}
// ---------- car trips (flooded/dry) ----------
export async function getAllCarTripsFlooded() {
  return await getJSON<any[]>(PATHS.carTripsFlooded)
}

export async function getCarTripFloodedById(id: number) {
  return await getJSON<any>(PATHS.carTripFloodedById(id))
}

export async function getAllCarTripsDry() {
  return await getJSON<any[]>(PATHS.carTripsDry)
}

export async function getCarTripDryById(id: number) {
  return await getJSON<any>(PATHS.carTripDryById(id))
}

// ---------- traffic (max flow) ----------
export async function getAllRoadMaxTrafficFlow() {
  return await getJSON<any[]>(PATHS.roadMaxTrafficFlow)
}

export async function getRoadMaxTrafficFlowById(id: number) {
  return await getJSON<any>(PATHS.roadMaxTrafficFlowById(id))
}

export async function getBusTripsDelay(
  stopId: string | number,
  endAreaCode: string,
  extra?: { // 可选参数：按需扩展
    speed_kmh?: 5 | 12 | 30 | 48
  }
): Promise<any> {
  return await getJSON<any>(PATHS.busTripsDelay, {
    stop_id: stopId,
    trip_end_area_code: endAreaCode,
    ...(extra?.speed_kmh ? { speed_kmh: extra.speed_kmh } : {})
  })
}

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

//PATHS
const PATHS = {
  // traffic & analytics (custom analytics endpoints; keep if your backend supports them)
  delay: '/traffic/delay',                 // GET ?mode=&scenario=&agg=&limit=
  floodedRoads: '/flood_events/roads',     // GET ?scenario=
  floodEventsByDateRange: '/get_flood_events_by_date_range', // GET ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
  floodLocations: '/flood_events/location',  // GET -> list of location counts
  criticality: '/traffic/criticality',     // GET ?metric=
  busImpacts: '/bus/impacts',              // GET ?scenario=
  summary: '/traffic/summary',             // GET ?mode=&scenario=
  onemapRoute: '/onemap_car_route',            // GET ?start_address=&end_address=&date=&time=
  getRoute: '/get_route',                  // NEW: OneMap PT routing via your backend
  getBusesAffected: '/get_buses_affected_by_floods', // GET ?flood_id=
  criticalSegmentsNearFlood: '/critical-segments',  // GET ?flood_id=&buffer_m=

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

// ---------- flood locations (counts) ----------
// ---------- flood locations (counts) ----------
function normalizeFloodLocationsResponse(raw: any): FloodLocationCount[] {
  // Accepts:
  // 1) [{ location, count, latitude, longitude, time_travel_delay_min, ... }, ...]  ⬅️ NEW
  // 2) [{ "Place": 3 }, ...]
  // 3) [["Place", 3], ...]
  // 4) { data: [...] } / { results: [...] }
  const src =
    Array.isArray(raw) ? raw
    : Array.isArray(raw?.data) ? raw.data
    : Array.isArray(raw?.results) ? raw.results
    : []

  // Group by location to handle duplicates (e.g., "Punggol West Flyover" appears twice)
  const byLoc = new Map<string, FloodLocationCount>()

  const upsert = (row: FloodLocationCount) => {
    const key = (row.location || '').trim()
    if (!key) return
    const prev = byLoc.get(key)
    if (!prev) {
      byLoc.set(key, { ...row })
      return
    }
    // merge rule: sum counts, take max delay, keep first lat/lon if missing
    prev.count = (prev.count || 0) + (row.count || 0)
    if (Number.isFinite(row.time_travel_delay_min)) {
      const cur = Number(prev.time_travel_delay_min ?? -Infinity)
      const nxt = Number(row.time_travel_delay_min)
      prev.time_travel_delay_min = Math.max(cur, nxt)
      if (!Number.isFinite(prev.time_travel_delay_min)) prev.time_travel_delay_min = nxt
    }
    if (!Number.isFinite(prev.latitude as number) && Number.isFinite(row.latitude as number)) prev.latitude = row.latitude
    if (!Number.isFinite(prev.longitude as number) && Number.isFinite(row.longitude as number)) prev.longitude = row.longitude
    // carry over other optional fields if useful
    prev.road_length ??= row.road_length
    prev.time_20kmh_min ??= row.time_20kmh_min
    prev.time_50kmh_min ??= row.time_50kmh_min
  }

  for (const item of src) {
    // Case 1: explicit fields from backend
    if (item && typeof item === 'object' && 'location' in item && 'count' in item) {
      upsert({
        location: String(item.location),
        count: Number(item.count) || 0,
        time_travel_delay_min: Number(item.time_travel_delay_min),
        latitude: Number(item.latitude),
        longitude: Number(item.longitude),
        road_length: Number(item.road_length),
        time_20kmh_min: Number(item.time_20kmh_min),
        time_50kmh_min: Number(item.time_50kmh_min),
      })
      continue
    }

    // Case 2: ["Place", 3]
    if (Array.isArray(item) && item.length >= 2) {
      const [loc, cnt] = item
      upsert({ location: String(loc), count: Number(cnt) || 0 })
      continue
    }

    // Case 3: { "Place": 3 }
    if (item && typeof item === 'object') {
      const entries = Object.entries(item)
      if (entries.length === 1) {
        const [loc, cnt] = entries[0]
        if (typeof loc === 'string') upsert({ location: loc, count: Number(cnt) || 0 })
      }
    }
  }

  return [...byLoc.values()]
}

export async function getFloodLocations(): Promise<FloodLocationCount[]> {
  const raw = await getJSON<any>(PATHS.floodLocations)
  return normalizeFloodLocationsResponse(raw)
}

export async function getFloodEventsByDateRange(params: {
  start_date: string; // 'YYYY-MM-DD'
  end_date: string;   // 'YYYY-MM-DD'
}) {
  // returns an array of events with geometry/metrics computed by backend
  return await getJSON<any[]>(PATHS.floodEventsByDateRange, params)
}

export async function getBusesAffectedByFloods(floodId: number) {
  // Returns an array of services; shape depends on your backend
  // e.g. [{ service_no: "190" }, { ServiceNo: "960E" }, ...]
  return await getJSON<any[]>(PATHS.getBusesAffected, { flood_id: floodId })
}

async function getJSON<T>(path: string, params?: Record<string, any>): Promise<T> {
  const r = await fetch(toURL(path, params), { method: 'GET' })
  if (!r.ok) {
    const txt = await r.text().catch(() => '')
    throw new Error(`GET ${path} failed: ${r.status} ${txt}`)
  }
  return (await r.json()) as T
}

// ---------- types for OneMap public transport route ----------

export type OneMapPtLeg = {
  mode: string
  duration?: number
  distance?: number
  from?: { name?: string; stopCode?: string; lat?: number; lon?: number }
  to?:   { name?: string; stopCode?: string; lat?: number; lon?: number }
  // Augmented by backend
  non_flooded_bus_duration?: number
  flooded_bus_duration_5kmh?: number
  flooded_bus_duration_10kmh?: number
  flooded_bus_duration_20kmh?: number
}

export type OneMapPtItinerary = {
  duration?: number
  walkTime?: number
  transitTime?: number
  waitingTime?: number
  legs?: OneMapPtLeg[]
}

export type OneMapPtResponse = {
  plan?: { itineraries?: OneMapPtItinerary[] }
  error?: string
}

// Critical Road Segments
export type Svy21LineString = {
  type: 'LineString'
  // EPSG:3414 (SVY21) x/y pairs straight from backend
  coordinates: [number, number][]
}

export type Wgs84Point = {
  type: 'Point'
  // [lon, lat] in WGS84 (backend already gives the flood_point in EPSG:4326 per your example)
  coordinates: [number, number]
}

export type CriticalSegment = {
  road_name: string
  road_type: string
  length_m: number
  centrality_score: number
  geometry: Svy21LineString
}

export type CriticalSegmentsNearFloodResponse = {
  flood_id: number
  buffer_m: number
  flood_point: Wgs84Point
  count_critical_segments: number
  critical_segments: CriticalSegment[]
}

// --- 3) Fetcher (robust against NaN in backend JSON) ---
export async function getCriticalSegmentsNearFlood(params: {
  flood_id: number | string
  buffer_m?: number | string // default 50 on backend; you can override
}): Promise<CriticalSegmentsNearFloodResponse> {
  const url = toURL(PATHS.criticalSegmentsNearFlood, {
    flood_id: params.flood_id,
    ...(params.buffer_m !== undefined ? { buffer_m: params.buffer_m } : {}),
  })

  const r = await fetch(url, { method: 'GET' })
  const rawText = await r.text()
  if (!r.ok) {
    throw new Error(`GET ${PATHS.criticalSegmentsNearFlood} failed: ${r.status} ${rawText}`)
  }

  // Backend sometimes returns bare NaN tokens (invalid JSON). Sanitize to null.
  // We do a generic replacement to be safe.
  const sanitized = rawText.replace(/\bNaN\b/g, 'null')

  let payload: CriticalSegmentsNearFloodResponse
  try {
    payload = JSON.parse(sanitized)
  } catch (e) {
    throw new Error(`Invalid JSON from critical-segments endpoint.`)
  }

  // Normalize road_name and any other nullable fields you care about
  if (Array.isArray(payload?.critical_segments)) {
    payload.critical_segments = payload.critical_segments.map((seg: any) => ({
      ...seg,
      road_name:
        typeof seg?.road_name === 'string' && seg.road_name.trim()
          ? seg.road_name
          : 'Unnamed Road',
    }))
  }

  return payload
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

// 3) Add this fetcher near your other exports
export async function getOneMapPtRoute(params: {
  start_address: string
  end_address: string
  date?: string
  time?: string
}) {
  return await getJSON<any>(PATHS.getRoute, params)
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

export type FloodLocationCount = {
  location: string
  count: number
  // optional extras (when backend provides them)
  time_travel_delay_min?: number
  latitude?: number
  longitude?: number
  road_length?: number
  time_20kmh_min?: number
  time_50kmh_min?: number
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
    speed_kmh?: 5 | 10 | 20 
  }
): Promise<any> {
  return await getJSON<any>(PATHS.busTripsDelay, {
    stop_id: stopId,
    trip_end_area_code: endAreaCode,
    ...(extra?.speed_kmh ? { speed_kmh: extra.speed_kmh } : {})
  })
}


export async function getOnemapCarRoute(params: {
  start_address: string
  end_address: string
  date?: string
  time?: string
}) {
  return await getJSON<any>(PATHS.onemapRoute, params)
}

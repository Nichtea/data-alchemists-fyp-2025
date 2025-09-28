// geocode.ts
export type Coords = { lat: number; lon: number }

/** Domain model for a bus stop item returned by your backend. */
export type BusStop = {
    id?: string | number
    code?: string
    name?: string
    lat: number
    lon: number
    distance_meters?: number
    [k: string]: any
  }

/** Parse "lat, lon" or "lat lon" or "lat:.. lon:.." into coordinates. */
export function parseLatLon(text: string): Coords | null {
    const t = text.trim()
    const mLabel = t.match(/lat\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*[, ]+\s*lon(?:g(?:itude)?)?\s*[:=]?\s*(-?\d+(?:\.\d+)?)/i)
    if (mLabel) {
      const la = Number(mLabel[1]); const lo = Number(mLabel[2])
      if (Number.isFinite(la) && Number.isFinite(lo)) return { lat: la, lon: lo }
    }
    const mSimple = t.match(/(-?\d+(?:\.\d+)?)\s*(?:,|\s)\s*(-?\d+(?:\.\d+)?)/)
    if (mSimple) {
      const la = Number(mSimple[1]); const lo = Number(mSimple[2])
      if (Number.isFinite(la) && Number.isFinite(lo)) return { lat: la, lon: lo }
    }
    return null
  }

/** OneMap (Singapore) Search API */
export async function geocodeOneMap(query: string): Promise<Coords | null> {
    const url = `https://developers.onemap.sg/commonapi/search?searchVal=${encodeURIComponent(query)}&returnGeom=Y&getAddrDetails=Y&pageNum=1`
    const res = await fetch(url, { headers: { accept: 'application/json' } })
    if (!res.ok) return null
    const data = await res.json()
    const first = data?.results?.[0]
    if (!first) return null
    const la = Number(first?.LATITUDE)
    const lo = Number(first?.LONGITUDE)
    if (!Number.isFinite(la) || !Number.isFinite(lo)) return null
    return { lat: la, lon: lo }
  }



//https://www.onemap.gov.sg/apidocs/nearbytransport


/** Call your backend to get nearest bus stops.
 * It returns an array; we normalize lat/lon and a few common fields.
 */
export async function getNearestBusStops(
    latitude: number,
    longitude: number,
    radiusInMeters = 1000
  ): Promise<BusStop[] | null> {
    const url =
      `https://www.onemap.gov.sg/api/public/nearbysvc/getNearestBusStops` +
      `?latitude=${encodeURIComponent(String(latitude))}` +
      `&longitude=${encodeURIComponent(String(longitude))}` +
      `&radius_in_meters=${encodeURIComponent(String(radiusInMeters))}`
  
    try {
      const res = await fetch(url, { headers: { accept: 'application/json' } })
      if (!res.ok) return null
      const data = await res.json()
  
      const arr = Array.isArray(data) ? data : (data?.results ?? data?.data)
      if (!Array.isArray(arr) || arr.length === 0) return null
  
      const normalized: BusStop[] = arr
        .map((r: any) => ({
          ...r,
          lat: Number(r?.lat ?? r?.latitude),
          lon: Number(r?.lon ?? r?.lng ?? r?.longitude),
          distance_meters: r?.distance_meters ?? r?.distance ?? r?.dist ?? undefined,
        }))
        .filter((r: any) => Number.isFinite(r.lat) && Number.isFinite(r.lon))
  
      return normalized.length ? normalized : null
    } catch (err) {
      console.error('getNearestBusStops failed:', err)
      return null
    }
  }
  
  /** OneMap-first geocode:
   * 1) Try direct "lat, lon" text.
   * 2) Fallback to OneMap address search.
   */
//   export async function geocodeSG(query: string): Promise<Coords | null> {
//     const parsed = parseLatLon(query)
//     if (parsed) return parsed
//     try {
//       return await geocodeOneMap(query)
//     } catch {
//       return null
//     }
//   }


/** Nominatim (global) fallback.
 * Note: browsers cannot set the 'User-Agent' header; do not try.
 * Consider adding an "&email=you@example.com" query param to be polite.
 */
export async function geocodeNominatim(query: string): Promise<Coords | null> {
    const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`
    const res = await fetch(url, { headers: { accept: 'application/json' } })
    if (!res.ok) return null
    const arr = await res.json()
    const first = arr?.[0]
    if (!first) return null
    return { lat: Number(first.lat), lon: Number(first.lon) }
  }

  export async function geocodeSG(query: string): Promise<Coords | null> {
    const parsed = parseLatLon(query)
    if (parsed) return parsed
    try {
      const om = await geocodeOneMap(query)
      if (om) return om
    } catch {}
    try {
      const nm = await geocodeNominatim(query)
      if (nm) return nm
    } catch {}
    return null
  }
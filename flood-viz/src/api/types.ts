// src/api/types.ts
export type Scenario = 'baseline' | 'worst_case'
export type Mode = 'car' | 'bus' | 'walk'

export interface DelayFeatureProps {
  segment_id: number
  baseline_min: number
  flooded_min: number
  delay_min: number
  road_class?: string
  region?: string
}
export interface CriticalityProps {
  segment_id: number
  tier: 'H' | 'M' | 'L'
  score: number
}

export type LineStringCoords = [number, number][]

export interface FeatureLineString<P = Record<string, any>> {
  type: 'Feature'
  properties: P
  geometry: {
    type: 'LineString'
    coordinates: LineStringCoords
  }
}

export interface FeatureCollection<F = FeatureLineString> {
  type: 'FeatureCollection'
  features: F[]
}

// Bus impacts
export interface BusImpactRow {
  service_id: string
  affected_segments: number
  affected_km?: number
  total_delay_min: number
}

// Summary KPI
export interface SummaryKpi {
  total_delay_min: number
  affected_ratio: number // 0..1
  top_segment?: {
    segment_id: number
    delay_min: number
  }
  impacted_bus_count?: number
}

/**
 * useTrafficData.js
 * ==================
 * React hook that fetches all traffic data from the TomTom-backed
 * backend endpoints and returns it in the exact shapes the Traffic page
 * components already expect.
 *
 * Polling intervals match backend cache TTLs:
 *   - overview / corridors / intersections / trend: every 60s
 *   - incidents: every 120s
 *
 * No new UI is added — loading/error states are surfaced via the
 * returned flags for the page to use with its existing state rendering.
 */

import { useState, useEffect, useRef, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function apiFetch(path) {
  const resp = await fetch(`${API_BASE}${path}`)
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(body?.detail?.error || body?.error || `HTTP ${resp.status}`)
  }
  return resp.json()
}

/** Map backend status → color used by the Traffic page */
const STATUS_COLOR = {
  'Free Flow': '#2F8F72',
  'Moderate':  '#F4A62A',
  'Congested': '#E5483F',
  'Severe':    '#8B0000',
  'Good':      '#2F8F72',
  'High Delay':'#E5483F',
}

/**
 * Normalise a corridor list from the backend into the shape Traffic.jsx
 * corridor table expects: { name, speed, time, status }
 */
function normCorridors(raw) {
  if (!raw?.corridors) return []
  return raw.corridors.map(c => ({
    name:   c.name,
    speed:  Math.round(c.speed),
    time:   c.time,
    status: c.status,
  }))
}

/**
 * Normalise incidents GeoJSON into the shape Traffic.jsx expects:
 * { type, location, detail, severity, time, color }
 */
function normIncidents(raw) {
  if (!raw?.features) return []
  return raw.features.slice(0, 8).map(f => {
    const p = f.properties || {}
    return {
      type:     p.type     || 'Incident',
      location: p.location || p.from || 'Unknown',
      detail:   p.detail   || p.to   || '',
      severity: p.severity || 'Low Impact',
      time:     p.time     || new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      color:    p.color    || '#8F9295',
    }
  })
}

/**
 * Normalise hourly trend into { time, speed, volume }[]
 */
function normTrend(raw) {
  if (!raw?.data) return []
  return raw.data.map(p => ({
    time:   p.time,
    speed:  p.speed,
    volume: p.volume,
  }))
}

/**
 * Normalise KPI overview into the 6-card array Traffic.jsx renders.
 * Metrics unavailable from TomTom (Volume, Queue Length) are returned as null.
 */
function normKPIs(raw) {
  if (!raw) return null
  const avgSpeed = raw.avg_speed_kmh ?? null

  return {
    avgSpeed:              avgSpeed !== null ? avgSpeed.toFixed(1) : null,
    avgDelaySeconds:       raw.avg_delay_seconds ?? 0,
    networkEfficiencyPct:  raw.network_efficiency_pct !== undefined && raw.network_efficiency_pct !== null ? Number(raw.network_efficiency_pct).toFixed(1) : null,
    travelTimeIndex:       raw.travel_time_index !== undefined && raw.travel_time_index !== null ? Number(raw.travel_time_index).toFixed(2) : null,
    congestedCorridors:    raw.congested_corridors ?? 0,
    activeIncidents:       raw.active_incidents ?? 0,
  }
}

/**
 * Normalise intersections into { name, delay, los, status }[]
 */
function normIntersections(raw) {
  if (!raw?.intersections) return []
  return raw.intersections.map(i => ({
    name:   i.name,
    delay:  i.delay,
    los:    i.los,
    status: i.status,
  }))
}

export function useTrafficData() {
  const [kpis, setKpis]               = useState(null)
  const [incidents, setIncidents]     = useState([])
  const [corridors, setCorridors]     = useState([])
  const [trend, setTrend]             = useState([])
  const [intersections, setIntersections] = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)

  const mountedRef = useRef(true)

  const fetchAll = useCallback(async () => {
    try {
      const [overviewRaw, corridorsRaw, trendRaw, intersectionsRaw] = await Promise.all([
        apiFetch('/api/traffic/overview'),
        apiFetch('/api/traffic/corridors'),
        apiFetch('/api/traffic/trend'),
        apiFetch('/api/traffic/intersections'),
      ])
      if (!mountedRef.current) return
      setKpis(normKPIs(overviewRaw))
      setCorridors(normCorridors(corridorsRaw))
      setTrend(normTrend(trendRaw))
      setIntersections(normIntersections(intersectionsRaw))
      setError(null)
    } catch (err) {
      if (!mountedRef.current) return
      console.warn('[useTrafficData] Fetch failed:', err.message)
      setError(err.message)
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [])

  const fetchIncidents = useCallback(async () => {
    try {
      const raw = await apiFetch('/api/traffic/incidents')
      if (!mountedRef.current) return
      setIncidents(normIncidents(raw))
    } catch (err) {
      console.warn('[useTrafficData] Incidents fetch failed:', err.message)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true

    // Initial load
    fetchAll()
    fetchIncidents()

    // Poll overview / corridors / trend / intersections every 60s
    const fastTimer = setInterval(fetchAll, 60_000)
    // Poll incidents every 120s
    const slowTimer = setInterval(fetchIncidents, 120_000)

    return () => {
      mountedRef.current = false
      clearInterval(fastTimer)
      clearInterval(slowTimer)
    }
  }, [fetchAll, fetchIncidents])

  return { kpis, incidents, corridors, trend, intersections, loading, error, STATUS_COLOR }
}

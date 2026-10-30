import { useRef, useEffect, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Car, Wind, Zap, Eye, EyeOff, Layers, Maximize2, RotateCcw } from 'lucide-react'
import { getDigitalTwin3DStyle } from '../../services/map/mapStyleService'
import {
  DIGITAL_TWIN_CENTER,
  HYDERABAD_BOUNDS,
} from '../../services/map/mapDataService'
import {
  addTrafficLayers,
  setTrafficVisibility,
  reloadTrafficTiles,
  buildTrafficPopup,
  TRAFFIC_LINE_LAYER_ID,
  TRAFFIC_SOURCE_ID,
  TRAFFIC_LEGEND_BUCKETS,
} from '../../services/map/trafficLayerService'
import {
  MapMarkerManager,
} from '../../services/map/markerLayerService'

/* ═══════════════════════════════════════════════════════════
   MAP INITIAL CONFIGURATION
   ═══════════════════════════════════════════════════════════ */

const INITIAL_VIEW = {
  center: DIGITAL_TWIN_CENTER,
  zoom: 11.6,
  pitch: 25,
  bearing: 0,
}

const LAYER_DEFS = [
  { id: 'traffic', label: 'Traffic Flow', icon: Car, color: '#2F8F72', desc: 'TomTom live vector tiles' },
  { id: 'energy', label: 'Energy Substations', icon: Zap, color: '#F59E0B', desc: 'TSSPDCL / TSTRANSCO Grid' },
  { id: 'aqi', label: 'AQI Sensors', icon: Wind, color: '#10B981', desc: 'TSPCB / CPCB CAAQMS Stations' },
]

const LEGEND_ITEMS = [
  { label: 'Free Flow (> 85%)', color: '#16A34A', type: 'line' },
  { label: 'Near Free (70% – 85%)', color: '#2F8F72', type: 'line' },
  { label: 'Moderate (50% – 70%)', color: '#EAB308', type: 'line' },
  { label: 'Slow (25% – 50%)', color: '#F97316', type: 'line' },
  { label: 'Congested (< 25%)', color: '#EF4444', type: 'line' },
  { label: 'Energy Substation (132-400kV)', color: '#F59E0B', type: 'node' },
  { label: 'AQI Sensor Station', color: '#10B981', type: 'sensor' },
]

/* ═══════════════════════════════════════════════════════════
   MAIN DIGITAL TWIN COMPONENT
   ═══════════════════════════════════════════════════════════ */

export default function DigitalTwinMap() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const popupRef = useRef(null)
  const markerManagerRef = useRef(null)

  const [layerState, setLayerState] = useState({
    traffic: true,
    energy: true,
    aqi: true,
  })
  const layerStateRef = useRef(layerState)
  layerStateRef.current = layerState

  const [loading, setLoading] = useState(true)
  const [trafficError, setTrafficError] = useState(false)
  const [lastUpdated, setLastUpdated] = useState('—')

  const activeCount = Object.values(layerState).filter(Boolean).length

  const toggleLayer = useCallback(id => {
    setLayerState(prev => {
      const next = { ...prev, [id]: !prev[id] }
      layerStateRef.current = next
      return next
    })
  }, [])

  /* ── Initialize Real Geospatial MapLibre Instance ── */
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const style = getDigitalTwin3DStyle()

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: style,
      center: INITIAL_VIEW.center,
      zoom: INITIAL_VIEW.zoom,
      pitch: INITIAL_VIEW.pitch,
      bearing: INITIAL_VIEW.bearing,
      minZoom: 9.5,
      maxZoom: 18,
      attributionControl: false,
      antialias: true,
      transformRequest: (url) => {
        return { url, credentials: 'omit' }
      },
    })

    const popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: true,
      maxWidth: '340px',
      className: 'sc-popup',
    })
    popupRef.current = popup

    const markerManager = new MapMarkerManager(map)
    markerManagerRef.current = markerManager

    // Idempotent setup function called on both 'load' and 'style.load'
    const setupLayers = () => {
      try {
        // 1. Add shared TomTom traffic vector layers
        addTrafficLayers(map)
        setTrafficVisibility(map, layerStateRef.current.traffic)

        // 2. Initialize and position authentic Substations & AQI markers
        markerManager.init()
        markerManager.setVisibility('energy', layerStateRef.current.energy)
        markerManager.setVisibility('aqi', layerStateRef.current.aqi)

        setLoading(false)
        setTrafficError(false)
      } catch (err) {
        console.error('[DigitalTwinMap] Error setting up layers:', err)
      }
    }

    map.on('load', setupLayers)
    map.on('style.load', setupLayers)

    // Traffic line click & hover
    map.on('mouseenter', TRAFFIC_LINE_LAYER_ID, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', TRAFFIC_LINE_LAYER_ID, () => {
      map.getCanvas().style.cursor = ''
    })
    map.on('click', TRAFFIC_LINE_LAYER_ID, e => {
      const feat = e.features?.[0]
      if (!feat) return
      popup
        .setLngLat(e.lngLat)
        .setHTML(buildTrafficPopup(feat.properties))
        .addTo(map)
    })

    // Capture source errors
    map.on('error', err => {
      if (err.sourceId === TRAFFIC_SOURCE_ID) {
        console.warn('[DigitalTwinMap] Vector tile error:', err.error)
        setTrafficError(true)
      }
    })

    // 60-second auto-reload for live vector tiles
    const refreshInterval = setInterval(() => {
      if (mapRef.current) {
        reloadTrafficTiles(mapRef.current)
      }
    }, 60000)

    // ResizeObserver for dynamic layout adjustment
    const ro = new ResizeObserver(() => {
      map.resize()
    })
    ro.observe(containerRef.current)

    mapRef.current = map

    return () => {
      clearInterval(refreshInterval)
      ro.disconnect()
      popup.remove()
      markerManager.destroy()
      markerManagerRef.current = null
      map.remove()
      mapRef.current = null
    }
  }, [])

  /* ── Sync Layer Visibility ── */
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // Traffic vector layer visibility
    setTrafficVisibility(map, layerState.traffic)

    // Substation & AQI marker visibility
    if (markerManagerRef.current) {
      markerManagerRef.current.setVisibility('energy', layerState.energy)
      markerManagerRef.current.setVisibility('aqi', layerState.aqi)
    }
  }, [layerState])

  /* ── AQI Polling (Every 90s, active only while Dashboard is viewed) ── */
  useEffect(() => {
    const abortController = new AbortController()
    let timerId = null
    let isMounted = true

    const updateAqiInPlace = (stations) => {
      if (!markerManagerRef.current || !Array.isArray(stations) || stations.length === 0) return
      const aqiMarkers = markerManagerRef.current.markers.filter(m => m.id === 'aqi')
      aqiMarkers.forEach(item => {
        const lngLat = item.marker.getLngLat()
        let nearestStation = null
        let minDist = Infinity
        for (const s of stations) {
          const d2 = (s.lon - lngLat.lng) ** 2 + (s.lat - lngLat.lat) ** 2
          if (d2 < minDist) {
            minDist = d2
            nearestStation = s
          }
        }
        if (nearestStation && minDist < 0.1) {
          const inner = item.container?.querySelector('.sc-aqi-marker-inner')
          if (inner) {
            const circle = inner.querySelector('div')
            if (circle) {
              if (nearestStation.color) {
                circle.style.background = nearestStation.color
                circle.style.boxShadow = `0 4px 12px ${nearestStation.color}66`
              }
              const aqiSpan = circle.querySelector('span')
              if (aqiSpan && nearestStation.aqi !== null && nearestStation.aqi !== undefined) {
                aqiSpan.textContent = String(nearestStation.aqi)
              }
            }
          }
          const popup = item.marker.getPopup()
          if (popup) {
            popup.setHTML(`
              <div style="font-family: var(--font-body, system-ui); min-width: 250px; padding: 2px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                  <span style="font-size: 0.65rem; font-weight: 700; color: ${nearestStation.color || '#10B981'}; text-transform: uppercase;
                    letter-spacing: 0.06em; font-family: var(--font-mono); background: ${(nearestStation.color || '#10B981')}18; padding: 2px 8px; border-radius: 4px;">
                    ${nearestStation.category || 'MODERATE'} AIR QUALITY
                  </span>
                  <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${nearestStation.provider_name || 'TSPCB CAAQMS'}</span>
                </div>
                <div style="font-size: 0.92rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
                  ${nearestStation.station_name || nearestStation.area}
                </div>
                <div style="display: flex; align-items: baseline; gap: 8px; margin: 8px 0;">
                  <span style="font-size: 1.8rem; font-weight: 800; color: ${nearestStation.color || '#10B981'}; font-family: var(--font-heading); line-height: 1;">
                    ${nearestStation.aqi}
                  </span>
                  <span style="font-size: 0.72rem; color: #64748B; font-weight: 600;">AQI Index · Live Telemetry</span>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.68rem; background: #F8FAFC;
                  padding: 6px 8px; border-radius: 4px; font-family: var(--font-mono); border: 1px solid #E2E8F0;">
                  <div>PM2.5: <strong>${nearestStation['PM2.5'] ?? '—'} µg/m³</strong></div>
                  <div>PM10: <strong>${nearestStation['PM10'] ?? '—'} µg/m³</strong></div>
                  <div>NO₂: <strong>${nearestStation['NO2'] ?? '—'} ppb</strong></div>
                  <div>SO₂: <strong>${nearestStation['SO2'] ?? '—'} ppb</strong></div>
                </div>
                <div style="margin-top: 6px; font-size: 0.62rem; color: #8F9295; font-family: var(--font-mono);">
                  Coordinates: ${Number(nearestStation.lat).toFixed(4)}°N, ${Number(nearestStation.lon).toFixed(4)}°E
                </div>
              </div>
            `)
          }
        }
      })
    }

    const pollAqi = async () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
        return
      }
      try {
        const resp = await fetch('/api/v1/pollution/current', { signal: abortController.signal })
        if (!resp.ok) return
        const json = await resp.json()
        if (!isMounted) return

        if (json?.stations) {
          updateAqiInPlace(json.stations)
        }
        if (json?.timestamp) {
          const d = new Date(json.timestamp)
          const timeStr = !isNaN(d.getTime())
            ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : json.timestamp
          setLastUpdated(timeStr)
        }
      } catch (err) {
        if (err.name === 'AbortError') return
        console.warn('[DigitalTwinMap] AQI poll error; keeping last good readings:', err)
      }
    }

    // Initial fetch once map layers are loaded
    pollAqi()

    // 90s cadence
    timerId = setInterval(pollAqi, 90000)

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        pollAqi()
        if (timerId) clearInterval(timerId)
        timerId = setInterval(pollAqi, 90000)
      } else {
        if (timerId) clearInterval(timerId)
        timerId = null
      }
    }

    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      isMounted = false
      abortController.abort()
      if (timerId) clearInterval(timerId)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [])

  /* ── Map Navigation Controls ── */
  const handleZoomIn = useCallback(() => {
    mapRef.current?.zoomIn({ duration: 300 })
  }, [])

  const handleZoomOut = useCallback(() => {
    mapRef.current?.zoomOut({ duration: 300 })
  }, [])

  const handleResetNorth = useCallback(() => {
    mapRef.current?.resetNorthPitch({ duration: 500 })
  }, [])

  const handleRecenter = useCallback(() => {
    mapRef.current?.flyTo({
      center: INITIAL_VIEW.center,
      zoom: INITIAL_VIEW.zoom,
      pitch: INITIAL_VIEW.pitch,
      bearing: 0,
      duration: 1000,
    })
  }, [])

  const handleFitBounds = useCallback(() => {
    mapRef.current?.fitBounds(HYDERABAD_BOUNDS, {
      padding: { top: 40, bottom: 40, left: 40, right: 40 },
      duration: 1200,
    })
  }, [])

  /* ═══════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════ */

  return (
    <div
      style={{
        background: 'var(--bg-card, #FFFFFF)',
        border: '1px solid var(--border-card, #EAE6DF)',
        borderRadius: 'var(--radius-lg, 14px)',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-card, 0 4px 18px rgba(0,0,0,0.04))',
      }}
    >
      {/* ── Header ── */}
      <div
        style={{
          padding: '16px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--border-divider, #F1F5F9)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '2px' }}>
            <h3
              style={{
                fontSize: '0.88rem',
                fontWeight: 700,
                color: 'var(--text-primary, #17212B)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                fontFamily: 'var(--font-heading, "Inter", sans-serif)',
              }}
            >
              CITY DIGITAL TWIN — HYDERABAD GEOSPATIAL INTELLIGENCE
            </h3>
            <span
              style={{
                padding: '3px 10px',
                borderRadius: 'var(--radius-full, 9999px)',
                fontSize: '0.62rem',
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                background: 'var(--accent-traffic-dim, rgba(47,143,114,0.1))',
                color: 'var(--accent-traffic, #2F8F72)',
                border: '1px solid rgba(47,143,114,0.2)',
                letterSpacing: '0.04em',
              }}
            >
              REAL GEODATA ACTIVE
            </span>
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--text-muted, #8F9295)', lineHeight: 1.4 }}>
            Geospatial synchronization with TSSPDCL Grid, TSPCB CAAQMS Stations & GHMC Arterial Networks.
          </p>
        </div>

        {/* Live Status Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              background: trafficError ? '#FEF2F2' : '#F0FDF4',
              border: `1px solid ${trafficError ? '#FECACA' : '#BBF7D0'}`,
              borderRadius: '6px',
              fontSize: '0.68rem',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              color: trafficError ? '#DC2626' : '#16A34A',
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: trafficError ? '#DC2626' : '#16A34A',
                display: 'inline-block',
              }}
            />
            {trafficError
              ? 'Traffic data unavailable'
              : `Live: TomTom | updated ${lastUpdated}`}
          </div>
        </div>
      </div>

      {/* ── Map Viewport ── */}
      <div style={{ position: 'relative', height: '520px', width: '100%' }}>
        <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

        {/* Loading Overlay */}
        {loading && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(247, 244, 236, 0.88)',
              zIndex: 5,
            }}
          >
            <div
              style={{
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-primary, #17212B)',
                letterSpacing: '0.06em',
                fontWeight: 700,
              }}
            >
              LOADING HYDERABAD GEOSPATIAL LAYERS…
            </div>
          </div>
        )}

        {/* ── Left: Active Layers Panel ── */}
        <div
          style={{
            position: 'absolute',
            top: '16px',
            left: '16px',
            background: 'var(--bg-card, #FFFFFF)',
            border: '1px solid var(--border-default, #E2E8F0)',
            borderRadius: '10px',
            padding: '14px 16px',
            width: '210px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
            zIndex: 10,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '12px',
            }}
          >
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 700,
                color: 'var(--text-primary, #17212B)',
                letterSpacing: '0.08em',
                fontFamily: 'var(--font-mono)',
              }}
            >
              ACTIVE LAYERS
            </span>
            <span
              style={{
                fontSize: '0.62rem',
                color: 'var(--text-muted, #8F9295)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
              }}
            >
              {activeCount} / 3
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {LAYER_DEFS.map(layer => {
              const Icon = layer.icon
              const active = layerState[layer.id]
              return (
                <div
                  key={layer.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '4px 0',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Icon size={15} color={active ? layer.color : '#94A3B8'} strokeWidth={2} />
                    <div>
                      <div
                        style={{
                          fontSize: '0.72rem',
                          color: active ? 'var(--text-primary, #17212B)' : '#94A3B8',
                          fontWeight: active ? 600 : 400,
                        }}
                      >
                        {layer.label}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => toggleLayer(layer.id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: active ? 'var(--text-secondary, #64748B)' : '#94A3B8',
                      padding: '2px',
                      display: 'flex',
                    }}
                    title={active ? `Hide ${layer.label}` : `Show ${layer.label}`}
                  >
                    {active ? <Eye size={15} /> : <EyeOff size={15} />}
                  </button>
                </div>
              )
            })}
          </div>

          <div
            style={{
              marginTop: '12px',
              paddingTop: '10px',
              borderTop: '1px solid var(--border-divider, #F1F5F9)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.65rem',
              color: 'var(--text-muted, #8F9295)',
              fontFamily: 'var(--font-mono)',
              fontWeight: 600,
              letterSpacing: '0.04em',
            }}
          >
            <Layers size={12} /> 3 GEOSPATIAL FEEDS
          </div>
        </div>

        {/* ── Right: Map Floating Navigation Controls ── */}
        <div
          style={{
            position: 'absolute',
            right: '16px',
            top: '50%',
            transform: 'translateY(-50%)',
            display: 'flex',
            flexDirection: 'column',
            gap: '2px',
            background: 'var(--bg-card, #FFFFFF)',
            border: '1px solid var(--border-default, #E2E8F0)',
            borderRadius: '8px',
            overflow: 'hidden',
            boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
            zIndex: 10,
          }}
        >
          <button
            title="Reset North"
            onClick={handleResetNorth}
            style={{
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              borderBottom: '1px solid var(--border-divider, #F1F5F9)',
              fontSize: '0.82rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
            }}
          >
            N
          </button>
          <button
            title="Zoom In"
            onClick={handleZoomIn}
            style={{
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              borderBottom: '1px solid var(--border-divider, #F1F5F9)',
              fontSize: '1.1rem',
            }}
          >
            +
          </button>
          <button
            title="Zoom Out"
            onClick={handleZoomOut}
            style={{
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              borderBottom: '1px solid var(--border-divider, #F1F5F9)',
              fontSize: '1.1rem',
            }}
          >
            −
          </button>
          <button
            title="Recenter to Central Hyderabad"
            onClick={handleRecenter}
            style={{
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              borderBottom: '1px solid var(--border-divider, #F1F5F9)',
              fontSize: '1rem',
            }}
          >
            <RotateCcw size={14} />
          </button>
          <button
            title="Fit Entire Hyderabad Outer Ring Road"
            onClick={handleFitBounds}
            style={{
              width: 36,
              height: 36,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              fontSize: '1rem',
            }}
          >
            <Maximize2 size={14} />
          </button>
        </div>

        {/* ── Bottom: Floating Pill Legend ── */}
        <div
          style={{
            position: 'absolute',
            bottom: '16px',
            left: '50%',
            transform: 'translateX(-50%)',
            display: 'flex',
            alignItems: 'center',
            gap: '18px',
            background: 'var(--bg-card, #FFFFFF)',
            border: '1px solid var(--border-default, #E2E8F0)',
            borderRadius: 'var(--radius-full, 9999px)',
            padding: '8px 22px',
            boxShadow: '0 4px 18px rgba(0,0,0,0.1)',
            zIndex: 10,
            flexWrap: 'wrap',
          }}
        >
          {LEGEND_ITEMS.map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {item.type === 'line' && (
                <div
                  style={{
                    width: 16,
                    height: 3.5,
                    borderRadius: 2,
                    background: item.color,
                  }}
                />
              )}
              {item.type === 'node' && (
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: item.color,
                  }}
                />
              )}
              {item.type === 'sensor' && (
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: '50%',
                    background: item.color,
                  }}
                />
              )}
              <span
                style={{
                  fontSize: '0.65rem',
                  color: 'var(--text-secondary, #64748B)',
                  fontWeight: 600,
                  fontFamily: 'var(--font-mono)',
                  letterSpacing: '0.02em',
                }}
              >
                {item.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

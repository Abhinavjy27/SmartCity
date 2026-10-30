import { useRef, useEffect, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Plus, Minus, LocateFixed, Maximize2 } from 'lucide-react'
import { getTrafficMapStyle } from '../../services/map/mapStyleService'
import {
  HYDERABAD_CENTER,
  HYDERABAD_BOUNDS,
} from '../../services/map/mapDataService'
import {
  addTrafficLayers,
  reloadTrafficTiles,
  buildTrafficPopup,
  TRAFFIC_LINE_LAYER_ID,
  TRAFFIC_SOURCE_ID,
  TRAFFIC_LEGEND_BUCKETS,
} from '../../services/map/trafficLayerService'

/* ═══════════════════════════════════════════════════════════
   MAP CONFIGURATION
   ═══════════════════════════════════════════════════════════ */

const INITIAL_VIEW = {
  center: [78.4450, 17.4200],
  zoom: 11.75,
  pitch: 0,
  bearing: 0,
}

/* ═══════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════ */

export default function TrafficIntelligenceMap() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const popupRef = useRef(null)
  const [loading, setLoading] = useState(true)
  const [tileError, setTileError] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(() => new Date().toLocaleTimeString())

  /* ── Initialize MapLibre GL ── */
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const style = getTrafficMapStyle()

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

    // Idempotent setup called on 'load' and on every 'style.load'
    const setupLayers = () => {
      try {
        addTrafficLayers(map)
        setLastUpdated(new Date().toLocaleTimeString())
        setTileError(false)
        setLoading(false)
      } catch (err) {
        console.error('[TrafficIntelligenceMap] Error setting up traffic layers:', err)
      }
    }

    map.on('load', setupLayers)
    map.on('style.load', setupLayers)

    /* ── Hover & Click on Vector Traffic Lines ── */
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

    // Listen for source errors
    map.on('error', err => {
      if (err.sourceId === TRAFFIC_SOURCE_ID) {
        console.warn('[TrafficIntelligenceMap] Vector tile source error:', err.error)
        setTileError(true)
      }
    })

    // 60-second auto-reload for live vector tiles
    const refreshInterval = setInterval(() => {
      if (mapRef.current) {
        reloadTrafficTiles(mapRef.current)
        setLastUpdated(new Date().toLocaleTimeString())
      }
    }, 60000)

    // ResizeObserver
    const ro = new ResizeObserver(() => {
      map.resize()
    })
    ro.observe(containerRef.current)

    mapRef.current = map

    return () => {
      clearInterval(refreshInterval)
      ro.disconnect()
      popup.remove()
      map.remove()
      mapRef.current = null
    }
  }, [])

  /* ── Map Navigation Handlers ── */
  const handleZoomIn = useCallback(() => {
    mapRef.current?.zoomIn({ duration: 300 })
  }, [])

  const handleZoomOut = useCallback(() => {
    mapRef.current?.zoomOut({ duration: 300 })
  }, [])

  const handleRecenter = useCallback(() => {
    mapRef.current?.flyTo({
      center: INITIAL_VIEW.center,
      zoom: INITIAL_VIEW.zoom,
      pitch: 0,
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
        position: 'relative',
      }}
    >
      <div style={{ position: 'relative', height: '540px', width: '100%' }}>
        <div ref={containerRef} style={{ position: 'absolute', inset: 0 }} />

        {/* Loading Spinner */}
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
              LOADING TOMTOM TRAFFIC FLOW TILES…
            </div>
          </div>
        )}

        {/* Tile error or unavailable banner */}
        {tileError && !loading && (
          <div
            style={{
              position: 'absolute',
              top: 16,
              right: 16,
              background: '#FEF2F2',
              border: '1px solid #FECACA',
              borderRadius: 6,
              padding: '6px 14px',
              fontSize: '0.68rem',
              fontFamily: 'var(--font-mono)',
              color: '#DC2626',
              fontWeight: 700,
              zIndex: 12,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            }}
          >
            ⚠ Traffic data unavailable — upstream proxy error
          </div>
        )}

        {/* ── Top-Left: Flow Speeds Legend ── */}
        <div
          style={{
            position: 'absolute',
            top: '16px',
            left: '16px',
            background: 'rgba(23, 33, 43, 0.94)',
            backdropFilter: 'blur(8px)',
            borderRadius: '10px',
            padding: '14px 16px',
            minWidth: '220px',
            color: '#FFFFFF',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
            zIndex: 10,
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <div
            style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em',
              marginBottom: '10px',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>FLOW SPEEDS</span>
              <span
                style={{
                  fontSize: '0.58rem',
                  background: 'rgba(47,143,114,0.25)',
                  color: '#2F8F72',
                  padding: '1px 6px',
                  borderRadius: 4,
                  letterSpacing: '0.06em',
                }}
              >
                LIVE
              </span>
            </div>
            <span
              style={{
                fontSize: '0.58rem',
                color: 'rgba(203,213,225,0.7)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              {lastUpdated}
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {TRAFFIC_LEGEND_BUCKETS.map(item => (
              <div
                key={item.label}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                <div
                  style={{
                    width: 14,
                    height: 3.5,
                    borderRadius: 2,
                    background: item.color,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: '0.63rem',
                    color: '#CBD5E1',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {item.label}
                </span>
              </div>
            ))}
          </div>

          <div
            style={{
              marginTop: 10,
              paddingTop: 8,
              borderTop: '1px solid rgba(255,255,255,0.08)',
              fontSize: '0.58rem',
              color: 'rgba(203,213,225,0.6)',
              fontFamily: 'var(--font-mono)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>TomTom Vector Flow Tiles</span>
            <span>60s TTL</span>
          </div>
        </div>

        {/* ── Bottom-Right: Map Floating Navigation Controls ── */}
        <div
          style={{
            position: 'absolute',
            right: '16px',
            bottom: '16px',
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
            title="Zoom In"
            onClick={handleZoomIn}
            style={{
              width: 34,
              height: 34,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              borderBottom: '1px solid var(--border-divider, #F1F5F9)',
              transition: 'background 0.15s ease',
            }}
          >
            <Plus size={15} />
          </button>
          <button
            title="Zoom Out"
            onClick={handleZoomOut}
            style={{
              width: 34,
              height: 34,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              borderBottom: '1px solid var(--border-divider, #F1F5F9)',
              transition: 'background 0.15s ease',
            }}
          >
            <Minus size={15} />
          </button>
          <button
            title="Recenter Map"
            onClick={handleRecenter}
            style={{
              width: 34,
              height: 34,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              borderBottom: '1px solid var(--border-divider, #F1F5F9)',
              transition: 'background 0.15s ease',
            }}
          >
            <LocateFixed size={15} />
          </button>
          <button
            title="Fit Entire Hyderabad Outer Ring Road"
            onClick={handleFitBounds}
            style={{
              width: 34,
              height: 34,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'var(--bg-card, #FFFFFF)',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-secondary, #64748B)',
              transition: 'background 0.15s ease',
            }}
          >
            <Maximize2 size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}

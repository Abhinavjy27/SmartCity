import { useRef, useEffect, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Plus, Minus, LocateFixed, Maximize2 } from 'lucide-react'
import { getTrafficMapStyle } from '../../services/map/mapStyleService'
import {
  HYDERABAD_CENTER,
  HYDERABAD_BOUNDS,
  REAL_TRAFFIC_FLOWS,
} from '../../services/map/mapDataService'

/* ═══════════════════════════════════════════════════════════
   MAP CONFIGURATION
   ═══════════════════════════════════════════════════════════ */

const INITIAL_VIEW = {
  center: [78.4450, 17.4200],
  zoom: 11.75,
  pitch: 0,
  bearing: 0,
}

const MAP_LEGEND = [
  { label: 'Free Flow (>50 km/h)', color: '#2F8F72' },
  { label: 'Moderate (30-50 km/h)', color: '#EAB308' },
  { label: 'Congested (15-30 km/h)', color: '#EF4444' },
  { label: 'Severe (<15 km/h)', color: '#8B0000' },
]

/* ═══════════════════════════════════════════════════════════
   POPUP BUILDER (Traffic Flow Corridors)
   ═══════════════════════════════════════════════════════════ */

function buildCorridorPopup(props) {
  const color = props.color || '#2F8F72'
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 230px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: ${color}; text-transform: uppercase; letter-spacing: 0.06em; font-family: var(--font-mono); background: ${color}15; padding: 2px 8px; border-radius: 4px;">
          ${props.statusLabel || props.status}
        </span>
        <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${props.corridor || 'Hyderabad'}</span>
      </div>
      <div style="font-size: 0.88rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        ${props.road || props.name}
      </div>
      <p style="font-size: 0.7rem; color: #64748B; margin-bottom: 8px; line-height: 1.35;">
        ${props.description || ''}
      </p>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #F8FAFC; padding: 8px 10px; border-radius: 6px; font-size: 0.72rem; border: 1px solid #E2E8F0;">
        <div>
          <div style="color: #8F9295; font-size: 0.6rem; font-family: var(--font-mono);">AVG SPEED</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: ${color}; font-family: var(--font-heading);">${props.speed} <span style="font-size: 0.65rem; font-weight: 400;">km/h</span></div>
        </div>
        <div>
          <div style="color: #8F9295; font-size: 0.6rem; font-family: var(--font-mono);">LANES / VOL</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: #17212B; font-family: var(--font-heading);">${props.lanes || 6} <span style="font-size: 0.65rem; font-weight: 400;">Lanes</span></div>
        </div>
      </div>
    </div>
  `
}

/* ═══════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════ */

export default function TrafficIntelligenceMap() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const popupRef = useRef(null)
  const [loading, setLoading] = useState(true)

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
    })

    const popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: true,
      maxWidth: '340px',
      className: 'sc-popup',
    })
    popupRef.current = popup

    map.on('load', () => {
      /* ── Traffic Flow GeoJSON Source & Crisp Speed Layers ── */
      map.addSource('traffic-flows', {
        type: 'geojson',
        data: REAL_TRAFFIC_FLOWS,
      })

      // Traffic casing glow
      map.addLayer({
        id: 'flow-casing',
        type: 'line',
        source: 'traffic-flows',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': [
            'match',
            ['get', 'status'],
            'free', '#2F8F72',
            'moderate', '#EAB308',
            'congested', '#EF4444',
            'severe', '#8B0000',
            '#8F9295',
          ],
          'line-width': ['interpolate', ['linear'], ['zoom'], 10, 6, 14, 12],
          'line-opacity': 0.25,
        },
      })

      // Solid flow line
      map.addLayer({
        id: 'flow-line',
        type: 'line',
        source: 'traffic-flows',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': [
            'match',
            ['get', 'status'],
            'free', '#2F8F72',
            'moderate', '#EAB308',
            'congested', '#EF4444',
            'severe', '#8B0000',
            '#8F9295',
          ],
          'line-width': ['interpolate', ['linear'], ['zoom'], 10, 3.5, 14, 6],
          'line-opacity': 0.95,
        },
      })

      /* ── Click & Hover Events on Traffic Corridors ── */
      map.on('mouseenter', 'flow-line', e => {
        map.getCanvas().style.cursor = 'pointer'
        const fid = e.features?.[0]?.properties?.id
        if (fid) {
          map.setPaintProperty('flow-line', 'line-width', [
            'case',
            ['==', ['get', 'id'], fid],
            8,
            ['interpolate', ['linear'], ['zoom'], 10, 3.5, 14, 6],
          ])
        }
      })

      map.on('mouseleave', 'flow-line', () => {
        map.getCanvas().style.cursor = ''
        map.setPaintProperty('flow-line', 'line-width', [
          'interpolate',
          ['linear'],
          ['zoom'],
          10,
          3.5,
          14,
          6,
        ])
      })

      map.on('click', 'flow-line', e => {
        const feat = e.features?.[0]
        if (!feat) return
        popup
          .setLngLat(e.lngLat)
          .setHTML(buildCorridorPopup(feat.properties))
          .addTo(map)
      })

      setLoading(false)
    })

    mapRef.current = map

    return () => {
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
              INITIALIZING HYDERABAD TRAFFIC GIS ENGINE…
            </div>
          </div>
        )}

        {/* ── Top-Left: Clean Flow Speeds Legend ── */}
        <div
          style={{
            position: 'absolute',
            top: '16px',
            left: '16px',
            background: 'rgba(23, 33, 43, 0.94)',
            backdropFilter: 'blur(8px)',
            borderRadius: '10px',
            padding: '14px 16px',
            minWidth: '170px',
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
              gap: '6px',
            }}
          >
            <span>FLOW SPEEDS</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {MAP_LEGEND.map(item => (
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
                    fontSize: '0.66rem',
                    color: '#CBD5E1',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {item.label}
                </span>
              </div>
            ))}
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

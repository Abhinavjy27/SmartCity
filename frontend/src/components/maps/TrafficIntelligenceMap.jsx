import { useRef, useEffect, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Plus, Minus, LocateFixed, Check, Maximize2, ShieldAlert, Video, AlertTriangle, Construction, Car } from 'lucide-react'
import { getTrafficMapStyle } from '../../services/map/mapStyleService'
import {
  HYDERABAD_CENTER,
  HYDERABAD_BOUNDS,
  REAL_TRAFFIC_FLOWS,
  REAL_INCIDENTS,
  REAL_CAMERAS,
  REAL_BOTTLENECKS,
  REAL_ROAD_CLOSURES,
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

const LAYER_DEFS = [
  { id: 'flow', label: 'Traffic Flow', checked: true, icon: Car },
  { id: 'incidents', label: 'Active Incidents', checked: true, icon: AlertTriangle },
  { id: 'cameras', label: 'Surveillance Cameras', checked: true, icon: Video },
  { id: 'bottlenecks', label: 'Bottleneck Hotspots', checked: true, icon: ShieldAlert },
  { id: 'closures', label: 'Road Closures', checked: true, icon: Construction },
]

const MAP_LEGEND = [
  { label: 'Free Flow (>50 km/h)', color: '#2F8F72' },
  { label: 'Moderate (30-50 km/h)', color: '#EAB308' },
  { label: 'Congested (15-30 km/h)', color: '#EF4444' },
  { label: 'Severe (<15 km/h)', color: '#8B0000' },
]

/* ═══════════════════════════════════════════════════════════
   POPUP BUILDERS
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

function buildIncidentPopup(props) {
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 240px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: ${props.color}; background: ${props.color}15; padding: 2px 8px; border-radius: 4px; font-family: var(--font-mono);">
          ⚠ ${props.type}
        </span>
        <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${props.time}</span>
      </div>
      <div style="font-size: 0.88rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        ${props.name}
      </div>
      <div style="font-size: 0.72rem; font-weight: 600; color: #475569; margin-bottom: 6px;">
        📍 ${props.location}
      </div>
      <div style="font-size: 0.7rem; color: #64748B; margin-bottom: 8px; line-height: 1.4;">
        ${props.detail}
      </div>
      <div style="background: #F8FAFC; padding: 6px 8px; border-radius: 4px; border: 1px solid #E2E8F0; font-size: 0.65rem; color: #1E293B;">
        <span style="color: #64748B; font-weight: 600;">Response:</span> ${props.actionRequired}
      </div>
    </div>
  `
}

function buildCameraPopup(props) {
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 220px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: #2F8F72; font-family: var(--font-mono); background: rgba(47,143,114,0.1); padding: 2px 8px; border-radius: 4px;">
          ● LIVE STREAM
        </span>
        <span style="font-size: 0.65rem; color: #64748B; font-family: var(--font-mono);">${props.resolution} @ ${props.fps}fps</span>
      </div>
      <div style="font-size: 0.85rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        📹 ${props.name}
      </div>
      <div style="font-size: 0.72rem; color: #64748B; margin-bottom: 6px;">Location: <strong>${props.location}</strong></div>
      <div style="font-size: 0.68rem; color: #475569; background: #F8FAFC; padding: 6px 8px; border-radius: 4px; border: 1px solid #E2E8F0;">
        Feed Type: <strong>${props.type}</strong><br/>
        Police Command & Control Center Connected
      </div>
    </div>
  `
}

function buildBottleneckPopup(props) {
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 230px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: #DC2626; font-family: var(--font-mono); background: #FEE2E2; padding: 2px 8px; border-radius: 4px;">
          CHOKE POINT
        </span>
        <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${props.los}</span>
      </div>
      <div style="font-size: 0.88rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        🛑 ${props.name}
      </div>
      <div style="font-size: 0.72rem; color: #64748B; margin-bottom: 8px;">Location: <strong>${props.location}</strong></div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; background: #FEF2F2; padding: 8px 10px; border-radius: 6px; border: 1px solid #FECACA; margin-bottom: 8px;">
        <div>
          <div style="color: #991B1B; font-size: 0.6rem; font-family: var(--font-mono);">QUEUE LENGTH</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: #DC2626; font-family: var(--font-heading);">${props.queueLength}</div>
        </div>
        <div>
          <div style="color: #991B1B; font-size: 0.6rem; font-family: var(--font-mono);">AVG DELAY</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: #DC2626; font-family: var(--font-heading);">${props.avgDelay}</div>
        </div>
      </div>
      <div style="font-size: 0.68rem; color: #64748B; line-height: 1.35;">
        Cause: ${props.cause}
      </div>
    </div>
  `
}

function buildClosurePopup(props) {
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 230px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: #D97706; font-family: var(--font-mono); background: #FEF3C7; padding: 2px 8px; border-radius: 4px;">
          ROAD CLOSURE
        </span>
        <span style="font-size: 0.65rem; color: #DC2626; font-weight: 700; font-family: var(--font-mono);">${props.status}</span>
      </div>
      <div style="font-size: 0.88rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        🚧 ${props.name}
      </div>
      <div style="font-size: 0.72rem; color: #475569; margin-bottom: 6px;">${props.road}</div>
      <div style="font-size: 0.7rem; color: #64748B; margin-bottom: 8px;">Reason: ${props.reason}</div>
      <div style="background: #F8FAFC; padding: 6px 8px; border-radius: 4px; border: 1px solid #E2E8F0; font-size: 0.65rem; color: #1E293B;">
        <span style="color: #64748B; font-weight: 600;">Diversion:</span> ${props.diversion}
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
  const markersRef = useRef([])

  const [layers, setLayers] = useState(LAYER_DEFS)
  const [loading, setLoading] = useState(true)

  const toggleLayer = useCallback(id => {
    setLayers(prev => prev.map(l => (l.id === id ? { ...l, checked: !l.checked } : l)))
  }, [])

  const isLayerActive = useCallback(
    id => layers.find(l => l.id === id)?.checked ?? true,
    [layers]
  )

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
      /* ── 1. Traffic Flow GeoJSON Source & Crisp Layers ── */
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

      /* ── 2. Road Closures GeoJSON Layer ── */
      map.addSource('road-closures', {
        type: 'geojson',
        data: REAL_ROAD_CLOSURES,
      })

      map.addLayer({
        id: 'closure-line',
        type: 'line',
        source: 'road-closures',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': '#DC2626',
          'line-width': 6,
          'line-dasharray': [2, 2],
          'line-opacity': 0.9,
        },
      })

      /* ── 3. Click & Hover Events on Traffic Corridors ── */
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

      map.on('click', 'closure-line', e => {
        const feat = e.features?.[0]
        if (!feat) return
        popup
          .setLngLat(e.lngLat)
          .setHTML(buildClosurePopup(feat.properties))
          .addTo(map)
      })

      /* ── 4. Active Incident Markers at Real Coordinates ── */
      REAL_INCIDENTS.features.forEach(inc => {
        const el = document.createElement('div')
        el.className = 'sc-incident-marker'
        el.style.cssText = `
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: ${inc.properties.color};
          border: 2.5px solid #FFFFFF;
          box-shadow: 0 4px 14px ${inc.properties.color}80;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          font-size: 14px;
          transition: transform 0.18s ease;
        `
        el.innerHTML = inc.properties.type === 'Accident' ? '🚨' : inc.properties.type === 'Road Work' ? '🚧' : '⚠️'
        el.onmouseenter = () => (el.style.transform = 'scale(1.2)')
        el.onmouseleave = () => (el.style.transform = 'scale(1)')

        const incPopup = new maplibregl.Popup({
          offset: 14,
          closeButton: true,
          maxWidth: '340px',
          className: 'sc-popup',
        }).setHTML(buildIncidentPopup(inc.properties))

        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(inc.geometry.coordinates)
          .setPopup(incPopup)
          .addTo(map)

        markersRef.current.push({ id: 'incidents', marker })
      })

      /* ── 5. Surveillance Cameras at Real Intersections ── */
      REAL_CAMERAS.features.forEach(cam => {
        const el = document.createElement('div')
        el.className = 'sc-camera-marker'
        el.style.cssText = `
          width: 26px;
          height: 26px;
          border-radius: 6px;
          background: #1E293B;
          border: 1.5px solid #FFFFFF;
          box-shadow: 0 2px 8px rgba(0,0,0,0.3);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          font-size: 12px;
          transition: transform 0.18s ease;
        `
        el.innerHTML = '📹'
        el.onmouseenter = () => (el.style.transform = 'scale(1.2)')
        el.onmouseleave = () => (el.style.transform = 'scale(1)')

        const camPopup = new maplibregl.Popup({
          offset: 14,
          closeButton: true,
          maxWidth: '340px',
          className: 'sc-popup',
        }).setHTML(buildCameraPopup(cam.properties))

        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(cam.geometry.coordinates)
          .setPopup(camPopup)
          .addTo(map)

        markersRef.current.push({ id: 'cameras', marker })
      })

      /* ── 6. Bottleneck Hotspots at Real Choke Points ── */
      REAL_BOTTLENECKS.features.forEach(btn => {
        const el = document.createElement('div')
        el.className = 'sc-bottleneck-marker'
        el.style.cssText = `
          background: #DC2626;
          color: #FFFFFF;
          padding: 4px 8px;
          border-radius: 6px;
          box-shadow: 0 4px 12px rgba(220, 38, 38, 0.45);
          font-family: var(--font-mono);
          font-size: 0.65rem;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 4px;
          border: 1px solid #FFFFFF;
          white-space: nowrap;
          transition: transform 0.18s ease;
        `
        el.innerHTML = `<span>🛑</span><span>${btn.properties.queueLength}</span>`
        el.onmouseenter = () => (el.style.transform = 'scale(1.12)')
        el.onmouseleave = () => (el.style.transform = 'scale(1)')

        const btnPopup = new maplibregl.Popup({
          offset: 14,
          closeButton: true,
          maxWidth: '340px',
          className: 'sc-popup',
        }).setHTML(buildBottleneckPopup(btn.properties))

        const marker = new maplibregl.Marker({ element: el, anchor: 'bottom' })
          .setLngLat(btn.geometry.coordinates)
          .setPopup(btnPopup)
          .addTo(map)

        markersRef.current.push({ id: 'bottlenecks', marker })
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

  /* ── Sync Layer Visibility ── */
  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    // 1. Line layers (Traffic Flow)
    const flowVisible = isLayerActive('flow') ? 'visible' : 'none'
    if (map.getLayer('flow-line')) map.setLayoutProperty('flow-line', 'visibility', flowVisible)
    if (map.getLayer('flow-casing')) map.setLayoutProperty('flow-casing', 'visibility', flowVisible)

    // 2. Road Closures
    const closureVisible = isLayerActive('closures') ? 'visible' : 'none'
    if (map.getLayer('closure-line')) map.setLayoutProperty('closure-line', 'visibility', closureVisible)

    // 3. HTML Markers (Incidents, Cameras, Bottlenecks)
    markersRef.current.forEach(({ id, marker }) => {
      const active = isLayerActive(id)
      const el = marker.getElement()
      if (el) el.style.display = active ? 'flex' : 'none'
    })
  }, [layers, isLayerActive])

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

        {/* ── Top-Left: Dark Layers & Legend Panel ── */}
        <div
          style={{
            position: 'absolute',
            top: '16px',
            left: '16px',
            background: 'rgba(23, 33, 43, 0.94)',
            backdropFilter: 'blur(8px)',
            borderRadius: '10px',
            padding: '16px',
            width: '185px',
            color: '#FFFFFF',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
            zIndex: 10,
            border: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          {/* Layers Section */}
          <div
            style={{
              fontSize: '0.68rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em',
              marginBottom: '12px',
              color: '#FFFFFF',
            }}
          >
            TRAFFIC LAYERS
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {layers.map(layer => {
              const Icon = layer.icon
              return (
                <label
                  key={layer.id}
                  onClick={() => toggleLayer(layer.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                    fontSize: '0.72rem',
                    color: layer.checked ? '#FFFFFF' : '#94A3B8',
                    fontWeight: layer.checked ? 600 : 400,
                    userSelect: 'none',
                  }}
                >
                  <div
                    style={{
                      width: 14,
                      height: 14,
                      borderRadius: 3,
                      background: layer.checked ? '#2F8F72' : 'transparent',
                      border: `1.5px solid ${layer.checked ? '#2F8F72' : '#64748B'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      transition: 'all 0.15s ease',
                      flexShrink: 0,
                    }}
                  >
                    {layer.checked && <Check size={10} color="#FFFFFF" strokeWidth={3} />}
                  </div>
                  <span style={{ whiteSpace: 'nowrap' }}>{layer.label}</span>
                </label>
              )
            })}
          </div>

          {/* Legend Section */}
          <div
            style={{
              marginTop: '14px',
              paddingTop: '12px',
              borderTop: '1px solid rgba(255, 255, 255, 0.12)',
            }}
          >
            <div
              style={{
                fontSize: '0.65rem',
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.08em',
                marginBottom: '8px',
                color: '#FFFFFF',
              }}
            >
              FLOW SPEEDS
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

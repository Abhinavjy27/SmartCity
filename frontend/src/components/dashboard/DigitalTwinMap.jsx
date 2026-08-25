import { useRef, useEffect, useState, useCallback } from 'react'
import * as maplibregl from 'maplibre-gl'
import { Car, Wind, Zap, Eye, EyeOff, Layers, Maximize2, RotateCcw } from 'lucide-react'
import { getDigitalTwin3DStyle } from '../../services/map/mapStyleService'
import {
  DIGITAL_TWIN_CENTER,
  HYDERABAD_BOUNDS,
  REAL_TRAFFIC_FLOWS,
  REAL_ENERGY_SUBSTATIONS,
  REAL_AQI_SENSORS,
} from '../../services/map/mapDataService'

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
  { id: 'traffic', label: 'Traffic Flow', icon: Car, color: '#2F8F72', desc: 'Real road network speeds' },
  { id: 'energy', label: 'Energy Substations', icon: Zap, color: '#F59E0B', desc: 'TSSPDCL / TSTRANSCO Grid' },
  { id: 'aqi', label: 'AQI Sensors', icon: Wind, color: '#10B981', desc: 'TSPCB / CPCB CAAQMS Stations' },
]

const LEGEND_ITEMS = [
  { label: 'Free Flow (>50 km/h)', color: '#2F8F72', type: 'line' },
  { label: 'Moderate (30-50 km/h)', color: '#EAB308', type: 'line' },
  { label: 'Congested (15-30 km/h)', color: '#EF4444', type: 'line' },
  { label: 'Severe (<15 km/h)', color: '#8B0000', type: 'line' },
  { label: 'Energy Substation (132-400kV)', color: '#F59E0B', type: 'node' },
  { label: 'AQI Sensor Station', color: '#10B981', type: 'sensor' },
]

/* ═══════════════════════════════════════════════════════════
   POPUP BUILDERS (Clean GIS Telemetry)
   ═══════════════════════════════════════════════════════════ */

function buildTrafficPopup(p) {
  const color = p.color || '#2F8F72'
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 240px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: ${color}; text-transform: uppercase; letter-spacing: 0.06em; font-family: var(--font-mono); background: ${color}15; padding: 2px 8px; border-radius: 4px;">
          ${p.statusLabel || p.status}
        </span>
        <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${p.corridor || 'Hyderabad'}</span>
      </div>
      <div style="font-size: 0.9rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        ${p.road || p.name}
      </div>
      <p style="font-size: 0.7rem; color: #64748B; margin-bottom: 10px; line-height: 1.35;">
        ${p.description || ''}
      </p>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #F8FAFC; padding: 8px 10px; border-radius: 6px; font-size: 0.72rem; border: 1px solid #E2E8F0;">
        <div>
          <div style="color: #8F9295; font-size: 0.6rem; font-family: var(--font-mono); text-transform: uppercase;">CURRENT SPEED</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: ${color}; font-family: var(--font-heading);">${p.speed} <span style="font-size: 0.65rem; font-weight: 500;">km/h</span></div>
        </div>
        <div>
          <div style="color: #8F9295; font-size: 0.6rem; font-family: var(--font-mono); text-transform: uppercase;">TRAFFIC VOLUME</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: #17212B; font-family: var(--font-heading);">${p.volume || 3800} <span style="font-size: 0.65rem; font-weight: 500;">vph</span></div>
        </div>
      </div>
      ${p.queueLength ? `
        <div style="margin-top: 8px; font-size: 0.68rem; color: #8B0000; font-family: var(--font-mono); font-weight: 600; display: flex; align-items: center; gap: 4px;">
          ⚠ Choke Point Queue: <strong>${p.queueLength}</strong>
        </div>
      ` : ''}
    </div>
  `
}

function buildEnergyPopup(p) {
  const isHighLoad = p.status === 'High Load'
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 250px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: #D97706; text-transform: uppercase; letter-spacing: 0.06em; font-family: var(--font-mono); background: #FEF3C7; padding: 2px 8px; border-radius: 4px;">
          ⚡ ${p.voltage} GRID
        </span>
        <span style="font-size: 0.65rem; color: ${isHighLoad ? '#EF4444' : '#10B981'}; font-weight: 700; font-family: var(--font-mono);">
          ● ${p.status}
        </span>
      </div>
      <div style="font-size: 0.9rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        ${p.name}
      </div>
      <div style="font-size: 0.68rem; color: #64748B; margin-bottom: 8px; font-family: var(--font-mono);">
        Operator: <strong>${p.operator || 'TSTRANSCO'}</strong> · Location: ${p.latitude.toFixed(4)}°N, ${p.longitude.toFixed(4)}°E
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #FFFBEB; padding: 8px 10px; border-radius: 6px; border: 1px solid #FDE68A; margin-bottom: 8px;">
        <div>
          <div style="color: #92400E; font-size: 0.6rem; font-family: var(--font-mono);">CURRENT LOAD</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: ${isHighLoad ? '#DC2626' : '#D97706'}; font-family: var(--font-heading);">${p.currentLoad}</div>
        </div>
        <div>
          <div style="color: #92400E; font-size: 0.6rem; font-family: var(--font-mono);">ACTIVE DEMAND</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: #17212B; font-family: var(--font-heading);">${p.activeDemand}</div>
        </div>
      </div>
      <div style="font-size: 0.68rem; color: #475569; line-height: 1.35; background: #F8FAFC; padding: 6px 8px; border-radius: 4px; border: 1px solid #E2E8F0;">
        <span style="color: #64748B; font-weight: 600;">Feed Sector:</span> ${p.feedArea || 'Regional Distribution'}
      </div>
    </div>
  `
}

function buildAqiPopup(p) {
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 240px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: ${p.color}; text-transform: uppercase; letter-spacing: 0.06em; font-family: var(--font-mono); background: ${p.color}18; padding: 2px 8px; border-radius: 4px;">
          ${p.category} AIR QUALITY
        </span>
        <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${p.source || 'TSPCB CAAQMS'}</span>
      </div>
      <div style="font-size: 0.9rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        ${p.location}
      </div>
      <div style="display: flex; align-items: baseline; gap: 8px; margin: 8px 0;">
        <span style="font-size: 1.8rem; font-weight: 800; color: ${p.color}; font-family: var(--font-heading); line-height: 1;">${p.aqi}</span>
        <span style="font-size: 0.72rem; color: #64748B; font-weight: 600;">AQI Index · ${p.temp} · ${p.humidity} RH</span>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.68rem; background: #F8FAFC; padding: 6px 8px; border-radius: 4px; font-family: var(--font-mono); border: 1px solid #E2E8F0;">
        <div>PM2.5: <strong>${p.pm25} µg/m³</strong></div>
        <div>PM10: <strong>${p.pm10} µg/m³</strong></div>
        <div>NO₂: <strong>${p.no2} ppb</strong></div>
        <div>SO₂: <strong>${p.so2} ppb</strong></div>
      </div>
      <div style="margin-top: 6px; font-size: 0.62rem; color: #8F9295; font-family: var(--font-mono);">
        Coordinates: ${p.latitude.toFixed(4)}°N, ${p.longitude.toFixed(4)}°E
      </div>
    </div>
  `
}

/* ═══════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════ */

export default function DigitalTwinMap() {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const popupRef = useRef(null)
  const markersRef = useRef([])

  const [layerState, setLayerState] = useState({
    traffic: true,
    energy: true,
    aqi: true,
  })
  const [loading, setLoading] = useState(true)

  const activeCount = Object.values(layerState).filter(Boolean).length

  const toggleLayer = useCallback(id => {
    setLayerState(prev => ({ ...prev, [id]: !prev[id] }))
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
    })

    const popup = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: true,
      maxWidth: '340px',
      className: 'sc-popup',
    })
    popupRef.current = popup

    map.on('load', () => {
      /* ── 1. Real Hyderabad Traffic Road Geometry ── */
      map.addSource('hyderabad-traffic-corridors', {
        type: 'geojson',
        data: REAL_TRAFFIC_FLOWS,
      })

      // Traffic casing glow
      map.addLayer({
        id: 'twin-traffic-casing',
        type: 'line',
        source: 'hyderabad-traffic-corridors',
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

      // Crisp solid traffic flow line
      map.addLayer({
        id: 'twin-traffic-line',
        type: 'line',
        source: 'hyderabad-traffic-corridors',
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

      // Traffic hover and click interactions
      map.on('mouseenter', 'twin-traffic-line', e => {
        map.getCanvas().style.cursor = 'pointer'
        const fid = e.features?.[0]?.properties?.id
        if (fid) {
          map.setPaintProperty('twin-traffic-line', 'line-width', [
            'case',
            ['==', ['get', 'id'], fid],
            8,
            ['interpolate', ['linear'], ['zoom'], 10, 3.5, 14, 6],
          ])
        }
      })

      map.on('mouseleave', 'twin-traffic-line', () => {
        map.getCanvas().style.cursor = ''
        map.setPaintProperty('twin-traffic-line', 'line-width', [
          'interpolate',
          ['linear'],
          ['zoom'],
          10,
          3.5,
          14,
          6,
        ])
      })

      map.on('click', 'twin-traffic-line', e => {
        const feat = e.features?.[0]
        if (!feat) return
        popup
          .setLngLat(e.lngLat)
          .setHTML(buildTrafficPopup(feat.properties))
          .addTo(map)
      })

      /* ── 2. Real Energy Substations (TSSPDCL / TSTRANSCO) ── */
      REAL_ENERGY_SUBSTATIONS.features.forEach(sub => {
        const el = document.createElement('div')
        el.className = 'sc-energy-node-marker'
        el.style.cssText = `
          display: flex;
          align-items: center;
          gap: 6px;
          cursor: pointer;
          transition: transform 0.18s ease;
        `
        el.innerHTML = `
          <div style="
            width: 28px;
            height: 28px;
            border-radius: 8px;
            background: #F59E0B;
            border: 2px solid #FFFFFF;
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.45);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 800;
          ">
            ⚡
          </div>
          <div style="
            background: rgba(23, 33, 43, 0.92);
            color: #FFFFFF;
            padding: 3px 7px;
            border-radius: 4px;
            font-size: 0.62rem;
            font-weight: 700;
            font-family: var(--font-mono);
            letter-spacing: 0.02em;
            white-space: nowrap;
            box-shadow: 0 2px 6px rgba(0,0,0,0.25);
            border: 1px solid rgba(245, 158, 11, 0.4);
          ">
            ${sub.properties.capacity}
          </div>
        `
        el.onmouseenter = () => (el.style.transform = 'scale(1.12)')
        el.onmouseleave = () => (el.style.transform = 'scale(1)')

        const nodePopup = new maplibregl.Popup({
          offset: 14,
          closeButton: true,
          maxWidth: '340px',
          className: 'sc-popup',
        }).setHTML(buildEnergyPopup(sub.properties))

        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(sub.geometry.coordinates)
          .setPopup(nodePopup)
          .addTo(map)

        markersRef.current.push({ id: 'energy', marker })
      })

      /* ── 3. Real AQI Monitoring Stations (TSPCB / CPCB CAAQMS) ── */
      REAL_AQI_SENSORS.features.forEach(sensor => {
        const el = document.createElement('div')
        el.className = 'sc-aqi-sensor-marker'
        el.style.cssText = `
          display: flex;
          align-items: center;
          gap: 5px;
          cursor: pointer;
          transition: transform 0.18s ease;
        `
        el.innerHTML = `
          <div style="
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background: ${sensor.properties.color};
            border: 2.5px solid #FFFFFF;
            box-shadow: 0 4px 12px ${sensor.properties.color}66;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: #FFFFFF;
          ">
            <span style="font-size: 0.65rem; font-weight: 800; font-family: var(--font-heading); line-height: 1;">${sensor.properties.aqi}</span>
            <span style="font-size: 0.45rem; font-weight: 700; font-family: var(--font-mono); opacity: 0.9;">AQI</span>
          </div>
        `
        el.onmouseenter = () => (el.style.transform = 'scale(1.15)')
        el.onmouseleave = () => (el.style.transform = 'scale(1)')

        const aqiPopup = new maplibregl.Popup({
          offset: 14,
          closeButton: true,
          maxWidth: '340px',
          className: 'sc-popup',
        }).setHTML(buildAqiPopup(sensor.properties))

        const marker = new maplibregl.Marker({ element: el, anchor: 'center' })
          .setLngLat(sensor.geometry.coordinates)
          .setPopup(aqiPopup)
          .addTo(map)

        markersRef.current.push({ id: 'aqi', marker })
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

    // Traffic line layers
    const trafficVis = layerState.traffic ? 'visible' : 'none'
    if (map.getLayer('twin-traffic-line')) map.setLayoutProperty('twin-traffic-line', 'visibility', trafficVis)
    if (map.getLayer('twin-traffic-casing')) map.setLayoutProperty('twin-traffic-casing', 'visibility', trafficVis)

    // Markers (Substations & AQI Sensors)
    markersRef.current.forEach(({ id, marker }) => {
      const active = layerState[id] ?? true
      const el = marker.getElement()
      if (el) el.style.display = active ? 'flex' : 'none'
    })
  }, [layerState])

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
                    title={active ? 'Hide Layer' : 'Show Layer'}
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

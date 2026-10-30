/**
 * TrafficLayerService
 * 
 * Production shared MapLibre GL JS traffic layer integration for SUPADSP Hyderabad.
 * Uses TomTom Traffic Flow Vector Tiles (.pbf) proxied server-side through FastAPI.
 * 
 * Schema Details:
 *   - Source Layer: "Traffic flow"
 *   - Property: "traffic_level" (float 0.00 = standstill to 1.00 = free-flow)
 *   - Property: "road_type" (e.g. "Major road", "Motorway", "Secondary")
 *   - Property: "road_closure" (boolean)
 */

export const VECTOR_TILE_URL = '/api/traffic/tiles/flow/{z}/{x}/{y}'
export const TRAFFIC_SOURCE_ID = 'tomtom-traffic-flow'
export const TRAFFIC_CASING_LAYER_ID = 'traffic-flow-casing'
export const TRAFFIC_LINE_LAYER_ID = 'traffic-flow-line'
export const TRAFFIC_SOURCE_LAYER = 'Traffic flow'

/**
 * Shared Legend and Threshold Buckets (0.0 to 1.0)
 */
export const TRAFFIC_LEGEND_BUCKETS = [
  { label: 'Free Flow (> 85%)', min: 0.85, max: 1.00, color: '#16A34A', hex: '#16A34A', status: 'Free Flow' },
  { label: 'Near Free (70% – 85%)', min: 0.70, max: 0.85, color: '#2F8F72', hex: '#2F8F72', status: 'Near Free' },
  { label: 'Moderate (50% – 70%)', min: 0.50, max: 0.70, color: '#EAB308', hex: '#EAB308', status: 'Moderate' },
  { label: 'Slow (25% – 50%)', min: 0.25, max: 0.50, color: '#F97316', hex: '#F97316', status: 'Slow' },
  { label: 'Congested (1% – 25%)', min: 0.01, max: 0.25, color: '#EF4444', hex: '#EF4444', status: 'Congested' },
  { label: 'Severe / Standstill (< 1%)', min: 0.00, max: 0.01, color: '#8B0000', hex: '#8B0000', status: 'Standstill' },
]

/**
 * High-precision MapLibre GL color expression based on traffic_level
 */
export const TRAFFIC_COLOR_EXPR = [
  'interpolate',
  ['linear'],
  ['coalesce', ['get', 'traffic_level'], 1],
  0.00, '#8B0000',   // standstill / severe
  0.25, '#EF4444',   // congested
  0.50, '#F97316',   // slow
  0.70, '#EAB308',   // moderate
  0.85, '#2F8F72',   // near free
  1.00, '#16A34A',   // free flow
]

export const LINE_WIDTH_EXPR = [
  'interpolate', ['linear'], ['zoom'],
  9, 1.2,
  11, 2.0,
  13, 3.2,
  15, 5.0,
  17, 8.0,
]

export const CASING_WIDTH_EXPR = [
  'interpolate', ['linear'], ['zoom'],
  9, 2.0,
  11, 3.2,
  13, 5.0,
  15, 8.0,
  17, 12.5,
]

/**
 * Idempotently adds the TomTom vector traffic source and line layers to the given MapLibre instance.
 * Safe to call on 'load', 'style.load', or during layer re-initialization.
 */
export function addTrafficLayers(map, options = {}) {
  if (!map) return

  // 1. Add or reuse vector source
  if (!map.getSource(TRAFFIC_SOURCE_ID)) {
    map.addSource(TRAFFIC_SOURCE_ID, {
      type: 'vector',
      tiles: [VECTOR_TILE_URL],
      minzoom: 0,
      maxzoom: 22,
      attribution: '© <a href="https://www.tomtom.com" target="_blank" rel="noopener">TomTom</a>',
    })
  }

  const beforeId = options.beforeId || undefined

  // 2. Add Casing Glow Layer (underneath)
  if (!map.getLayer(TRAFFIC_CASING_LAYER_ID)) {
    map.addLayer({
      id: TRAFFIC_CASING_LAYER_ID,
      type: 'line',
      source: TRAFFIC_SOURCE_ID,
      'source-layer': TRAFFIC_SOURCE_LAYER,
      layout: {
        'line-join': 'round',
        'line-cap': 'round',
        visibility: options.visibility !== undefined ? options.visibility : 'visible',
      },
      paint: {
        'line-color': TRAFFIC_COLOR_EXPR,
        'line-width': CASING_WIDTH_EXPR,
        'line-opacity': 0.22,
        'line-blur': 1.5,
      },
    }, beforeId)
  }

  // 3. Add Crisp Speed Colored Line Layer (above casing)
  if (!map.getLayer(TRAFFIC_LINE_LAYER_ID)) {
    map.addLayer({
      id: TRAFFIC_LINE_LAYER_ID,
      type: 'line',
      source: TRAFFIC_SOURCE_ID,
      'source-layer': TRAFFIC_SOURCE_LAYER,
      layout: {
        'line-join': 'round',
        'line-cap': 'round',
        visibility: options.visibility !== undefined ? options.visibility : 'visible',
      },
      paint: {
        'line-color': TRAFFIC_COLOR_EXPR,
        'line-width': LINE_WIDTH_EXPR,
        'line-opacity': 0.95,
      },
    }, beforeId)
  }
}

/**
 * Safely toggle traffic layer visibility without touching other map layers.
 */
export function setTrafficVisibility(map, isVisible) {
  if (!map) return
  const vis = isVisible ? 'visible' : 'none'
  if (map.getLayer(TRAFFIC_LINE_LAYER_ID)) {
    map.setLayoutProperty(TRAFFIC_LINE_LAYER_ID, 'visibility', vis)
  }
  if (map.getLayer(TRAFFIC_CASING_LAYER_ID)) {
    map.setLayoutProperty(TRAFFIC_CASING_LAYER_ID, 'visibility', vis)
  }
}

/**
 * Reloads traffic vector tiles every 60 seconds with cache-busting timestamp
 * without recreating layers or resetting view.
 */
export function reloadTrafficTiles(map) {
  if (!map) return
  const source = map.getSource(TRAFFIC_SOURCE_ID)
  if (source && typeof source.setTiles === 'function') {
    const freshUrl = `${VECTOR_TILE_URL}?_ts=${Date.now()}`
    source.setTiles([freshUrl])
  }
}

/**
 * Formats a telemetry popup for a selected road segment from TomTom vector properties.
 */
export function buildTrafficPopup(properties) {
  const level = properties?.traffic_level ?? null
  const roadType = properties?.road_type ?? 'Arterial Road'
  const roadClosure = properties?.road_closure ?? false

  const FREE_FLOW_APPROX_KMH = 70
  const estimatedSpeed = level !== null ? Math.round(level * FREE_FLOW_APPROX_KMH) : null

  let statusLabel = 'Unknown'
  let statusColor = '#8F9295'
  if (level !== null) {
    if (level >= 0.85) { statusLabel = 'Free Flow'; statusColor = '#16A34A' }
    else if (level >= 0.70) { statusLabel = 'Near Free'; statusColor = '#2F8F72' }
    else if (level >= 0.50) { statusLabel = 'Moderate'; statusColor = '#EAB308' }
    else if (level >= 0.25) { statusLabel = 'Slow'; statusColor = '#F97316' }
    else if (level > 0.00) { statusLabel = 'Congested'; statusColor = '#EF4444' }
    else { statusLabel = 'Standstill'; statusColor = '#8B0000' }
  }

  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 240px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: ${statusColor}; text-transform: uppercase;
          letter-spacing: 0.06em; font-family: var(--font-mono); background: ${statusColor}18;
          padding: 2px 8px; border-radius: 4px;">
          ${statusLabel}
        </span>
        <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${roadType}</span>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #F8FAFC;
        padding: 8px 10px; border-radius: 6px; font-size: 0.72rem; border: 1px solid #E2E8F0; margin-top: 8px;">
        <div>
          <div style="color: #8F9295; font-size: 0.6rem; font-family: var(--font-mono);">TRAFFIC LEVEL</div>
          <div style="font-weight: 800; font-size: 1.15rem; color: ${statusColor}; font-family: var(--font-heading);">
            ${level !== null ? (level * 100).toFixed(0) + '%' : '—'}
          </div>
        </div>
        <div>
          <div style="color: #8F9295; font-size: 0.6rem; font-family: var(--font-mono);">EST. SPEED</div>
          <div style="font-weight: 800; font-size: 1.15rem; color: #17212B; font-family: var(--font-heading);">
            ${estimatedSpeed !== null ? estimatedSpeed + ' <span style="font-size:0.65rem;font-weight:400">km/h</span>' : '—'}
          </div>
        </div>
      </div>
      ${roadClosure ? `
        <div style="margin-top: 8px; font-size: 0.68rem; color: #8B0000; font-family: var(--font-mono);
          font-weight: 600; display: flex; align-items: center; gap: 4px;">
          ⛔ Road Closure Reported
        </div>
      ` : ''}
      <div style="margin-top: 8px; font-size: 0.6rem; color: #94A3B8; font-family: var(--font-mono);">
        Source: TomTom Traffic Flow Vector Tiles (real-time) via secure proxy
      </div>
    </div>
  `
}

/**
 * MapStyleService
 * 
 * Provides production-ready MapLibre GL style specifications for:
 * 1. City Digital Twin (Operations GIS Map with authentic Hyderabad geography)
 * 2. Traffic Intelligence Map (High-contrast command center GIS map)
 *
 * Map tiles are served through the backend proxy (/api/tiles/basic/{z}/{x}/{y})
 * so the TomTom API key never reaches the browser.
 * Attribution: © TomTom (required by TomTom Terms of Use)
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const MAP_PALETTE = {
  // Warm Ivory Theme Tokens
  bg: '#F7F4EC',
  land: '#F4EFE6',
  landuseGreen: '#E2EBD8',
  water: '#BBD7EA',
  roadMinor: '#E8E2D6',
  roadPrimary: '#D2C8B7',
  text: '#17212B',
  textSecondary: '#64748B',

  // Traffic State Colors
  trafficFree: '#2F8F72',
  trafficModerate: '#EAB308',
  trafficCongested: '#EF4444',
  trafficSevere: '#8B0000',
  trafficNoData: '#8F9295',

  // Energy & AQI Accents
  energyAmber: '#F59E0B',
  aqiGreen: '#22C55E',
  aqiModerate: '#EAB308',
  aqiPoor: '#F97316',
  aqiVeryPoor: '#EF4444',
  aqiSevere: '#7E22CE',
}

/**
 * High-performance Raster-based TomTom / GIS Style
 * Tiles are proxied through the backend to keep the API key server-side.
 */
export function getDigitalTwin3DStyle() {
  return {
    version: 8,
    name: 'Hyderabad-Digital-Twin-Basemap',
    sources: {
      'tomtom-basemap': {
        type: 'raster',
        tiles: [
          `${API_BASE}/api/tiles/basic/{z}/{x}/{y}`,
        ],
        tileSize: 256,
        attribution: '© <a href="https://www.tomtom.com" target="_blank">TomTom</a>',
      },
    },
    layers: [
      {
        id: 'bg',
        type: 'background',
        paint: {
          'background-color': '#F4EFE6',
        },
      },
      {
        id: 'basemap-tiles',
        type: 'raster',
        source: 'tomtom-basemap',
        paint: {
          'raster-opacity': 0.92,
          'raster-saturation': -0.1,
          'raster-contrast': 0.04,
        },
      },
    ],
  }
}

/**
 * Traffic Intelligence Map Style
 * Uses TomTom tiles (proxied) for accurate street-level Hyderabad detail.
 */
export function getTrafficMapStyle() {
  return {
    version: 8,
    name: 'Hyderabad-Traffic-Intelligence-Basemap',
    sources: {
      'tomtom-basemap': {
        type: 'raster',
        tiles: [
          `${API_BASE}/api/tiles/basic/{z}/{x}/{y}`,
        ],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© <a href="https://www.tomtom.com" target="_blank">TomTom</a>',
      },
    },
    layers: [
      {
        id: 'bg',
        type: 'background',
        paint: {
          'background-color': '#F4EFE6',
        },
      },
      {
        id: 'basemap-tiles',
        type: 'raster',
        source: 'tomtom-basemap',
        paint: {
          'raster-opacity': 0.85,
          'raster-saturation': -0.3, // slight desaturation so traffic lines pop
        },
      },
    ],
  }
}

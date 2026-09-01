/**
 * MapStyleService
 * 
 * Provides production-ready MapLibre GL style specifications for:
 * 1. City Digital Twin (Operations GIS Map with authentic Hyderabad geography)
 * 2. Traffic Intelligence Map (High-contrast command center GIS map)
 */

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
 * High-performance, reliable Raster-based Carto Positron / Voyager Style
 * Displays authentic Hyderabad road network, lakes (Hussain Sagar, Osman Sagar, Himayat Sagar),
 * neighborhoods, and landmarks directly from OpenStreetMap data.
 */
export function getDigitalTwin3DStyle() {
  return {
    version: 8,
    name: 'Hyderabad-Digital-Twin-Basemap',
    sources: {
      'carto-voyager': {
        type: 'raster',
        tiles: [
          'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
          'https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
          'https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
          'https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
          'https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}@2x.png',
        ],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors, © CARTO',
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
        source: 'carto-voyager',
        paint: {
          'raster-opacity': 0.94,
          'raster-saturation': -0.15,
          'raster-contrast': 0.05,
          'raster-brightness-min': 0.02,
        },
      },
    ],
  }
}

/**
 * Traffic Intelligence Map Style (Clean Light Carto Positron)
 */
export function getTrafficMapStyle() {
  return {
    version: 8,
    name: 'Hyderabad-Traffic-Intelligence-Basemap',
    sources: {
      'carto-positron': {
        type: 'raster',
        tiles: [
          'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
          'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
          'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
          'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
          'https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png',
        ],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors, © CARTO',
      },
    },
    layers: [
      {
        id: 'bg',
        type: 'background',
        paint: {
          'background-color': '#F7F4EC',
        },
      },
      {
        id: 'positron-tiles',
        type: 'raster',
        source: 'carto-positron',
        paint: {
          'raster-opacity': 0.92,
          'raster-contrast': 0.06,
          'raster-saturation': -0.1,
        },
      },
    ],
  }
}

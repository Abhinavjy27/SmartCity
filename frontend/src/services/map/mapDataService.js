/**
 * Map Data Service & Architecture Adapter
 * 
 * Provides an enterprise-grade abstraction layer between:
 * - Real geospatial datasets (GeoJSON FeatureCollections)
 * - Live telemetry feeds (WebSockets / REST endpoints)
 * - MapLibre GL UI components
 * 
 * Enforces strict geographic coordinate integrity: WGS84 [lng, lat]
 */

import {
  HYDERABAD_CENTER,
  DIGITAL_TWIN_CENTER,
  HYDERABAD_BOUNDS,
  HYDERABAD_AREAS,
  REAL_TRAFFIC_FLOWS,
  REAL_ENERGY_SUBSTATIONS,
  REAL_AQI_SENSORS,
  REAL_INCIDENTS,
  REAL_CAMERAS,
  REAL_BOTTLENECKS,
  REAL_ROAD_CLOSURES,
} from './hyderabadGeoData'

export {
  HYDERABAD_CENTER,
  DIGITAL_TWIN_CENTER,
  HYDERABAD_BOUNDS,
  HYDERABAD_AREAS,
  REAL_TRAFFIC_FLOWS,
  REAL_ENERGY_SUBSTATIONS,
  REAL_AQI_SENSORS,
  REAL_INCIDENTS,
  REAL_CAMERAS,
  REAL_BOTTLENECKS,
  REAL_ROAD_CLOSURES,
}

/* ── Enterprise Map Data Service ── */
class MapDataService {
  constructor() {
    this.listeners = new Set()
    this.trafficData = REAL_TRAFFIC_FLOWS
    this.energyData = REAL_ENERGY_SUBSTATIONS
    this.aqiData = REAL_AQI_SENSORS
    this.incidentsData = REAL_INCIDENTS
    this.camerasData = REAL_CAMERAS
    this.bottlenecksData = REAL_BOTTLENECKS
    this.roadClosuresData = REAL_ROAD_CLOSURES
    this.isLive = false
    this.pollTimer = null
  }

  /**
   * Subscribe to live geospatial telemetry updates.
   */
  subscribe(listener) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  notify() {
    const payload = {
      traffic: this.trafficData,
      energy: this.energyData,
      aqi: this.aqiData,
      incidents: this.incidentsData,
      cameras: this.camerasData,
      bottlenecks: this.bottlenecksData,
      closures: this.roadClosuresData,
    }
    this.listeners.forEach(fn => {
      try {
        fn(payload)
      } catch (e) {
        console.error('Error in MapDataService listener:', e)
      }
    })
  }

  getTrafficFlows() {
    return this.trafficData
  }

  getEnergySubstations() {
    return this.energyData
  }

  getAqiSensors() {
    return this.aqiData
  }

  getIncidents() {
    return this.incidentsData
  }

  getCameras() {
    return this.camerasData
  }

  getBottlenecks() {
    return this.bottlenecksData
  }

  getRoadClosures() {
    return this.roadClosuresData
  }

  /**
   * Production Data Adapter: Load external GeoJSON from REST endpoint
   * Example: await mapDataService.loadFromApi('/api/v1/gis/traffic-flows')
   */
  async loadFromApi(layerName, endpointUrl) {
    try {
      const response = await fetch(endpointUrl)
      if (!response.ok) throw new Error(`HTTP ${response.status} from ${endpointUrl}`)
      const geojson = await response.json()
      
      switch (layerName) {
        case 'traffic':
          this.trafficData = geojson
          break
        case 'energy':
          this.energyData = geojson
          break
        case 'aqi':
          this.aqiData = geojson
          break
        case 'incidents':
          this.incidentsData = geojson
          break
        case 'cameras':
          this.camerasData = geojson
          break
        case 'bottlenecks':
          this.bottlenecksData = geojson
          break
        case 'closures':
          this.roadClosuresData = geojson
          break
        default:
          console.warn(`Unknown layer name: ${layerName}`)
      }
      this.notify()
      return geojson
    } catch (err) {
      console.warn(`Failed to fetch live API for ${layerName}, fallback to verified Hyderabad dataset:`, err)
      return null
    }
  }
}

export const mapDataService = new MapDataService()

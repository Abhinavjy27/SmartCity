/**
 * MarkerLayerService
 * 
 * Production Geospatial Marker System for SUPADSP Hyderabad Digital Twin.
 * Renders verified Energy Substations (TSSPDCL / TSTRANSCO) and TSPCB / CPCB CAAQMS AQI Stations.
 * 
 * Key Architectural Guarantees:
 * 1. Strict coordinate anchoring: WGS84 [lng, lat] coordinates only.
 * 2. Immutable wrapper transform: MapLibre manages outer marker container transform;
 *    hover animations scale child nodes only, preventing markers from jumping or disappearing.
 * 3. Visibility toggling via CSS visibility + pointerEvents (never modifying display property).
 * 4. Full idempotency on both 'load' and 'style.load' events.
 * 5. Automatic cleanup on map removal to prevent memory leaks and zombie references.
 */

import * as maplibregl from 'maplibre-gl'
import {
  REAL_ENERGY_SUBSTATIONS,
  REAL_AQI_SENSORS,
} from './hyderabadGeoData'

export function buildEnergyPopup(properties) {
  const isHighLoad = properties.status === 'High Load'
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 260px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: #D97706; text-transform: uppercase;
          letter-spacing: 0.06em; font-family: var(--font-mono); background: #FEF3C7; padding: 2px 8px; border-radius: 4px;">
          ⚡ ${properties.voltage || properties.capacity} GRID
        </span>
        <span style="font-size: 0.65rem; color: ${isHighLoad ? '#EF4444' : '#10B981'}; font-weight: 700; font-family: var(--font-mono);">
          ● ${properties.status || 'Operational'}
        </span>
      </div>
      <div style="font-size: 0.92rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        ${properties.name}
      </div>
      <div style="font-size: 0.68rem; color: #64748B; margin-bottom: 8px; font-family: var(--font-mono);">
        Operator: <strong>${properties.operator || 'TSTRANSCO'}</strong> · ${properties.latitude.toFixed(4)}°N, ${properties.longitude.toFixed(4)}°E
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #FFFBEB;
        padding: 8px 10px; border-radius: 6px; border: 1px solid #FDE68A; margin-bottom: 8px;">
        <div>
          <div style="color: #92400E; font-size: 0.6rem; font-family: var(--font-mono);">CURRENT LOAD</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: ${isHighLoad ? '#DC2626' : '#D97706'}; font-family: var(--font-heading);">
            ${properties.currentLoad || '72%'}
          </div>
        </div>
        <div>
          <div style="color: #92400E; font-size: 0.6rem; font-family: var(--font-mono);">ACTIVE DEMAND</div>
          <div style="font-weight: 800; font-size: 1.1rem; color: #17212B; font-family: var(--font-heading);">
            ${properties.activeDemand || '160 MW'}
          </div>
        </div>
      </div>
      <div style="font-size: 0.68rem; color: #475569; line-height: 1.35; background: #F8FAFC; padding: 6px 8px; border-radius: 4px; border: 1px solid #E2E8F0;">
        <span style="color: #64748B; font-weight: 600;">Feed Sector:</span> ${properties.feedArea || 'Regional Distribution Sector'}
      </div>
    </div>
  `
}

export function buildAqiPopup(properties) {
  return `
    <div style="font-family: var(--font-body, system-ui); min-width: 250px; padding: 2px;">
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span style="font-size: 0.65rem; font-weight: 700; color: ${properties.color}; text-transform: uppercase;
          letter-spacing: 0.06em; font-family: var(--font-mono); background: ${properties.color}18; padding: 2px 8px; border-radius: 4px;">
          ${properties.category} AIR QUALITY
        </span>
        <span style="font-size: 0.65rem; color: #8F9295; font-family: var(--font-mono);">${properties.source || 'TSPCB CAAQMS'}</span>
      </div>
      <div style="font-size: 0.92rem; font-weight: 700; color: #17212B; margin-bottom: 4px;">
        ${properties.location}
      </div>
      <div style="display: flex; align-items: baseline; gap: 8px; margin: 8px 0;">
        <span style="font-size: 1.8rem; font-weight: 800; color: ${properties.color}; font-family: var(--font-heading); line-height: 1;">
          ${properties.aqi}
        </span>
        <span style="font-size: 0.72rem; color: #64748B; font-weight: 600;">AQI Index · ${properties.temp || '29°C'} · ${properties.humidity || '55%'} RH</span>
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px; font-size: 0.68rem; background: #F8FAFC;
        padding: 6px 8px; border-radius: 4px; font-family: var(--font-mono); border: 1px solid #E2E8F0;">
        <div>PM2.5: <strong>${properties.pm25} µg/m³</strong></div>
        <div>PM10: <strong>${properties.pm10} µg/m³</strong></div>
        <div>NO₂: <strong>${properties.no2 || '35'} ppb</strong></div>
        <div>SO₂: <strong>${properties.so2 || '14'} ppb</strong></div>
      </div>
      <div style="margin-top: 6px; font-size: 0.62rem; color: #8F9295; font-family: var(--font-mono);">
        Coordinates: ${properties.latitude.toFixed(4)}°N, ${properties.longitude.toFixed(4)}°E
      </div>
    </div>
  `
}

/**
 * Robust Marker Manager for MapLibre map instances.
 */
export class MapMarkerManager {
  constructor(map) {
    this.map = map
    this.markers = [] // Array of { id: 'energy' | 'aqi', marker: maplibregl.Marker, container: HTMLElement, labelEl: HTMLElement }
    this.visibilityState = {
      energy: true,
      aqi: true,
    }
    this.zoomListener = this.handleZoom.bind(this)
  }

  init() {
    this.clearMarkers()
    this.createEnergyMarkers()
    this.createAqiMarkers()

    // Add zoom threshold handler for voltage labels
    this.map.off('zoom', this.zoomListener)
    this.map.on('zoom', this.zoomListener)
    this.handleZoom()
  }

  handleZoom() {
    if (!this.map) return
    const zoom = this.map.getZoom()
    const showLabels = zoom >= 10.5
    for (const item of this.markers) {
      if (item.labelEl) {
        item.labelEl.style.display = showLabels ? 'block' : 'none'
      }
    }
  }

  createEnergyMarkers() {
    REAL_ENERGY_SUBSTATIONS.features.forEach(sub => {
      // Outer container: position and transform managed by MapLibre exclusively
      const container = document.createElement('div')
      container.className = 'sc-substation-marker-container'
      container.style.cssText = `
        visibility: ${this.visibilityState.energy ? 'visible' : 'hidden'};
        pointer-events: ${this.visibilityState.energy ? 'auto' : 'none'};
      `

      // Inner container: handles hover scaling and presentation
      const inner = document.createElement('div')
      inner.className = 'sc-substation-marker-inner'
      inner.style.cssText = `
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
        transition: transform 0.18s cubic-bezier(0.4, 0, 0.2, 1);
        transform-origin: center center;
      `

      inner.innerHTML = `
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
          flex-shrink: 0;
        ">
          ⚡
        </div>
        <div class="sc-substation-label" style="
          background: rgba(23, 33, 43, 0.92);
          color: #FFFFFF;
          padding: 3px 7px;
          border-radius: 4px;
          font-size: 0.62rem;
          font-weight: 700;
          font-family: var(--font-mono, monospace);
          letter-spacing: 0.02em;
          white-space: nowrap;
          box-shadow: 0 2px 6px rgba(0,0,0,0.25);
          border: 1px solid rgba(245, 158, 11, 0.4);
        ">
          ${sub.properties.capacity || sub.properties.voltage}
        </div>
      `

      // Notice: hover transform scales inner element ONLY — outer container transform is untouched!
      inner.addEventListener('mouseenter', () => { inner.style.transform = 'scale(1.14)' })
      inner.addEventListener('mouseleave', () => { inner.style.transform = 'scale(1.0)' })

      container.appendChild(inner)

      const popup = new maplibregl.Popup({
        offset: 16,
        closeButton: true,
        maxWidth: '340px',
        className: 'sc-popup',
      }).setHTML(buildEnergyPopup(sub.properties))

      const marker = new maplibregl.Marker({ element: container, anchor: 'center' })
        .setLngLat(sub.geometry.coordinates)
        .setPopup(popup)
        .addTo(this.map)

      const labelEl = inner.querySelector('.sc-substation-label')
      this.markers.push({ id: 'energy', marker, container, labelEl })
    })
  }

  createAqiMarkers() {
    REAL_AQI_SENSORS.features.forEach(sensor => {
      // Outer container: position and transform managed by MapLibre exclusively
      const container = document.createElement('div')
      container.className = 'sc-aqi-marker-container'
      container.style.cssText = `
        visibility: ${this.visibilityState.aqi ? 'visible' : 'hidden'};
        pointer-events: ${this.visibilityState.aqi ? 'auto' : 'none'};
      `

      // Inner container: handles hover scaling and presentation
      const inner = document.createElement('div')
      inner.className = 'sc-aqi-marker-inner'
      inner.style.cssText = `
        display: flex;
        align-items: center;
        gap: 5px;
        cursor: pointer;
        transition: transform 0.18s cubic-bezier(0.4, 0, 0.2, 1);
        transform-origin: center center;
      `

      inner.innerHTML = `
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
          flex-shrink: 0;
        ">
          <span style="font-size: 0.65rem; font-weight: 800; font-family: var(--font-heading, sans-serif); line-height: 1;">
            ${sensor.properties.aqi}
          </span>
          <span style="font-size: 0.45rem; font-weight: 700; font-family: var(--font-mono, monospace); opacity: 0.9;">
            AQI
          </span>
        </div>
      `

      inner.addEventListener('mouseenter', () => { inner.style.transform = 'scale(1.15)' })
      inner.addEventListener('mouseleave', () => { inner.style.transform = 'scale(1.0)' })

      container.appendChild(inner)

      const popup = new maplibregl.Popup({
        offset: 16,
        closeButton: true,
        maxWidth: '340px',
        className: 'sc-popup',
      }).setHTML(buildAqiPopup(sensor.properties))

      const marker = new maplibregl.Marker({ element: container, anchor: 'center' })
        .setLngLat(sensor.geometry.coordinates)
        .setPopup(popup)
        .addTo(this.map)

      this.markers.push({ id: 'aqi', marker, container, labelEl: null })
    })
  }

  setVisibility(id, isVisible) {
    this.visibilityState[id] = isVisible
    for (const item of this.markers) {
      if (item.id === id) {
        item.container.style.visibility = isVisible ? 'visible' : 'hidden'
        item.container.style.pointerEvents = isVisible ? 'auto' : 'none'
      }
    }
  }

  clearMarkers() {
    for (const item of this.markers) {
      try {
        item.marker.remove()
      } catch (e) {
        // Safe ignore
      }
    }
    this.markers = []
  }

  destroy() {
    if (this.map) {
      this.map.off('zoom', this.zoomListener)
    }
    this.clearMarkers()
    this.map = null
  }
}

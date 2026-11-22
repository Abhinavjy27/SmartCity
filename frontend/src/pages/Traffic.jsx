import { useState } from 'react'
import {
  Car, Gauge, Timer, AlertTriangle, MapPin,
  ChevronDown, ShieldAlert, CheckCircle2
} from 'lucide-react'
import {
  AreaChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import TrafficIntelligenceMap from '../components/maps/TrafficIntelligenceMap'
import { useTrafficData } from '../hooks/useTrafficData'

/* ── Static fallback display values (used only while loading) ── */
const LOADING_KPIS = [
  { icon: Gauge,         label: 'Avg Speed',           value: '—',  unit: 'km/h', trend: '—', tColor: 'var(--text-muted)' },
  { icon: Car,           label: 'Traffic Volume',      value: '—',  unit: 'Lakh', trend: '—', tColor: 'var(--text-muted)' },
  { icon: Timer,         label: 'Travel Time Index',   value: '—',  unit: '',     trend: '—', tColor: 'var(--text-muted)' },
  { icon: MapPin,        label: 'Queue Length',        value: '—',  unit: 'km',   trend: '—', tColor: 'var(--text-muted)' },
  { icon: AlertTriangle, label: 'Congested Corridors', value: '—',  unit: '',     trend: '—', tColor: 'var(--text-muted)' },
  { icon: ShieldAlert,   label: 'Active Incidents',    value: '—',  unit: '',     trend: '—', tColor: 'var(--text-muted)' },
]

const statusColor = {
  'Free Flow': '#2F8F72',
  'Moderate':  '#F4A62A',
  'Congested': '#E5483F',
  'Severe':    '#8B0000',
  'Good':      '#2F8F72',
  'High Delay':'#E5483F',
}

export default function Traffic() {
  const [timeRange, setTimeRange] = useState('Live')
  const [showAllIncidents, setShowAllIncidents] = useState(false)
  const [showAllCorridors, setShowAllCorridors] = useState(false)
  const [showAllIntersections, setShowAllIntersections] = useState(false)
  const { kpis, incidents, corridors, trend, intersections, loading, error } = useTrafficData()

  /* ── Build KPI card array from live data (or loading placeholders) ── */
  const kpiCards = kpis
    ? [
        { icon: Gauge,         label: 'Avg Speed',           value: kpis.avgSpeed ?? 'Unavailable', unit: kpis.avgSpeed ? 'km/h' : '', trend: kpis.avgSpeed ? '▼ live' : '—', tColor: '#E5483F' },
        { icon: Car,           label: 'Traffic Volume',      value: 'Unavailable',                  unit: '',    trend: '—', tColor: 'var(--text-muted)' },
        { icon: Timer,         label: 'Travel Time Index',   value: kpis.travelTimeIndex ?? 'Unavailable', unit: '', trend: kpis.travelTimeIndex ? '▲ DERIVED' : '—', tColor: '#E5483F' },
        { icon: MapPin,        label: 'Queue Length',        value: 'Unavailable',                  unit: '',    trend: '—', tColor: 'var(--text-muted)' },
        { icon: AlertTriangle, label: 'Congested Corridors', value: String(kpis.congestedCorridors), unit: '',  trend: '▲ live', tColor: '#E5483F' },
        { icon: ShieldAlert,   label: 'Active Incidents',    value: String(kpis.activeIncidents),    unit: '',  trend: '▲ live', tColor: '#E5483F' },
      ]
    : LOADING_KPIS

  const displayCorridors = corridors.length > 0 ? corridors : []
  const displayIncidents = incidents.length > 0 ? incidents : []
  const displayTrend = trend.length > 0 ? trend : []
  const displayIntersections = intersections.length > 0 ? intersections : []

  // Sliced trend data according to timeRange
  const filteredTrend = (() => {
    if (displayTrend.length === 0) return []
    if (timeRange === '15 Min') return displayTrend.slice(-2)
    if (timeRange === '1 Hour') return displayTrend.slice(-4)
    if (timeRange === '3 Hours') return displayTrend.slice(-8)
    if (timeRange === 'Live') return displayTrend.slice(-6)
    return displayTrend
  })()

  return (
    <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* ── Time Range Bar ───────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px',
        flexWrap: 'wrap',
      }}>
        {['Live', '15 Min', '1 Hour', '3 Hours', 'Custom'].map(t => (
          <button key={t} onClick={() => setTimeRange(t)} style={{
            padding: '6px 16px', borderRadius: 'var(--radius-full)',
            fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
            background: timeRange === t ? '#2F8F72' : 'var(--bg-card)',
            color: timeRange === t ? '#fff' : 'var(--text-secondary)',
            border: timeRange === t ? 'none' : '1px solid var(--border-default)',
            transition: 'all var(--transition-fast)',
          }}>{t}</button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            <span style={{ fontSize: '1rem' }}>☀️</span>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>29°C</span>
            <span>Clear Skies</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', borderLeft: '1px solid var(--border-default)', paddingLeft: '16px' }}>
            10:18 AM<br />Jun 12, 2025
          </div>
        </div>
      </div>

      {/* ── 1. Full-Width Interactive Traffic GIS Map ─────────── */}
      <TrafficIntelligenceMap />

      {/* ── 2. Traffic Overview (Moved Below Map) ─────────── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px 24px',
        boxShadow: 'var(--shadow-card)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
            Traffic Overview
          </h3>
          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            All Corridors <ChevronDown size={10} />
          </div>
        </div>

        {/* 6 Responsive Overview Metric Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '14px',
        }}>
          {kpiCards.map((kpi, i) => {
            const Icon = kpi.icon
            return (
              <div key={i} style={{
                padding: '14px 16px', borderRadius: 'var(--radius-md)',
                background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
                display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                  <Icon size={14} color="var(--text-muted)" strokeWidth={1.8} />
                  <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    {kpi.label}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                    {kpi.value}
                  </span>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{kpi.unit}</span>
                </div>
                <span style={{ fontSize: '0.62rem', color: kpi.tColor, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                  {kpi.trend} vs yesterday
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── 3. Active Incidents (Moved Below Traffic Overview) */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px 24px',
        boxShadow: 'var(--shadow-card)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertTriangle size={16} color="#E5483F" />
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Active Incidents
            </h3>
          </div>
          <span
            onClick={() => setShowAllIncidents(prev => !prev)}
            style={{ fontSize: '0.65rem', color: '#2F8F72', fontFamily: 'var(--font-mono)', cursor: 'pointer', fontWeight: 600 }}
          >
            {showAllIncidents ? 'COLLAPSE <' : `VIEW ALL (${displayIncidents.length}) >`}
          </span>
        </div>

        {/* Incidents in a balanced responsive grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '12px',
        }}>
          {displayIncidents.length > 0 ? (
            (showAllIncidents ? displayIncidents : displayIncidents.slice(0, 4)).map((inc, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: '12px',
                padding: '14px', borderRadius: 'var(--radius-md)',
                background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
                transition: 'all var(--transition-fast)',
              }}>
                <AlertTriangle size={18} color={inc.color} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '2px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: inc.color }}>{inc.type}</span>
                    <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{inc.time}</span>
                  </div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {inc.location}
                  </div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {inc.detail}
                  </div>
                  <div style={{ marginTop: '6px' }}>
                    <span style={{
                      fontSize: '0.58rem', fontWeight: 600, color: inc.color,
                      padding: '2px 6px', borderRadius: 'var(--radius-full)',
                      background: 'var(--bg-card)', border: `1px solid ${inc.color}33`,
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {inc.severity}
                    </span>
                  </div>
                </div>
              </div>
            ))
          ) : loading ? (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '16px', borderRadius: 'var(--radius-md)',
              background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
            }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Loading live incidents from TomTom…
              </span>
            </div>
          ) : (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '12px',
              padding: '14px 18px', borderRadius: 'var(--radius-md)',
              background: 'rgba(47, 143, 114, 0.06)', border: '1px solid rgba(47, 143, 114, 0.25)',
              gridColumn: '1 / -1',
            }}>
              <CheckCircle2 size={18} color="#2F8F72" style={{ flexShrink: 0 }} />
              <div>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#2F8F72', marginBottom: '2px' }}>
                  All Monitored Corridors Clear
                </div>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
                  No active accidents, hazards, or major road closures currently detected in Hyderabad.
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── 4. Lower Sections: Corridor Performance + Traffic Trend + Intersections ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1.2fr 1fr',
        gap: 'var(--space-lg)',
        alignItems: 'start',
      }}>
        {/* Corridor Performance */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Corridor Performance</h3>
            <span
              onClick={() => setShowAllCorridors(prev => !prev)}
              style={{ fontSize: '0.65rem', color: '#2F8F72', fontFamily: 'var(--font-mono)', cursor: 'pointer', fontWeight: 600 }}
            >
              {showAllCorridors ? 'COLLAPSE <' : `VIEW ALL (${displayCorridors.length}) >`}
            </span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
            <thead>
              <tr>
                {['CORRIDOR', 'AVG SPEED', 'TRAVEL TIME', 'STATUS'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 4px', fontSize: '0.58rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600, letterSpacing: '0.06em', borderBottom: '1px solid var(--border-divider)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(displayCorridors.length > 0 ? (showAllCorridors ? displayCorridors : displayCorridors.slice(0, 5)) : [
                { name: 'Loading…', speed: '—', time: '—', status: '—' },
              ]).map((c, i) => (
                <tr key={i}>
                  <td style={{ padding: '8px 4px', color: 'var(--text-primary)', fontWeight: 500 }}>{c.name}</td>
                  <td style={{ padding: '8px 4px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{c.speed} km/h</td>
                  <td style={{ padding: '8px 4px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{c.time}</td>
                  <td style={{ padding: '8px 4px' }}>
                    <span style={{
                      fontSize: '0.6rem', fontWeight: 600,
                      color: statusColor[c.status] || 'var(--text-muted)',
                    }}>{c.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Traffic Trend Chart */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Traffic Trend</h3>
            <span style={{ fontSize: '0.62rem', color: '#2F8F72', fontFamily: 'var(--font-mono)', background: 'rgba(47, 143, 114, 0.08)', padding: '2px 8px', borderRadius: 'var(--radius-full)' }}>
              Range: {timeRange}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={filteredTrend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tSpeedGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2F8F72" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#2F8F72" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval={timeRange === '15 Min' || timeRange === '1 Hour' ? 0 : 2} axisLine={false} tickLine={false} />
              <YAxis yAxisId="speed" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} label={{ value: 'Speed (km/h)', angle: -90, position: 'insideLeft', fontSize: 8, fill: '#8F9295' }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Area yAxisId="speed" type="monotone" dataKey="speed" stroke="#2F8F72" strokeWidth={1.5} fill="url(#tSpeedGrad)" name="Avg Speed (km/h)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Intersection Performance */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <div>
              <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Intersection Performance</h3>
              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>DERIVED from nearby TomTom corridor flow delay</div>
            </div>
            <span
              onClick={() => setShowAllIntersections(prev => !prev)}
              style={{ fontSize: '0.65rem', color: '#2F8F72', fontFamily: 'var(--font-mono)', cursor: 'pointer', fontWeight: 600 }}
            >
              {showAllIntersections ? 'COLLAPSE <' : `VIEW ALL (${displayIntersections.length}) >`}
            </span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
            <thead>
              <tr>
                {['INTERSECTION', 'DELAY', 'LOS', 'STATUS'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '6px 4px', fontSize: '0.58rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600, letterSpacing: '0.06em', borderBottom: '1px solid var(--border-divider)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(displayIntersections.length > 0 ? (showAllIntersections ? displayIntersections : displayIntersections.slice(0, 5)) : [
                { name: 'Loading…', delay: '—', los: '—', status: '—' },
              ]).map((int, i) => (
                <tr key={i}>
                  <td style={{ padding: '8px 4px', color: 'var(--text-primary)', fontWeight: 500 }}>{int.name}</td>
                  <td style={{ padding: '8px 4px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{int.delay}</td>
                  <td style={{ padding: '8px 4px', fontFamily: 'var(--font-mono)', fontWeight: 700, color: statusColor[int.status] || 'var(--text-secondary)' }}>{int.los}</td>
                  <td style={{ padding: '8px 4px' }}>
                    <span style={{ fontSize: '0.6rem', fontWeight: 600, color: statusColor[int.status] || 'var(--text-muted)' }}>{int.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

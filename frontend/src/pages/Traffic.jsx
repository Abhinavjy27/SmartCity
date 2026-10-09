import { useState } from 'react'
import {
  Car, Gauge, Timer, AlertTriangle, MapPin,
  ChevronDown, ShieldAlert
} from 'lucide-react'
import {
  AreaChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import TrafficIntelligenceMap from '../components/maps/TrafficIntelligenceMap'

/* ── Data ── */
const hourlyData = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  speed: Math.max(10, 55 - 35 * Math.exp(-((i - 9) ** 2) / 4) - 30 * Math.exp(-((i - 18) ** 2) / 5) + (Math.random() - 0.5) * 8),
  volume: Math.round((800 + 2800 * Math.exp(-((i - 9) ** 2) / 4) + 2200 * Math.exp(-((i - 18) ** 2) / 5) + (Math.random() - 0.5) * 300) / 1000 * 10) / 10,
}))

const corridors = [
  { name: 'LB Nagar', speed: 12, time: '28 min', status: 'Severe' },
  { name: 'Gachibowli - HiTech City', speed: 18, time: '16 min', status: 'Congested' },
  { name: 'Madhapur - Jubilee Hills', speed: 22, time: '12 min', status: 'Moderate' },
  { name: 'PVNR Expressway', speed: 45, time: '15 min', status: 'Free Flow' },
  { name: 'Inner Ring Road', speed: 20, time: '22 min', status: 'Congested' },
]

const incidents = [
  { type: 'Accident', location: 'Outer Ring Road', detail: 'Near Gachibowli Flyover', severity: 'High Impact', time: '10:05 AM', color: '#E5483F' },
  { type: 'Lane Blockage', location: 'HiTech City Main Road', detail: 'Near Cyber Towers', severity: 'Medium Impact', time: '10:12 AM', color: '#F4A62A' },
  { type: 'Road Work', location: 'PV Narasimha Rao Expressway', detail: 'Near Financial District', severity: 'Medium Impact', time: '10:15 AM', color: '#F4A62A' },
  { type: 'Vehicle Breakdown', location: 'Inner Ring Road', detail: 'Near Koti', severity: 'Low Impact', time: '10:17 AM', color: '#2F8F72' },
]

const intersections = [
  { name: 'Gachibowli Junction', delay: '142 sec', los: 'F', status: 'High Delay' },
  { name: 'HiTech City Junction', delay: '98 sec', los: 'E', status: 'High Delay' },
  { name: 'KPHB Junction', delay: '64 sec', los: 'D', status: 'Moderate' },
  { name: 'Jubilee Hills Checkpost', delay: '41 sec', los: 'C', status: 'Good' },
  { name: 'Ameerpet Junction', delay: '34 sec', los: 'B', status: 'Good' },
]

const statusColor = {
  'Free Flow': '#2F8F72',
  'Moderate': '#F4A62A',
  'Congested': '#E5483F',
  'Severe': '#8B0000',
  'Good': '#2F8F72',
  'High Delay': '#E5483F'
}

export default function Traffic() {
  const [timeRange, setTimeRange] = useState('Live')

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
          {[
            { icon: Gauge, label: 'Avg Speed', value: '15.2', unit: 'km/h', trend: '▼ 26.4%', tColor: '#E5483F' },
            { icon: Car, label: 'Traffic Volume', value: '2.48', unit: 'Lakh', trend: '▲ 8.7%', tColor: '#2F8F72' },
            { icon: Timer, label: 'Travel Time Index', value: '1.78', unit: '', trend: '▲ 18.6%', tColor: '#E5483F' },
            { icon: MapPin, label: 'Queue Length', value: '3.4', unit: 'km', trend: '▲ 22.1%', tColor: '#E5483F' },
            { icon: AlertTriangle, label: 'Congested Corridors', value: '12', unit: '', trend: '▲ 3', tColor: '#E5483F' },
            { icon: ShieldAlert, label: 'Active Incidents', value: '24', unit: '', trend: '▲ 5', tColor: '#E5483F' },
          ].map((kpi, i) => {
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
          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', cursor: 'pointer', fontWeight: 600 }}>
            VIEW ALL &gt;
          </span>
        </div>

        {/* 4 Incidents in a balanced responsive grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '12px',
        }}>
          {incidents.map((inc, i) => (
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
          ))}
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
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', cursor: 'pointer' }}>VIEW ALL &gt;</span>
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
              {corridors.map((c, i) => (
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
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Traffic Trend</h3>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={hourlyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tSpeedGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2F8F72" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#2F8F72" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis yAxisId="speed" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} label={{ value: 'Speed (km/h)', angle: -90, position: 'insideLeft', fontSize: 8, fill: '#8F9295' }} />
              <YAxis yAxisId="volume" orientation="right" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} label={{ value: 'Volume (Lakh)', angle: 90, position: 'insideRight', fontSize: 8, fill: '#8F9295' }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Area yAxisId="speed" type="monotone" dataKey="speed" stroke="#2F8F72" strokeWidth={1.5} fill="url(#tSpeedGrad)" name="Avg Speed (km/h)" />
              <Line yAxisId="volume" type="monotone" dataKey="volume" stroke="#6C8FC5" strokeWidth={1.5} strokeDasharray="4 3" dot={false} name="Traffic Volume (Lakh)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Intersection Performance */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Intersection Performance</h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', cursor: 'pointer' }}>VIEW ALL &gt;</span>
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
              {intersections.map((int, i) => (
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

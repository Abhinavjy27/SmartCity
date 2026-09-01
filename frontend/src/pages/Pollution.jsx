import { useState } from 'react'
import {
  Wind, Droplets, Flame, CloudRain, Factory, Thermometer,
  AlertTriangle, ArrowRight, Info, CheckCircle2, Shield
} from 'lucide-react'
import AnimatedCounter from '../components/AnimatedCounter'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, ReferenceLine
} from 'recharts'

/* ── Data ── */
const aqiTrend = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  aqi: Math.round(80 + 60 * Math.exp(-((i - 8) ** 2) / 8) + 45 * Math.exp(-((i - 20) ** 2) / 6) + (Math.random() - 0.5) * 20),
  pm25: Math.round(30 + 40 * Math.exp(-((i - 8) ** 2) / 8) + 30 * Math.exp(-((i - 20) ** 2) / 6) + (Math.random() - 0.5) * 10),
}))

const pollutants = [
  { name: 'PM2.5', value: 48, unit: 'μg/m³', limit: 60, icon: Droplets, color: '#E5483F' },
  { name: 'PM10', value: 78, unit: 'μg/m³', limit: 100, icon: Wind, color: '#F4A62A' },
  { name: 'NO₂', value: 26, unit: 'μg/m³', limit: 80, icon: Factory, color: '#6C8FC5' },
  { name: 'SO₂', value: 14, unit: 'μg/m³', limit: 80, icon: CloudRain, color: '#2F8F72' },
  { name: 'O₃', value: 32, unit: 'μg/m³', limit: 100, icon: Thermometer, color: '#4C9E9B' },
  { name: 'CO', value: 0.6, unit: 'mg/m³', limit: 2.0, icon: Flame, color: '#8B5CF6' },
]

const topPollutants = [
  { name: 'PM2.5', value: 42, max: 80 },
  { name: 'PM10', value: 76, max: 80 },
  { name: 'NO₂', value: 28, max: 80 },
  { name: 'O₃', value: 30, max: 80 },
  { name: 'SO₂', value: 16, max: 80 },
]

const hotspots = [
  { area: 'Nacharam Industrial Area', aqi: 176, status: 'Unhealthy', pm: 68, color: '#E5483F' },
  { area: 'Sanathnagar', aqi: 162, status: 'Unhealthy', pm: 61, color: '#E5483F' },
  { area: 'Balanagar', aqi: 151, status: 'Unhealthy for Sensitive', pm: 55, color: '#F4A62A' },
  { area: 'Kukatpally', aqi: 142, status: 'Moderate', pm: 46, color: '#F4A62A' },
  { area: 'Gachibowli', aqi: 121, status: 'Moderate', pm: 38, color: '#F4A62A' },
]

const distributionData = [
  { name: 'Good (0-50)', value: 16, pct: 30.8, color: '#2F8F72' },
  { name: 'Moderate (51-100)', value: 18, pct: 34.6, color: '#F4A62A' },
  { name: 'Unhealthy for Sensitive', value: 10, pct: 19.2, color: '#E5913F' },
  { name: 'Unhealthy (151-200)', value: 6, pct: 11.5, color: '#E5483F' },
  { name: 'Very Unhealthy (201+)', value: 2, pct: 3.9, color: '#8B0000' },
]

const trendVsYesterday = [
  { area: 'Gachibowli', change: 12, dir: 'down' },
  { area: 'Jubilee Hills', change: 8, dir: 'down' },
  { area: 'Banjara Hills', change: 5, dir: 'down' },
  { area: 'Kondapur', change: 6, dir: 'up' },
  { area: 'Nacharam', change: 18, dir: 'up' },
  { area: 'Sanathnagar', change: 16, dir: 'up' },
]

const forecastData = [
  { day: 'Today, Jun 12', aqi: 136, pm: 48, status: 'Moderate', color: '#F4A62A' },
  { day: 'Fri, Jun 13', aqi: 142, pm: 52, status: 'Moderate', color: '#F4A62A' },
  { day: 'Sat, Jun 14', aqi: 128, pm: 44, status: 'Moderate', color: '#F4A62A' },
  { day: 'Sun, Jun 15', aqi: 112, pm: 38, status: 'Moderate', color: '#F4A62A' },
  { day: 'Mon, Jun 16', aqi: 98, pm: 32, status: 'Satisfactory', color: '#2F8F72' },
  { day: 'Tue, Jun 17', aqi: 92, pm: 30, status: 'Satisfactory', color: '#2F8F72' },
  { day: 'Wed, Jun 18', aqi: 85, pm: 28, status: 'Satisfactory', color: '#2F8F72' },
]

const advisories = [
  { title: 'Air Quality Advisory', desc: 'Unhealthy air quality in industrial areas (Nacharam & Sanathnagar)', time: '10:05 AM', color: '#E5483F' },
  { title: 'Health Advisory', desc: 'Sensitive groups should limit prolonged outdoor exertion', time: '9:45 AM', color: '#F4A62A' },
  { title: 'Construction Advisory', desc: 'Dust mitigation protocols active near Hitec City metro corridor', time: '9:30 AM', color: '#F4A62A' },
]

export default function Pollution() {
  const [timeRange, setTimeRange] = useState('24 Hours')

  return (
    <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* ── Time Range Bar ───────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {['Live', '1 Hour', '6 Hours', '24 Hours', '7 Days', '30 Days'].map(t => (
          <button key={t} onClick={() => setTimeRange(t)} style={{
            padding: '6px 16px', borderRadius: 'var(--radius-full)',
            fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
            background: timeRange === t ? '#4C9E9B' : 'var(--bg-card)',
            color: timeRange === t ? '#fff' : 'var(--text-secondary)',
            border: timeRange === t ? 'none' : '1px solid var(--border-default)',
          }}>{t}</button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            <span>☀️</span> <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>29°C</span> <span>Clear Skies</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', borderLeft: '1px solid var(--border-default)', paddingLeft: '16px' }}>
            10:18 AM<br />Jun 12, 2025
          </div>
        </div>
      </div>

      {/* ── 1. Top Section: Rebalanced Current AQI Card + Hotspots ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 340px',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* Current AQI Rebalanced Summary Card */}
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '20px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{
              fontSize: '0.85rem',
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.06em',
            }}>
              Current Air Quality Index
            </h3>
            <span style={{
              fontSize: '0.65rem',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
            }}>
              Hyderabad Metropolitan Average · 52 Stations
            </span>
          </div>

          {/* Balanced Horizontal Metric Elements */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '150px 1fr 1fr 1fr 1fr',
            gap: '16px',
            alignItems: 'center',
          }}>
            {/* Circular AQI Gauge */}
            <div style={{ textAlign: 'center' }}>
              <div style={{ position: 'relative', width: 110, height: 110, margin: '0 auto' }}>
                <svg width="110" height="110" viewBox="0 0 110 110">
                  <circle cx="55" cy="55" r="46" fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth="8" />
                  <circle cx="55" cy="55" r="46" fill="none" stroke="#F4A62A" strokeWidth="8"
                    strokeDasharray={`${(136 / 300) * 289} 289`}
                    strokeLinecap="round" transform="rotate(-90 55 55)"
                    style={{ transition: 'stroke-dasharray 1s ease' }}
                  />
                </svg>
                <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <Wind size={16} color="#F4A62A" strokeWidth={1.5} />
                  <span style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'var(--font-heading)', lineHeight: 1 }}>
                    <AnimatedCounter value={136} />
                  </span>
                  <span style={{ fontSize: '0.52rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>US AQI</span>
                </div>
              </div>
              <span style={{
                padding: '2px 10px', borderRadius: 'var(--radius-full)',
                fontSize: '0.6rem', fontWeight: 600,
                background: 'var(--accent-energy-dim)', color: '#B8860B',
                border: '1px solid rgba(244,166,42,0.2)',
                marginTop: '6px', display: 'inline-block',
              }}>
                Moderate
              </span>
            </div>

            {/* Dominant Pollutant */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                DOMINANT POLLUTANT
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-heading)' }}>
                PM2.5
              </div>
              <div style={{ fontSize: '0.75rem', color: '#E5483F', fontWeight: 600 }}>
                48 μg/m³
              </div>
              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Limit: 60 μg/m³
              </div>
            </div>

            {/* AQI Trend (24H) */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                AQI TREND (24H)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ color: '#E5483F', fontWeight: 700, fontSize: '1.2rem', fontFamily: 'var(--font-heading)' }}>
                  ▲ 12%
                </span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                vs yesterday
              </div>
              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Peak at 8:00 PM
              </div>
            </div>

            {/* Sensitive Groups */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                SENSITIVE GROUPS
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                <AlertTriangle size={14} color="#F4A62A" />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                  Unhealthy
                </span>
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '4px', lineHeight: 1.3 }}>
                Limit strenuous outdoor activity
              </div>
            </div>

            {/* Data Coverage */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                DATA COVERAGE
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                <span style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: '#2F8F72' }}>
                  92%
                </span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                48/52 Stations
              </div>
              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Telemetry Live
              </div>
            </div>
          </div>

          {/* Daily Quick Stats Row */}
          <div style={{
            display: 'flex',
            gap: '24px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-divider)',
            fontSize: '0.72rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Daily Max:</span>
              <span style={{ fontWeight: 700, color: '#E5483F', fontFamily: 'var(--font-mono)' }}>176 AQI</span>
              <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>(8:00 PM)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Daily Min:</span>
              <span style={{ fontWeight: 700, color: '#2F8F72', fontFamily: 'var(--font-mono)' }}>68 AQI</span>
              <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>(6:00 AM)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Daily Average:</span>
              <span style={{ fontWeight: 700, color: '#F4A62A', fontFamily: 'var(--font-mono)' }}>124 AQI</span>
              <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>(Moderate)</span>
            </div>
          </div>
        </div>

        {/* AQI Hotspots Card */}
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              AQI Hotspots (Current)
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', cursor: 'pointer' }}>
              VIEW ALL
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
            {hotspots.map((h, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '7px 10px', borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
              }}>
                <div style={{ width: 36, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: h.color, fontFamily: 'var(--font-heading)', lineHeight: 1.1 }}>{h.aqi}</div>
                  <div style={{ fontSize: '0.48rem', color: h.color, fontWeight: 600 }}>{h.status === 'Unhealthy for Sensitive' ? 'Sensitive' : h.status}</div>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {h.area}
                  </div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    PM2.5: {h.pm} μg/m³
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 2. Middle Row: 24h Trend + Pollutant Grid + Top Pollutants ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.2fr 1.3fr 280px',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* AQI Trend Chart */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              AQI Trend (24 Hours)
            </h3>
            <Info size={12} color="var(--text-muted)" />
          </div>
          <ResponsiveContainer width="100%" height={210}>
            <AreaChart data={aqiTrend} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="aqiAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F4A62A" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#F4A62A" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval={4} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} domain={[0, 200]} />
              <ReferenceLine y={50} stroke="rgba(47,143,114,0.3)" strokeDasharray="3 3" />
              <ReferenceLine y={100} stroke="rgba(244,166,42,0.3)" strokeDasharray="3 3" />
              <ReferenceLine y={150} stroke="rgba(229,72,63,0.3)" strokeDasharray="3 3" />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Area type="monotone" dataKey="aqi" stroke="#F4A62A" strokeWidth={1.5} fill="url(#aqiAreaGrad)" name="AQI" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Pollutant Concentration Grid */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Pollutant Concentration (Current)
            </h3>
            <Info size={12} color="var(--text-muted)" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
            {pollutants.map((p, i) => (
              <div key={p.name} style={{
                padding: '10px', borderRadius: 'var(--radius-md)',
                background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
                textAlign: 'center',
              }}>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '2px' }}>{p.name}</div>
                <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-heading)' }}>{p.value}</div>
                <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>{p.unit}</div>
                <div style={{ fontSize: '0.55rem', color: i < 2 ? '#E5483F' : '#2F8F72', fontWeight: 600, marginTop: '2px' }}>
                  {i < 2 ? `▲ ${3 + i * 2}%` : `▼ ${10 - i}%`} vs yday
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Pollutants Breakdown */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Top Pollutants (24H Avg)
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {topPollutants.map(p => (
              <div key={p.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 500, color: 'var(--text-primary)' }}>{p.name}</span>
                  <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{p.value} μg/m³</span>
                </div>
                <div style={{ height: 5, borderRadius: 3, background: 'var(--bg-workspace)', overflow: 'hidden' }}>
                  <div style={{
                    width: `${(p.value / p.max) * 100}%`, height: '100%', borderRadius: 3,
                    background: p.value > 50 ? '#6C8FC5' : '#4C9E9B',
                    transition: 'width 1s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 3. Dedicated Spacious Air Quality Forecast Section ── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        boxShadow: 'var(--shadow-card)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Air Quality Forecast (7-Day Projection)
            </h3>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Predictive neural atmospheric dispersion model for Hyderabad urban basin.
            </p>
          </div>
          <span style={{ fontSize: '0.65rem', color: '#4C9E9B', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
            TSPCB Telemetry Synchronized
          </span>
        </div>

        {/* Generous Forecast Chart with Readable Labels */}
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={forecastData} margin={{ top: 10, right: 20, left: -10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
            <XAxis dataKey="day" tick={{ fontSize: 9, fill: '#17212B', fontWeight: 500 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} domain={[0, 180]} />
            <ReferenceLine y={50} stroke="rgba(47,143,114,0.3)" strokeDasharray="4 4" label={{ value: 'Good', fill: '#2F8F72', fontSize: 9 }} />
            <ReferenceLine y={100} stroke="rgba(244,166,42,0.3)" strokeDasharray="4 4" label={{ value: 'Moderate', fill: '#F4A62A', fontSize: 9 }} />
            <ReferenceLine y={150} stroke="rgba(229,72,63,0.3)" strokeDasharray="4 4" label={{ value: 'Unhealthy', fill: '#E5483F', fontSize: 9 }} />
            <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.72rem', boxShadow: 'var(--shadow-elevated)' }} />
            <Bar dataKey="aqi" radius={[6, 6, 0, 0]} name="Projected AQI">
              {forecastData.map((d, i) => (
                <Cell key={i} fill={d.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>

        {/* 7-Day Day-by-Day Forecast Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(7, 1fr)',
          gap: '10px',
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid var(--border-divider)',
        }}>
          {forecastData.map((f, i) => (
            <div key={i} style={{
              padding: '10px 8px', borderRadius: 'var(--radius-md)',
              background: i === 0 ? 'var(--accent-air-dim)' : 'var(--bg-workspace)',
              border: `1px solid ${i === 0 ? 'rgba(76,158,155,0.3)' : 'var(--border-divider)'}`,
              textAlign: 'center',
            }}>
              <div style={{ fontSize: '0.65rem', fontWeight: 600, color: i === 0 ? '#4C9E9B' : 'var(--text-secondary)' }}>
                {f.day.split(',')[0]}
              </div>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: f.color, fontFamily: 'var(--font-heading)', margin: '4px 0' }}>
                {f.aqi}
              </div>
              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)' }}>
                PM2.5: {f.pm}
              </div>
              <div style={{ fontSize: '0.58rem', fontWeight: 600, color: f.color, marginTop: '2px' }}>
                {f.status}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── 4. Lower Row: AQI Distribution + Trend vs Yesterday + Alerts ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.1fr 1.1fr 1.2fr',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* AQI Distribution */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>
            AQI Distribution (City)
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ position: 'relative', width: 100, height: 100 }}>
              <svg width="100" height="100" viewBox="0 0 100 100">
                {(() => {
                  const r = 38; const c = 2 * Math.PI * r; let off = 0;
                  return distributionData.map(d => {
                    const dash = (d.pct / 100) * c; const o = -off; off += dash;
                    return <circle key={d.name} cx="50" cy="50" r={r} fill="none" stroke={d.color} strokeWidth="12" strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={o} transform="rotate(-90 50 50)" />
                  })
                })()}
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>52</span>
                <span style={{ fontSize: '0.5rem', color: 'var(--text-muted)' }}>Stations</span>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.62rem' }}>
              {distributionData.map(d => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: d.color }} />
                  <span style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>{d.value} ({d.pct}%)</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AQI Trend vs Yesterday */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>
            AQI Trend vs Yesterday (By Area)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {trendVsYesterday.map(t => (
              <div key={t.area} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-primary)', width: '90px', fontWeight: 500 }}>{t.area}</span>
                <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--bg-workspace)', overflow: 'hidden', display: 'flex', justifyContent: t.dir === 'up' ? 'flex-end' : 'flex-start' }}>
                  <div style={{ width: `${t.change * 3}%`, height: '100%', borderRadius: 3, background: t.dir === 'up' ? '#E5483F' : '#2F8F72' }} />
                </div>
                <span style={{ fontSize: '0.6rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: t.dir === 'up' ? '#E5483F' : '#2F8F72', width: '40px', textAlign: 'right' }}>
                  {t.dir === 'up' ? '▲' : '▼'} {t.change}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Alerts & Advisories */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Alerts & Advisories
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {advisories.map((a, i) => (
              <div key={i} style={{ display: 'flex', gap: '8px', padding: '9px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)' }}>
                <AlertTriangle size={15} color={a.color} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 600, color: a.color }}>{a.title}</div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>{a.desc}</div>
                </div>
                <div style={{ fontSize: '0.52rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>{a.time}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 5. Bottom Insight Bar ─────────────────────────── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 24px',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Wind size={16} color="#4C9E9B" />
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Air Quality Tip</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '12px' }}>
              Consider using public transport and carpooling to reduce emissions and improve air quality.
            </span>
          </div>
        </div>
        <button style={{
          padding: '8px 18px', borderRadius: 'var(--radius-md)',
          border: '1px solid #4C9E9B', background: 'transparent',
          color: '#4C9E9B', fontSize: '0.72rem', fontWeight: 600,
          fontFamily: 'var(--font-mono)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap',
        }}>
          View Recommendations <ArrowRight size={12} />
        </button>
      </div>
    </div>
  )
}

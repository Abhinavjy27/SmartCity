import { useState } from 'react'
import {
  Zap, Battery, TrendingUp, Lightbulb, AlertTriangle,
  ArrowRight, Info, ChevronDown, Activity, ShieldAlert, Cpu
} from 'lucide-react'
import AnimatedCounter from '../components/AnimatedCounter'
import {
  AreaChart, Area, Line, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine
} from 'recharts'

/* ── Data ── */
const loadCurve = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  actual: Math.round(1200 + 1600 * Math.exp(-((i - 14) ** 2) / 10) + 800 * Math.exp(-((i - 20) ** 2) / 6) + (Math.random() - 0.5) * 150),
  forecast: Math.round(1100 + 1500 * Math.exp(-((i - 14) ** 2) / 10) + 700 * Math.exp(-((i - 20) ** 2) / 6)),
}))

const demandForecast = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  forecast: Math.round(1100 + 1500 * Math.exp(-((i - 14) ** 2) / 10) + 700 * Math.exp(-((i - 20) ** 2) / 6)),
  optimistic: Math.round(950 + 1300 * Math.exp(-((i - 14) ** 2) / 10) + 600 * Math.exp(-((i - 20) ** 2) / 6)),
  pessimistic: Math.round(1250 + 1700 * Math.exp(-((i - 14) ** 2) / 10) + 850 * Math.exp(-((i - 20) ** 2) / 6)),
}))


const substations = [
  { name: 'HITECH City Substation', load: 420, capacity: 500, util: 84, status: 'Normal' },
  { name: 'Gachibowli Primary Feeder', load: 380, capacity: 500, util: 76, status: 'Normal' },
  { name: 'Balanagar Industrial 220kV', load: 310, capacity: 400, util: 78, status: 'Normal' },
  { name: 'Kukatpally Junction Substation', load: 290, capacity: 400, util: 73, status: 'Normal' },
  { name: 'Nacharam TSIIC Grid Station', load: 270, capacity: 400, util: 68, status: 'Normal' },
  { name: 'Sanathnagar Distribution Unit', load: 240, capacity: 300, util: 80, status: 'High Load' },
  { name: 'Madhapur IT Corridor Feeder', load: 210, capacity: 300, util: 70, status: 'Normal' },
]

const weeklyConsumption = [
  { day: 'Mon', thisWeek: 58, lastWeek: 52 },
  { day: 'Tue', thisWeek: 62, lastWeek: 55 },
  { day: 'Wed', thisWeek: 55, lastWeek: 58 },
  { day: 'Thu', thisWeek: 72, lastWeek: 60 },
  { day: 'Fri', thisWeek: 68, lastWeek: 63 },
  { day: 'Sat', thisWeek: 45, lastWeek: 42 },
  { day: 'Sun', thisWeek: 38, lastWeek: 35 },
]

const renewableData = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  solar: Math.max(0, Math.round(400 * Math.exp(-((i - 13) ** 2) / 8))),
  wind: Math.round(80 + 60 * Math.sin(i * 0.5) + (Math.random() - 0.5) * 30),
  hydro: Math.round(100 + (Math.random() - 0.5) * 20),
}))

const alerts = [
  { title: 'High Load Alert', desc: 'Sanathnagar Substation\nUtilization: 80%', time: '10:12 AM', color: '#E5483F' },
  { title: 'Voltage Deviation', desc: 'Balanagar Feeder 3\nVoltage: ±3%', time: '10:05 AM', color: '#F4A62A' },
  { title: 'Transformer Overload', desc: 'Kukatpally 220/33kV\nLoad: 92%', time: '10:05 AM', color: '#F4A62A' },
]

const anomalies = [
  { title: 'Unusual Load Spike', desc: 'Detected in LB Nagar residential area\n+18% above historical average', time: '10:15 AM', color: '#E5483F' },
  { title: 'Sudden Demand Drop', desc: 'Detected in Hitec City Feeder 4\n-15% below forecast baseline', time: '10:07 AM', color: '#2F8F72' },
]

export default function Energy() {
  const [timeRange, setTimeRange] = useState('24 Hours')

  return (
    <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* ── Time Range Bar ───────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {['Live', '1 Hour', '6 Hours', '24 Hours', '7 Days', '30 Days'].map(t => (
          <button key={t} onClick={() => setTimeRange(t)} style={{
            padding: '6px 16px', borderRadius: 'var(--radius-full)',
            fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
            background: timeRange === t ? '#F4A62A' : 'var(--bg-card)',
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

      {/* ── 1. KPI Strip (6 Key Operational Metrics) ──────── */}
      <div style={{
        display: 'flex',
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px 8px',
        boxShadow: 'var(--shadow-card)',
        gap: 0,
        overflowX: 'auto',
      }}>
        {[
          { icon: Zap, label: 'TOTAL GRID LOAD', value: '2,842', unit: 'MW', trend: '▲ 6.4% vs yesterday', tColor: '#2F8F72' },
          { icon: Activity, label: 'PEAK DEMAND (TODAY)', value: '3,450', unit: 'MW', sub: '4:45 PM (Forecast)', tColor: '' },
          { icon: Battery, label: 'ENERGY CONSUMED', value: '58.7', unit: 'GWh', trend: '▲ 5.2% vs yesterday', tColor: '#E5483F' },
          { icon: TrendingUp, label: 'RENEWABLE SHARE', value: '28.6', unit: '%', trend: '▲ 3.1% vs yesterday', tColor: '#2F8F72' },
          { icon: Cpu, label: 'FREQUENCY', value: '49.98', unit: 'Hz', sub: 'Normal Grid State' },
          { icon: Lightbulb, label: 'GRID EFFICIENCY', value: '92.4', unit: '%', trend: '▲ 2.3% vs yesterday', tColor: '#2F8F72' },
        ].map((kpi, idx, arr) => {
          const Icon = kpi.icon
          return (
            <div key={kpi.label} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: '165px' }}>
              <div style={{ padding: '0 16px', flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <Icon size={16} color="var(--text-muted)" strokeWidth={1.5} />
                  <span style={{ fontSize: '0.58rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
                    {kpi.label}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                  <span style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                    {kpi.value}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{kpi.unit}</span>
                </div>
                {kpi.trend && <div style={{ fontSize: '0.58rem', color: kpi.tColor, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{kpi.trend}</div>}
                {kpi.sub && <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)' }}>{kpi.sub}</div>}
              </div>
              {idx < arr.length - 1 && <div style={{ width: '1px', height: '48px', background: 'var(--border-default)', flexShrink: 0 }} />}
            </div>
          )
        })}
      </div>

      {/* ── 2. Row 1: Load Curve + Demand Forecast (Spacious 2-Column Grid) ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* Load Curve (Today) */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Load Curve (Today)
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.65rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ width: 10, height: 3, background: '#2F8F72', borderRadius: 2 }} />
                <span>Actual Load (MW)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ width: 10, height: 2, background: '#8F9295', borderRadius: 2 }} />
                <span>Forecast (MW)</span>
              </div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={loadCurve} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2F8F72" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#2F8F72" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit=" MW" />
              <ReferenceLine y={2842} stroke="#2F8F72" strokeDasharray="3 3" label={{ value: 'Current: 2,842 MW', fill: '#2F8F72', fontSize: 9, position: 'insideTopLeft' }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.72rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Area type="monotone" dataKey="actual" stroke="#2F8F72" strokeWidth={2} fill="url(#loadGrad)" name="Actual Load" />
              <Line type="monotone" dataKey="forecast" stroke="#8F9295" strokeWidth={1.5} strokeDasharray="4 3" dot={false} name="Forecast" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Demand Forecast */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)',
          display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
                Demand Forecast
              </h3>
              <Info size={13} color="var(--text-muted)" />
            </div>
            <div style={{ display: 'flex', gap: '16px' }}>
              <div><span style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>3,450 <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>MW</span></span> <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>Expected Peak</span></div>
              <div><span style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: '#F4A62A' }}>4:45 PM</span> <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>Today</span></div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={demandForecast} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit=" MW" />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.72rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Area type="monotone" dataKey="pessimistic" stroke="transparent" fill="rgba(229,72,63,0.08)" name="Pessimistic Envelope" />
              <Area type="monotone" dataKey="optimistic" stroke="transparent" fill="rgba(47,143,114,0.08)" name="Optimistic Envelope" />
              <Line type="monotone" dataKey="forecast" stroke="#F4A62A" strokeWidth={2} dot={false} name="Forecasted Peak" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── 3. Substation Performance Table ───────── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        boxShadow: 'var(--shadow-card)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
            Substation Performance Matrix
          </h3>
          <span style={{ fontSize: '0.65rem', color: '#F4A62A', fontWeight: 600, fontFamily: 'var(--font-mono)', cursor: 'pointer' }}>
            VIEW ALL SUBSTATIONS &gt;
          </span>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem' }}>
          <thead>
            <tr>
              {['SUBSTATION NAME', 'CURRENT LOAD (MW)', 'CAPACITY (MW)', 'UTILIZATION', 'OPERATIONAL STATUS'].map(h => (
                <th key={h} style={{
                  textAlign: 'left', padding: '8px 6px', fontSize: '0.6rem',
                  color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
                  fontWeight: 600, letterSpacing: '0.06em', borderBottom: '1px solid var(--border-divider)'
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {substations.map(s => (
              <tr key={s.name}>
                <td style={{ padding: '10px 6px', fontWeight: 600, color: 'var(--text-primary)' }}>{s.name}</td>
                <td style={{ padding: '10px 6px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{s.load} MW</td>
                <td style={{ padding: '10px 6px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{s.capacity} MW</td>
                <td style={{ padding: '10px 6px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ width: '100px', height: 6, borderRadius: 3, background: 'var(--bg-workspace)', overflow: 'hidden' }}>
                      <div style={{ width: `${s.util}%`, height: '100%', borderRadius: 3, background: s.util > 79 ? '#E5483F' : '#2F8F72' }} />
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', fontWeight: 600 }}>{s.util}%</span>
                  </div>
                </td>
                <td style={{ padding: '10px 6px' }}>
                  <span style={{
                    fontSize: '0.62rem', fontWeight: 600,
                    padding: '3px 8px', borderRadius: 'var(--radius-full)',
                    background: s.status === 'Normal' ? 'rgba(47,143,114,0.1)' : 'rgba(229,72,63,0.1)',
                    color: s.status === 'Normal' ? '#2F8F72' : '#E5483F',
                    border: `1px solid ${s.status === 'Normal' ? 'rgba(47,143,114,0.2)' : 'rgba(229,72,63,0.2)'}`,
                  }}>
                    {s.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── 5. Row 4: Energy Consumption Trend + Renewable Generation Trend ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* Weekly Energy Consumption Trend */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Energy Consumption Trend (Weekly)
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Unit: GWh</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={weeklyConsumption} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 9, fill: '#8F9295' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit=" GWh" />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.72rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Bar dataKey="thisWeek" fill="#F4A62A" radius={[4, 4, 0, 0]} name="This Week" />
              <Bar dataKey="lastWeek" fill="rgba(0,0,0,0.08)" radius={[4, 4, 0, 0]} name="Last Week" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Renewable Generation Trend */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Renewable Generation Stack (24H)
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>% Share</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={renewableData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval={4} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.72rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Area type="monotone" dataKey="solar" stackId="1" stroke="#F4A62A" fill="rgba(244,166,42,0.3)" name="Solar (MW)" />
              <Area type="monotone" dataKey="wind" stackId="1" stroke="#4C9E9B" fill="rgba(76,158,155,0.3)" name="Wind (MW)" />
              <Area type="monotone" dataKey="hydro" stackId="1" stroke="#6C8FC5" fill="rgba(108,143,197,0.3)" name="Hydro (MW)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── 6. Row 5: Active Alerts + Anomaly Detection ──── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* Active Alerts */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Active Grid Alerts
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL &gt;</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {alerts.map((a, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '12px', padding: '12px',
                borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
              }}>
                <AlertTriangle size={16} color={a.color} style={{ flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: a.color }}>{a.title}</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', whiteSpace: 'pre-line' }}>{a.desc}</div>
                </div>
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{a.time}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Anomaly Detection */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Telemetry Anomaly Detection
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL &gt;</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {anomalies.map((a, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '12px', padding: '12px',
                borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
              }}>
                <Cpu size={16} color="#2563EB" style={{ flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>{a.title}</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', whiteSpace: 'pre-line' }}>{a.desc}</div>
                </div>
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{a.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 7. Bottom Insight Bar ─────────────────────────── */}
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
          <Zap size={16} color="#F4A62A" />
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Energy Insight</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '12px' }}>
              Renewable share increased by 3.1% compared to yesterday. Solar generation is performing 12% above forecast.
            </span>
          </div>
        </div>
        <button style={{
          padding: '8px 18px', borderRadius: 'var(--radius-md)',
          border: '1px solid #F4A62A', background: 'transparent',
          color: '#F4A62A', fontSize: '0.72rem', fontWeight: 600,
          fontFamily: 'var(--font-mono)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap',
        }}>
          View Detailed Report <ArrowRight size={12} />
        </button>
      </div>
    </div>
  )
}

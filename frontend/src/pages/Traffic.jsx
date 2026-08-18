import { Car, Gauge, Timer, Radio, AlertTriangle, TrendingUp, MapPin } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import AnimatedCounter from '../components/AnimatedCounter'
import ProblemSolverSection from '../components/ProblemSolverSection'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell
} from 'recharts'

const sensors = [
  { id: 'SENSOR_01', name: 'Gachibowli Flyover', speed: 18.5, volume: 3420, occ: 87.2, congestion: 'HEAVY' },
  { id: 'SENSOR_02', name: 'HITECH City Mindspace', speed: 15.2, volume: 3890, occ: 91.3, congestion: 'HEAVY' },
  { id: 'SENSOR_03', name: 'Jubilee Hills Checkpost', speed: 22.1, volume: 3100, occ: 72.4, congestion: 'MODERATE' },
  { id: 'SENSOR_04', name: 'Punjagutta Junction', speed: 12.8, volume: 4180, occ: 94.1, congestion: 'HEAVY' },
  { id: 'SENSOR_05', name: 'Begumpet Airport Flyover', speed: 28.3, volume: 2890, occ: 65.8, congestion: 'MODERATE' },
  { id: 'SENSOR_06', name: 'Secunderabad Paradise', speed: 31.2, volume: 2450, occ: 58.2, congestion: 'MODERATE' },
  { id: 'SENSOR_07', name: 'Koti Women\'s College', speed: 14.6, volume: 3050, occ: 88.7, congestion: 'HEAVY' },
  { id: 'SENSOR_08', name: 'Charminar Madina', speed: 9.8, volume: 2780, occ: 96.2, congestion: 'HEAVY' },
  { id: 'SENSOR_09', name: 'LB Nagar Ring Road', speed: 42.5, volume: 3200, occ: 48.3, congestion: 'SMOOTH' },
  { id: 'SENSOR_10', name: 'Kukatpally Y Junction', speed: 24.7, volume: 3650, occ: 76.1, congestion: 'MODERATE' },
  { id: 'SENSOR_11', name: 'Miyapur Metro Station', speed: 38.1, volume: 2700, occ: 52.4, congestion: 'SMOOTH' },
  { id: 'SENSOR_12', name: 'Mehdipatnam Bus Station', speed: 16.3, volume: 3480, occ: 85.3, congestion: 'HEAVY' },
  { id: 'SENSOR_13', name: 'Ameerpet Metro', speed: 13.5, volume: 3920, occ: 92.8, congestion: 'HEAVY' },
  { id: 'SENSOR_14', name: 'Banjara Hills Road No 1', speed: 26.8, volume: 2950, occ: 68.9, congestion: 'MODERATE' },
  { id: 'SENSOR_15', name: 'Toli Chowki Flyover', speed: 33.4, volume: 2680, occ: 55.1, congestion: 'SMOOTH' },
]

const hourlyData = Array.from({ length: 24 }, (_, i) => ({
  h: `${String(i).padStart(2, '0')}:00`,
  speed: Math.max(10, 55 - 35 * Math.exp(-((i - 9) ** 2) / 4) - 30 * Math.exp(-((i - 18) ** 2) / 5) + (Math.random() - 0.5) * 8),
  volume: Math.round(800 + 2800 * Math.exp(-((i - 9) ** 2) / 4) + 2200 * Math.exp(-((i - 18) ** 2) / 5) + (Math.random() - 0.5) * 300),
}))

const corridorData = [
  { name: 'IT Corridor', value: 88, color: '#f43f5e' },
  { name: 'Old City', value: 92, color: '#f43f5e' },
  { name: 'Secunderabad', value: 58, color: '#f59e0b' },
  { name: 'Kukatpally', value: 72, color: '#f59e0b' },
  { name: 'LB Nagar', value: 45, color: '#10b981' },
  { name: 'Miyapur', value: 38, color: '#10b981' },
]

export default function Traffic() {
  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><Car size={28} /> Traffic Intelligence</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <StatusBadge status="AI" />
          <span className="badge badge-info">15 Active Sensors</span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid-kpi">
        <MetricCard icon={Gauge} label="Avg Network Speed" value={23.67} suffix=" km/h" decimals={2} color="cyan" trend="down" trendValue="-15%" />
        <MetricCard icon={Car} label="Total Vehicles" value={2342} color="violet" trend="up" trendValue="+12%" />
        <MetricCard icon={Timer} label="Avg Delay" value={87.64} suffix="s" decimals={0} color="amber" trend="up" trendValue="+23%" />
        <MetricCard icon={Radio} label="Signal Optimizations" value={106} color="emerald" subtitle="AI Adaptive Controller" />
      </div>

      {/* Charts Row */}
      <div className="grid-dashboard" style={{ marginTop: 'var(--space-xl)' }}>
        <GlassCard>
          <div className="section-title">24h Speed & Volume Forecast</div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={hourlyData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tSpeed" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00f0ff" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#00f0ff" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" />
              <XAxis dataKey="h" tick={{ fontSize: 10, fill: '#64748b' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
              <Area type="monotone" dataKey="speed" stroke="#00f0ff" strokeWidth={2} fill="url(#tSpeed)" name="Speed (km/h)" />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard>
          <div className="section-title">Corridor Congestion Index</div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={corridorData} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} width={100} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
              <Bar dataKey="value" radius={[0, 6, 6, 0]} name="Congestion %">
                {corridorData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>

      {/* Sensor Table */}
      <GlassCard style={{ marginTop: 'var(--space-xl)', overflow: 'auto' }}>
        <div className="section-title">Live Sensor Data — 15 Hyderabad Intersections</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Sensor ID</th>
              <th>Location</th>
              <th>Speed (km/h)</th>
              <th>Volume (vph)</th>
              <th>Occupancy %</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sensors.map(s => (
              <tr key={s.id}>
                <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', fontSize: '0.8rem' }}>{s.id}</td>
                <td style={{ color: 'var(--text-primary)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <MapPin size={12} color="var(--text-muted)" />{s.name}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', color: s.speed < 15 ? 'var(--accent-rose)' : s.speed < 30 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>{s.speed}</td>
                <td style={{ fontFamily: 'var(--font-mono)' }}>{s.volume.toLocaleString()}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--bg-primary)', maxWidth: 80, overflow: 'hidden' }}>
                      <div style={{
                        width: `${s.occ}%`, height: '100%', borderRadius: 3,
                        background: s.occ > 85 ? 'var(--accent-rose)' : s.occ > 65 ? 'var(--accent-amber)' : 'var(--accent-emerald)',
                        transition: 'width 1s ease',
                      }} />
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>{s.occ}%</span>
                  </div>
                </td>
                <td><StatusBadge status={s.congestion} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </GlassCard>

      {/* AI Multi-Suggestion Problem Solver Module */}
      <ProblemSolverSection initialProblemId="PROB_01" />
    </div>
  )
}

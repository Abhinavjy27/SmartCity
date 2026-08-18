import { Wind, Droplets, Flame, CloudRain, Factory, Thermometer, MapPin } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import AQIGauge from '../components/AQIGauge'
import AnimatedCounter from '../components/AnimatedCounter'
import ProblemSolverSection from '../components/ProblemSolverSection'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const aqiTrend = Array.from({ length: 24 }, (_, i) => ({
  h: `${String(i).padStart(2, '0')}:00`,
  aqi: Math.round(80 + 60 * Math.exp(-((i - 8) ** 2) / 8) + 45 * Math.exp(-((i - 20) ** 2) / 6) + (Math.random() - 0.5) * 20),
  pm25: Math.round(30 + 40 * Math.exp(-((i - 8) ** 2) / 8) + 30 * Math.exp(-((i - 20) ** 2) / 6) + (Math.random() - 0.5) * 10),
}))

const pollutants = [
  { name: 'PM2.5', value: 78.5, unit: 'μg/m³', limit: 60, icon: Droplets, color: 'rose' },
  { name: 'PM10', value: 115.9, unit: 'μg/m³', limit: 100, icon: Wind, color: 'amber' },
  { name: 'CO', value: 1189, unit: 'μg/m³', limit: 2000, icon: Flame, color: 'emerald' },
  { name: 'NO₂', value: 45.0, unit: 'μg/m³', limit: 80, icon: Factory, color: 'violet' },
  { name: 'SO₂', value: 17.0, unit: 'μg/m³', limit: 80, icon: CloudRain, color: 'blue' },
  { name: 'O₃', value: 53.0, unit: 'μg/m³', limit: 100, icon: Thermometer, color: 'cyan' },
]

const stations = [
  { name: 'Central University', aqi: 128, status: 'MODERATE_AQI', pm25: 72.3 },
  { name: 'Sanathnagar', aqi: 156, status: 'POOR', pm25: 94.1 },
  { name: 'Zoo Park', aqi: 142, status: 'MODERATE_AQI', pm25: 82.7 },
  { name: 'Somajiguda', aqi: 118, status: 'MODERATE_AQI', pm25: 65.4 },
  { name: 'Kokapet', aqi: 95, status: 'SATISFACTORY', pm25: 48.2 },
  { name: 'Bollarum Industrial', aqi: 178, status: 'POOR', pm25: 112.8 },
  { name: 'Kompally', aqi: 134, status: 'MODERATE_AQI', pm25: 76.9 },
  { name: 'ECIL Kapra', aqi: 145, status: 'MODERATE_AQI', pm25: 85.3 },
  { name: 'ICRISAT Patancheru', aqi: 102, status: 'MODERATE_AQI', pm25: 55.1 },
  { name: 'IDA Pashamylaram', aqi: 168, status: 'POOR', pm25: 105.7 },
  { name: 'Nacharam TSIIC', aqi: 139, status: 'MODERATE_AQI', pm25: 79.8 },
  { name: 'New Malakpet', aqi: 151, status: 'POOR', pm25: 91.4 },
  { name: 'Ramachandrapuram', aqi: 112, status: 'MODERATE_AQI', pm25: 61.3 },
]

export default function Pollution() {
  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><Wind size={28} /> Air Quality Command</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <StatusBadge status="AI" />
          <span className="badge badge-moderate">13 TSPCB Stations</span>
        </div>
      </div>

      {/* AQI Gauge + Pollutant Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 'var(--space-xl)' }}>
        <GlassCard style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }} glow="amber">
          <div className="section-title" style={{ alignSelf: 'flex-start' }}>Current AQI</div>
          <AQIGauge value={136} size={220} />
          <div style={{ marginTop: '12px', textAlign: 'center' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Hyderabad Avg · Last Updated 17:45 IST
            </div>
          </div>
        </GlassCard>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-md)' }}>
          {pollutants.map(p => {
            const Icon = p.icon
            const isOver = p.value > p.limit
            return (
              <GlassCard key={p.name}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: 'var(--radius-sm)',
                    background: `var(--accent-${p.color}-dim)`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    <Icon size={18} color={`var(--accent-${p.color})`} />
                  </div>
                  {isOver && <span className="badge badge-heavy" style={{ fontSize: '0.6rem', padding: '2px 6px' }}>EXCEEDS</span>}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '2px' }}>{p.name}</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: isOver ? 'var(--accent-rose)' : 'var(--text-primary)' }}>
                  <AnimatedCounter value={p.value} decimals={1} />
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {p.unit} · Limit: {p.limit}
                </div>
                {/* Progress bar */}
                <div style={{ marginTop: '8px', height: 4, borderRadius: 2, background: 'var(--bg-primary)', overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.min((p.value / p.limit) * 100, 100)}%`, height: '100%', borderRadius: 2,
                    background: isOver ? 'var(--accent-rose)' : `var(--accent-${p.color})`,
                    transition: 'width 1.5s ease',
                  }} />
                </div>
              </GlassCard>
            )
          })}
        </div>
      </div>

      {/* AQI Timeline */}
      <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
        <div className="section-title">24h AQI & PM2.5 Trend</div>
        <ResponsiveContainer width="100%" height={250}>
          <AreaChart data={aqiTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="gAQI" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gPM" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#f43f5e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" />
            <XAxis dataKey="h" tick={{ fontSize: 10, fill: '#64748b' }} interval={3} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
            <Area type="monotone" dataKey="aqi" stroke="#f59e0b" strokeWidth={2} fill="url(#gAQI)" name="AQI" />
            <Area type="monotone" dataKey="pm25" stroke="#f43f5e" strokeWidth={2} fill="url(#gPM)" name="PM2.5 (μg/m³)" />
          </AreaChart>
        </ResponsiveContainer>
      </GlassCard>

      {/* Station Grid */}
      <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
        <div className="section-title">TSPCB Monitoring Stations</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '12px' }}>
          {stations.map(s => (
            <div key={s.name} style={{
              padding: '14px', borderRadius: 'var(--radius-md)',
              background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
              transition: 'all var(--transition-fast)', cursor: 'default',
            }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-hover)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-default)'}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                <MapPin size={12} color="var(--text-muted)" />
                <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>{s.name}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                <div>
                  <span style={{ fontSize: '1.5rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: s.aqi > 150 ? 'var(--accent-rose)' : s.aqi > 100 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                    {s.aqi}
                  </span>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginLeft: '4px' }}>AQI</span>
                </div>
                <StatusBadge status={s.status} />
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                PM2.5: {s.pm25} μg/m³
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* AI Multi-Suggestion Problem Solver Module */}
      <ProblemSolverSection initialProblemId="PROB_02" />
    </div>
  )
}

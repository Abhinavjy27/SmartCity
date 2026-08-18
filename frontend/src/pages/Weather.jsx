import { CloudSun, Thermometer, Droplets, Wind, Eye, Gauge, CloudRain, Sun, Cloud, CloudLightning } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import AnimatedCounter from '../components/AnimatedCounter'
import ProblemSolverSection from '../components/ProblemSolverSection'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts'

const hourlyTemp = Array.from({ length: 24 }, (_, i) => ({
  h: `${String(i).padStart(2, '0')}:00`,
  temp: Math.round((28 + 8 * Math.sin((i - 6) * Math.PI / 12) + (Math.random() - 0.5) * 2) * 10) / 10,
  humidity: Math.round(60 - 20 * Math.sin((i - 6) * Math.PI / 12) + (Math.random() - 0.5) * 5),
}))

const precipData = Array.from({ length: 7 }, (_, i) => {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  return { day: days[i], rain: Math.round(Math.random() * 25 * 10) / 10 }
})

const forecast = [
  { day: 'Today', high: 34, low: 26, icon: Sun, condition: 'Partly Cloudy', rain: '10%' },
  { day: 'Tomorrow', high: 33, low: 25, icon: Cloud, condition: 'Overcast', rain: '35%' },
  { day: 'Wed', high: 31, low: 24, icon: CloudRain, condition: 'Light Rain', rain: '65%' },
  { day: 'Thu', high: 30, low: 23, icon: CloudLightning, condition: 'Thunderstorm', rain: '80%' },
  { day: 'Fri', high: 32, low: 24, icon: CloudRain, condition: 'Scattered Rain', rain: '55%' },
  { day: 'Sat', high: 33, low: 25, icon: Cloud, condition: 'Cloudy', rain: '25%' },
  { day: 'Sun', high: 35, low: 26, icon: Sun, condition: 'Sunny', rain: '5%' },
]

const correlations = [
  { param: 'Temperature → AQI', correlation: '+0.72', direction: 'up', insight: 'Higher temps increase ground-level ozone' },
  { param: 'Humidity → PM2.5', correlation: '-0.58', direction: 'down', insight: 'Moisture helps settle particulate matter' },
  { param: 'Wind Speed → AQI', correlation: '-0.65', direction: 'down', insight: 'Wind disperses pollutants from urban core' },
  { param: 'Rainfall → Traffic Speed', correlation: '-0.41', direction: 'down', insight: 'Rain slows traffic by ~15% on average' },
]

export default function Weather() {
  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><CloudSun size={28} /> Weather Intelligence</h1>
        <StatusBadge status="ONLINE" />
      </div>

      {/* Current Conditions */}
      <div className="grid-kpi">
        <MetricCard icon={Thermometer} label="Temperature" value={33.2} suffix="°C" decimals={1} color="amber" trend="up" trendValue="+1.5°" subtitle="Feels Like: 37°C" />
        <MetricCard icon={Droplets} label="Humidity" value={62} suffix="%" color="blue" trend="down" trendValue="-4%" subtitle="Dew Point: 22°C" />
        <MetricCard icon={Wind} label="Wind Speed" value={12.4} suffix=" km/h" decimals={1} color="cyan" subtitle="Direction: SSE" />
        <MetricCard icon={Gauge} label="Pressure" value={1012} suffix=" hPa" color="violet" trend="down" trendValue="-2 hPa" />
      </div>

      {/* 7-Day Forecast Strip */}
      <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
        <div className="section-title">7-Day Forecast</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '8px' }}>
          {forecast.map((f, i) => {
            const Icon = f.icon
            return (
              <div key={f.day} style={{
                padding: '16px 12px', borderRadius: 'var(--radius-md)',
                background: i === 0 ? 'var(--accent-cyan-dim)' : 'var(--bg-primary)',
                border: `1px solid ${i === 0 ? 'rgba(0,240,255,0.3)' : 'var(--border-default)'}`,
                textAlign: 'center',
                transition: 'all var(--transition-fast)',
                cursor: 'default',
              }}
                onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
                onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
              >
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: i === 0 ? 'var(--accent-cyan)' : 'var(--text-primary)', marginBottom: '8px' }}>
                  {f.day}
                </div>
                <Icon size={28} color={i === 0 ? 'var(--accent-cyan)' : 'var(--text-muted)'} style={{ marginBottom: '8px' }} />
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '6px' }}>{f.condition}</div>
                <div style={{ fontFamily: 'var(--font-mono)' }}>
                  <span style={{ fontSize: '1rem', fontWeight: 700 }}>{f.high}°</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}> / {f.low}°</span>
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                  💧 {f.rain}
                </div>
              </div>
            )
          })}
        </div>
      </GlassCard>

      {/* Charts */}
      <div className="grid-dashboard" style={{ marginTop: 'var(--space-xl)' }}>
        <GlassCard>
          <div className="section-title">24h Temperature & Humidity</div>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={hourlyTemp} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gTemp" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gHum" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" />
              <XAxis dataKey="h" tick={{ fontSize: 10, fill: '#64748b' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
              <Area type="monotone" dataKey="temp" stroke="#f59e0b" strokeWidth={2} fill="url(#gTemp)" name="Temperature (°C)" />
              <Area type="monotone" dataKey="humidity" stroke="#3b82f6" strokeWidth={2} fill="url(#gHum)" name="Humidity (%)" />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard>
          <div className="section-title">Weekly Precipitation</div>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={precipData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} unit="mm" />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
              <Bar dataKey="rain" fill="#3b82f6" radius={[6, 6, 0, 0]} name="Rainfall (mm)" />
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>

      {/* Weather-City Correlations */}
      <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
        <div className="section-title">Cross-Domain Weather Correlations</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
          {correlations.map((c, i) => (
            <div key={i} style={{
              padding: '14px', borderRadius: 'var(--radius-md)',
              background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{c.param}</span>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: '0.9rem',
                  color: c.direction === 'up' ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                }}>
                  {c.correlation}
                </span>
              </div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{c.insight}</p>
            </div>
          ))}
        </div>
      </GlassCard>

      {/* AI Multi-Suggestion Problem Solver Module */}
      <ProblemSolverSection initialProblemId="PROB_04" />
    </div>
  )
}

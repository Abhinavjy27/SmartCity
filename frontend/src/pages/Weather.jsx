import { useState } from 'react'
import { CloudSun, Thermometer, Droplets, Wind, Gauge, CloudRain, Sun, Cloud, CloudLightning, AlertTriangle, ArrowRight, Info, Compass, Moon } from 'lucide-react'
import AnimatedCounter from '../components/AnimatedCounter'
import {
  AreaChart, Area, LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ComposedChart
} from 'recharts'

/* ── Data ── */
const hourlyForecast = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  temp: Math.round((28 + 8 * Math.sin((i - 6) * Math.PI / 12)) * 10) / 10,
  rain: Math.max(0, Math.round(Math.max(0, 20 * Math.exp(-((i - 22) ** 2) / 8)) + (Math.random() - 0.7) * 10)),
}))

const weekForecast = [
  { day: 'Today', weather: '☀️', maxMin: '34° / 24°', rain: '0%' },
  { day: 'Fri, Jun 13', weather: '⛅', maxMin: '35° / 24°', rain: '5%' },
  { day: 'Sat, Jun 14', weather: '🌥️', maxMin: '33° / 23°', rain: '25%' },
  { day: 'Sun, Jun 15', weather: '🌧️', maxMin: '31° / 23°', rain: '60%' },
  { day: 'Mon, Jun 16', weather: '🌧️', maxMin: '30° / 22°', rain: '70%' },
  { day: 'Tue, Jun 17', weather: '⛅', maxMin: '31° / 22°', rain: '20%' },
  { day: 'Wed, Jun 18', weather: '☀️', maxMin: '33° / 23°', rain: '10%' },
]

const rainfallWeek = [
  { day: 'Mon', thisWeek: 0, lastWeek: 5 },
  { day: 'Tue', thisWeek: 2, lastWeek: 8 },
  { day: 'Wed', thisWeek: 0, lastWeek: 3 },
  { day: 'Thu', thisWeek: 10, lastWeek: 12 },
  { day: 'Fri', thisWeek: 8, lastWeek: 6 },
  { day: 'Sat', thisWeek: 15, lastWeek: 18 },
  { day: 'Sun', thisWeek: 12, lastWeek: 4 },
]

const humidityPressure = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  humidity: Math.round(60 - 20 * Math.sin((i - 6) * Math.PI / 12) + (Math.random() - 0.5) * 5),
  pressure: Math.round(1008 + 6 * Math.sin((i - 12) * Math.PI / 12) + (Math.random() - 0.5) * 2),
}))

const weatherAlerts = [
  { title: 'Thunderstorm Watch', desc: 'Moderate thunderstorms likely in Hyderabad & surrounding areas', time: '10:05 AM', color: '#F4A62A' },
  { title: 'High Temperature Alert', desc: 'Day temperatures expected to reach 34°C - 36°C', time: '9:30 AM', color: '#E5483F' },
]

const windDirections = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

export default function Weather() {
  const [timeRange, setTimeRange] = useState('24 Hours')

  return (
    <div className="stagger-children">
      {/* Time Range Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: 'var(--space-lg)', flexWrap: 'wrap' }}>
        {['Now', '1 Hour', '6 Hours', '24 Hours', '7 Days', '15 Days'].map(t => (
          <button key={t} onClick={() => setTimeRange(t)} style={{
            padding: '6px 16px', borderRadius: 'var(--radius-full)',
            fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
            background: timeRange === t ? '#6C8FC5' : 'var(--bg-card)',
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

      {/* Top Row: Current Weather + Today's Summary + Weather Alerts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 300px', gap: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        {/* Current Weather */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '16px' }}>Current Weather</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            <Sun size={40} color="#F4A62A" strokeWidth={1.5} />
            <div>
              <div style={{ fontSize: '2.8rem', fontWeight: 700, fontFamily: 'var(--font-heading)', lineHeight: 1 }}>29°C</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Feels like 31°C</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Clear Skies</div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.72rem' }}>
            {[
              { icon: Droplets, label: 'Humidity', value: '48%' },
              { icon: Wind, label: 'Wind', value: '12 km/h NE' },
              { icon: Gauge, label: 'Pressure', value: '1012 hPa' },
              { icon: Sun, label: 'Visibility', value: '10 km' },
              { icon: Thermometer, label: 'Dew Point', value: '17°C' },
              { icon: Sun, label: 'UV Index', value: '6 High' },
            ].map(d => {
              const Icon = d.icon
              return (
                <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Icon size={13} color="var(--text-muted)" strokeWidth={1.5} />
                  <span style={{ color: 'var(--text-muted)' }}>{d.label}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', marginLeft: 'auto' }}>{d.value}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Today's Summary */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '16px' }}>Today's Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '16px' }}>
            {[
              { label: 'Max Temp', value: '34°C', sub: '2:30 PM', icon: '🌡️', color: '#E5483F' },
              { label: 'Min Temp', value: '24°C', sub: '5:30 AM', icon: '🌡️', color: '#6C8FC5' },
              { label: 'Rainfall', value: '0 mm', sub: '0%', icon: '🌧️', color: 'var(--text-primary)' },
              { label: 'Wind Gust', value: '28 km/h', sub: '3:00 PM', icon: '💨', color: 'var(--text-primary)' },
            ].map(s => (
              <div key={s.label} style={{ textAlign: 'center', padding: '14px 8px', borderRadius: 'var(--radius-md)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)' }}>
                <span style={{ fontSize: '1.2rem' }}>{s.icon}</span>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '6px' }}>{s.label}</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: s.color, fontFamily: 'var(--font-heading)', marginTop: '2px' }}>{s.value}</div>
                <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '2px' }}>{s.sub}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Weather Alerts */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Weather Alerts</h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL</span>
          </div>
          {weatherAlerts.map((a, i) => (
            <div key={i} style={{ display: 'flex', gap: '10px', padding: '12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)', marginBottom: '10px' }}>
              <AlertTriangle size={16} color={a.color} style={{ flexShrink: 0, marginTop: '2px' }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: a.color }}>{a.title}</div>
                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>{a.desc}</div>
              </div>
              <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>{a.time}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Middle Row: 24h Forecast + 7-Day Forecast + Rainfall Overview */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr', gap: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        {/* 24-Hour Forecast */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>24-Hour Forecast</h3>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={hourlyForecast} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tempGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#E5483F" stopOpacity={0.1} />
                  <stop offset="100%" stopColor="#E5483F" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 7, fill: '#8F9295' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis yAxisId="temp" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit="°C" />
              <YAxis yAxisId="rain" orientation="right" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit="%" domain={[0, 100]} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem', boxShadow: 'var(--shadow-elevated)' }} />
              <Area yAxisId="temp" type="monotone" dataKey="temp" stroke="#E5483F" strokeWidth={1.5} fill="url(#tempGrad)" name="Temperature (°C)" />
              <Bar yAxisId="rain" dataKey="rain" fill="rgba(108,143,197,0.3)" radius={[2, 2, 0, 0]} name="Chance of Rain (%)" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* 7-Day Forecast */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>7-Day Forecast</h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
            <thead>
              <tr>
                {['DAY', 'WEATHER', 'MAX / MIN', 'RAIN'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '5px 3px', fontSize: '0.52rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600, letterSpacing: '0.06em', borderBottom: '1px solid var(--border-divider)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {weekForecast.map((f, i) => (
                <tr key={i}>
                  <td style={{ padding: '8px 3px', fontWeight: i === 0 ? 600 : 400, color: i === 0 ? 'var(--text-primary)' : 'var(--text-secondary)' }}>{f.day}</td>
                  <td style={{ padding: '8px 3px', fontSize: '1.1rem' }}>{f.weather}</td>
                  <td style={{ padding: '8px 3px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{f.maxMin}</td>
                  <td style={{ padding: '8px 3px', fontFamily: 'var(--font-mono)', color: parseInt(f.rain) > 40 ? '#6C8FC5' : 'var(--text-muted)' }}>{f.rain}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Rainfall Overview */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Rainfall Overview</h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
            <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)' }}>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>24-Hour Total</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>0 <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 400 }}>mm</span></div>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>0% vs yesterday</div>
            </div>
            <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)' }}>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Monthly Total</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>48.6 <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 400 }}>mm</span></div>
              <div style={{ fontSize: '0.55rem', color: '#2F8F72', fontWeight: 600 }}>▲ 12% vs last month</div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={rainfallWeek} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="day" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem' }} />
              <Bar dataKey="thisWeek" fill="#6C8FC5" radius={[3, 3, 0, 0]} name="This Week" />
              <Bar dataKey="lastWeek" fill="rgba(0,0,0,0.06)" radius={[3, 3, 0, 0]} name="Last Week" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row: Wind + Humidity/Pressure + Severe Weather + Pollen */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr 1fr 1fr', gap: 'var(--space-lg)' }}>
        {/* Wind Overview */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Wind Overview</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            {/* Wind compass */}
            <div style={{ position: 'relative', width: 100, height: 100 }}>
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border-default)" strokeWidth="1" />
                <circle cx="50" cy="50" r="30" fill="none" stroke="var(--border-divider)" strokeWidth="0.5" />
                {windDirections.map((d, i) => {
                  const angle = (i * 45 - 90) * (Math.PI / 180)
                  const x = 50 + 42 * Math.cos(angle)
                  const y = 50 + 42 * Math.sin(angle)
                  return <text key={d} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="7" fill={d === 'NE' ? '#6C8FC5' : 'var(--text-muted)'} fontFamily="var(--font-mono)" fontWeight={d === 'NE' ? 700 : 400}>{d}</text>
                })}
                {/* Wind arrow pointing NE */}
                <line x1="50" y1="50" x2="75" y2="25" stroke="#6C8FC5" strokeWidth="2" strokeLinecap="round" />
                <circle cx="50" cy="50" r="3" fill="#6C8FC5" />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>12</span>
                <span style={{ fontSize: '0.45rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>km/h</span>
                <span style={{ fontSize: '0.5rem', fontWeight: 600, color: '#6C8FC5' }}>NE</span>
              </div>
            </div>
            <div style={{ fontSize: '0.68rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Avg Wind Speed</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>12 km/h</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Max Wind Gust</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>28 km/h</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Wind Direction</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>NE (45°)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Calm Conditions</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>2%</span>
              </div>
            </div>
          </div>
        </div>

        {/* Humidity & Pressure */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Humidity & Pressure Trend</h3>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={humidityPressure} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 7, fill: '#8F9295' }} interval={4} axisLine={false} tickLine={false} />
              <YAxis yAxisId="hum" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit="%" domain={[20, 100]} />
              <YAxis yAxisId="pres" orientation="right" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit=" hPa" domain={[995, 1020]} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem' }} />
              <Area yAxisId="hum" type="monotone" dataKey="humidity" stroke="#6C8FC5" strokeWidth={1.5} fill="rgba(108,143,197,0.1)" name="Humidity (%)" />
              <Line yAxisId="pres" type="monotone" dataKey="pressure" stroke="#F4A62A" strokeWidth={1.5} dot={false} name="Pressure (hPa)" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Severe Weather Risk */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Severe Weather Risk</h3>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
            <div style={{ position: 'relative', width: 110, height: 110 }}>
              <svg width="110" height="110" viewBox="0 0 110 110">
                <circle cx="55" cy="55" r="48" fill="none" stroke="rgba(0,0,0,0.04)" strokeWidth="6" />
                <circle cx="55" cy="55" r="48" fill="none" stroke="#F4A62A" strokeWidth="6"
                  strokeDasharray={`${0.45 * 301.6} 301.6`}
                  strokeLinecap="round" transform="rotate(-90 55 55)" />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <CloudLightning size={22} color="#F4A62A" />
                <span style={{ fontSize: '0.9rem', fontWeight: 700, color: '#F4A62A', marginTop: '2px' }}>Moderate</span>
                <span style={{ fontSize: '0.5rem', color: 'var(--text-muted)' }}>Risk Level</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.65rem' }}>
            <div><span style={{ color: 'var(--text-muted)' }}>Primary Risk</span><div style={{ fontWeight: 600 }}>Thunderstorms</div></div>
            <div><span style={{ color: 'var(--text-muted)' }}>Probability</span><div style={{ fontWeight: 600 }}>45%</div></div>
            <div><span style={{ color: 'var(--text-muted)' }}>Time Window</span><div style={{ fontWeight: 600 }}>2 PM - 10 PM</div></div>
          </div>
        </div>

        {/* Pollen & Air Comfort */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Pollen & Air Comfort</h3>
          <div style={{ textAlign: 'center', marginBottom: '16px' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Pollen Count</div>
            <div style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: '#2F8F72' }}>32</div>
            <div style={{ fontSize: '0.65rem', color: '#2F8F72', fontWeight: 600 }}>Low</div>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>(Grasses)</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.68rem' }}>
            {[
              { label: 'Air Comfort', value: 'Good', color: '#2F8F72' },
              { label: 'Outdoor Activity', value: 'Good', color: '#2F8F72' },
              { label: 'Asthma Risk', value: 'Low', color: '#2F8F72' },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                <span style={{ fontWeight: 600, color: item.color }}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Insight Bar */}
      <div style={{ marginTop: 'var(--space-lg)', background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '16px 24px', boxShadow: 'var(--shadow-card)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <CloudSun size={16} color="#6C8FC5" />
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Weather Insight</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '12px' }}>Clear conditions expected today with a chance of thunderstorms this evening. Carry an umbrella if traveling after 2 PM.</span>
          </div>
        </div>
        <button style={{ padding: '8px 18px', borderRadius: 'var(--radius-md)', border: '1px solid #6C8FC5', background: 'transparent', color: '#6C8FC5', fontSize: '0.72rem', fontWeight: 600, fontFamily: 'var(--font-mono)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap' }}>
          View Detailed Weather Report <ArrowRight size={12} />
        </button>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { CloudSun, Thermometer, Droplets, Wind, Gauge, CloudRain, Sun, Cloud, CloudLightning, RefreshCw, AlertTriangle, Loader2 } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import ProblemSolverSection from '../components/ProblemSolverSection'
import { weatherApi, modelsApi } from '../services/api'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar } from 'recharts'

const iconMap = {
  Sun,
  Cloud,
  CloudRain,
  CloudLightning
}

export default function Weather() {
  const [weatherState, setWeatherState] = useState(null)
  const [weatherData, setWeatherData] = useState(null)
  const [forecast, setForecast] = useState([])
  const [hourlyTemp, setHourlyTemp] = useState([])
  const [precipData, setPrecipData] = useState([])
  const [correlations, setCorrelations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadWeatherData = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await weatherApi.getCurrent()
      if (data) {
        setWeatherData(data)
        if (data.forecast_7d) {
          setForecast(data.forecast_7d)
        }
        if (data.hourly_temp) {
          setHourlyTemp(data.hourly_temp)
        }
        if (data.weekly_precipitation) {
          setPrecipData(data.weekly_precipitation)
        }
        if (data.correlations) {
          setCorrelations(data.correlations)
        }
      }
    } catch (err) {
      console.warn('Weather API fetch error:', err)
      setError(err.message || 'Failed to connect to Weather Agent backend on port 8000')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadWeatherData()

    async function loadWeatherModel() {
      try {
        const res = await modelsApi.analyzeWeather({ location: 'Hyderabad Central' })
        setWeatherState(res)
      } catch (err) {
        console.warn('Weather model sync:', err)
      }
    }
    loadWeatherModel()
  }, [])

  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><CloudSun size={28} /> Weather Intelligence</h1>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {loading && <span className="badge badge-info"><Loader2 size={12} className="animate-spin" /> Fetching Telemetry...</span>}
          <StatusBadge status={error ? 'WARNING' : 'ONLINE'} />
          {weatherData?.timestamp && (
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
              Live Agent: {weatherData.timestamp.slice(11, 19)} UTC
            </span>
          )}
        </div>
      </div>

      {/* Offline / Connection Error Screen */}
      {error && !weatherData && (
        <GlassCard style={{ padding: '32px', textAlign: 'center', borderColor: 'var(--accent-rose)', margin: 'var(--space-xl) 0' }}>
          <AlertTriangle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ color: 'var(--accent-rose)', marginBottom: '8px' }}>Weather Agent Backend Offline</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '600px', margin: '0 auto 16px' }}>
            Cannot connect to backend endpoint <code>/api/v1/weather/current</code> ({error}).<br />
            Please make sure the backend supervisor is running on <code>http://127.0.0.1:8000</code>:
          </p>
          <pre style={{ background: 'var(--bg-card)', padding: '10px 18px', borderRadius: 'var(--radius-sm)', display: 'inline-block', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            ..\.venv\Scripts\python -m uvicorn backend.supervisor.main:app --host 127.0.0.1 --port 8000 --reload
          </pre>
          <div style={{ marginTop: '18px' }}>
            <button onClick={loadWeatherData} className="btn-primary" style={{ padding: '8px 18px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <RefreshCw size={14} /> Retry Connection
            </button>
          </div>
        </GlassCard>
      )}

      {/* Loading Skeleton */}
      {loading && !weatherData && !error && (
        <GlassCard style={{ padding: '48px', textAlign: 'center', margin: 'var(--space-xl) 0' }}>
          <Loader2 size={36} className="animate-spin" color="var(--accent-cyan)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Connecting to Weather Agent API & loading meteorological telemetry...</p>
        </GlassCard>
      )}

      {/* Live Content */}
      {weatherData && (
        <>
          {error && (
            <div className="glass-card" style={{ padding: '12px 16px', marginBottom: 'var(--space-md)', borderColor: 'var(--accent-rose)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)', fontSize: '0.8rem' }}>
                <AlertTriangle size={16} />
                <span>Weather Agent Notice: {error}</span>
              </div>
              <button onClick={loadWeatherData} style={{ background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: '4px 8px', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <RefreshCw size={12} /> Retry
              </button>
            </div>
          )}

          {/* Current Conditions */}
          <div className="grid-kpi">
            <MetricCard icon={Thermometer} label="Temperature" value={weatherData.temperature_c} suffix="°C" decimals={1} color="amber" trend="up" trendValue="+1.5°" subtitle={`Feels Like: ${weatherData.feels_like_c}°C`} />
            <MetricCard icon={Droplets} label="Humidity" value={weatherData.humidity_pct} suffix="%" color="blue" trend="down" trendValue="-4%" subtitle={`Dew Point: ${weatherData.dew_point_c}°C`} />
            <MetricCard icon={Wind} label="Wind Speed" value={weatherData.wind_speed_kmh} suffix=" km/h" decimals={1} color="cyan" subtitle={`Direction: ${weatherData.wind_direction}`} />
            <MetricCard icon={Gauge} label="Pressure" value={weatherData.pressure_hpa} suffix=" hPa" color="violet" trend="down" trendValue="-2 hPa" />
          </div>

          {/* 7-Day Forecast Strip */}
          {forecast.length > 0 && (
            <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
              <div className="section-title">7-Day Forecast (Backend Agent)</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '8px' }}>
                {forecast.map((f, i) => {
                  const Icon = typeof f.icon === 'function' ? f.icon : (iconMap[f.icon] || Sun)
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
          )}

          {/* Charts */}
          <div className="grid-dashboard" style={{ marginTop: 'var(--space-xl)' }}>
            {hourlyTemp.length > 0 && (
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
            )}

            {precipData.length > 0 && (
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
            )}
          </div>

          {/* Weather-City Correlations */}
          {correlations.length > 0 && (
            <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
              <div className="section-title">Cross-Domain Weather Correlations</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
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
          )}

          {/* AI Multi-Suggestion Problem Solver Module */}
          <ProblemSolverSection initialProblemId="PROB_04" />
        </>
      )}
    </div>
  )
}

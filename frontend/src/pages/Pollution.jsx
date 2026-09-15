import { useState, useEffect } from 'react'
import { Wind, Droplets, Flame, CloudRain, Factory, Thermometer, MapPin, RefreshCw, AlertTriangle, Loader2 } from 'lucide-react'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import AQIGauge from '../components/AQIGauge'
import AnimatedCounter from '../components/AnimatedCounter'
import ProblemSolverSection from '../components/ProblemSolverSection'
import { pollutionApi, modelsApi } from '../services/api'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const pollutantIconMap = {
  'PM2.5': Droplets,
  'PM10': Wind,
  'CO': Flame,
  'NO₂': Factory,
  'SO₂': CloudRain,
  'O₃': Thermometer
}

export default function Pollution() {
  const [modelState, setModelState] = useState(null)
  const [pollutionData, setPollutionData] = useState(null)
  const [pollutants, setPollutants] = useState([])
  const [aqiTrend, setAqiTrend] = useState([])
  const [stations, setStations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadPollutionData = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await pollutionApi.getCurrent()
      if (data) {
        setPollutionData({
          aqi: data.aqi ?? data.city_avg_aqi ?? 0,
          category: data.category ?? 'MODERATE',
          active_stations: data.active_stations ?? (data.stations ? data.stations.length : 0),
          updated_time: data.timestamp ? `${data.timestamp.slice(11, 19)} UTC` : 'Live Telemetry',
          timestamp: data.timestamp || null,
          source: data.source || 'Pollution Agent'
        })
        if (data.pollutants) {
          setPollutants(data.pollutants)
        }
        if (data.aqi_trend) {
          setAqiTrend(data.aqi_trend)
        }
        if (data.stations) {
          setStations(data.stations)
        }
      }
    } catch (err) {
      console.warn('Pollution API fetch error:', err)
      setError(err.message || 'Failed to connect to Pollution Agent backend on port 8000')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPollutionData()

    async function loadPollutionModel() {
      try {
        const res = await modelsApi.analyzeFlood({ location: 'Nacharam Industrial Sector' })
        setModelState(res)
      } catch (err) {
        console.warn('Pollution model sync:', err)
      }
    }
    loadPollutionModel()
  }, [])

  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><Wind size={28} /> Air Quality Command</h1>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {loading && <span className="badge badge-info"><Loader2 size={12} className="animate-spin" /> Fetching TSPCB Telemetry...</span>}
          <StatusBadge status={error ? 'WARNING' : 'AI'} />
          {pollutionData?.timestamp && (
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
              Live Agent: {pollutionData.timestamp.slice(11, 19)} UTC
            </span>
          )}
          {pollutionData && (
            <span className="badge badge-moderate">{pollutionData.active_stations} TSPCB Stations</span>
          )}
        </div>
      </div>

      {/* Offline / Error Screen when backend is down */}
      {error && !pollutionData && (
        <GlassCard style={{ padding: '32px', textAlign: 'center', borderColor: 'var(--accent-rose)', margin: 'var(--space-xl) 0' }}>
          <AlertTriangle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ color: 'var(--accent-rose)', marginBottom: '8px' }}>Pollution Agent Backend Offline</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '600px', margin: '0 auto 16px' }}>
            Cannot connect to backend endpoint <code>/api/v1/pollution/current</code> ({error}).<br />
            Please make sure the backend supervisor is running on <code>http://127.0.0.1:8000</code>:
          </p>
          <pre style={{ background: 'var(--bg-card)', padding: '10px 18px', borderRadius: 'var(--radius-sm)', display: 'inline-block', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            ..\.venv\Scripts\python -m uvicorn backend.supervisor.main:app --host 127.0.0.1 --port 8000 --reload
          </pre>
          <div style={{ marginTop: '18px' }}>
            <button onClick={loadPollutionData} className="btn-primary" style={{ padding: '8px 18px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <RefreshCw size={14} /> Retry Connection
            </button>
          </div>
        </GlassCard>
      )}

      {/* Loading Skeleton */}
      {loading && !pollutionData && !error && (
        <GlassCard style={{ padding: '48px', textAlign: 'center', margin: 'var(--space-xl) 0' }}>
          <Loader2 size={36} className="animate-spin" color="var(--accent-cyan)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Connecting to Pollution Agent API & loading air quality metrics...</p>
        </GlassCard>
      )}

      {/* Live Content */}
      {pollutionData && (
        <>
          {error && (
            <div className="glass-card" style={{ padding: '12px 16px', marginBottom: 'var(--space-md)', borderColor: 'var(--accent-rose)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)', fontSize: '0.8rem' }}>
                <AlertTriangle size={16} />
                <span>Pollution Agent Notice: {error}</span>
              </div>
              <button onClick={loadPollutionData} style={{ background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: '4px 8px', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <RefreshCw size={12} /> Retry
              </button>
            </div>
          )}

          {/* AQI Gauge + Pollutant Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 'var(--space-xl)' }}>
            <GlassCard style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }} glow="amber">
              <div className="section-title" style={{ alignSelf: 'flex-start' }}>Current AQI</div>
              <AQIGauge value={pollutionData.aqi} size={220} />
              <div style={{ marginTop: '12px', textAlign: 'center' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  Hyderabad Avg · Last Updated {pollutionData.updated_time}
                </div>
              </div>
            </GlassCard>

            {pollutants.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-md)' }}>
                {pollutants.map(p => {
                  const Icon = typeof p.icon === 'function' ? p.icon : (pollutantIconMap[p.name] || Wind)
                  const isOver = p.value > p.limit
                  return (
                    <GlassCard key={p.name}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                        <div style={{
                          width: 36, height: 36, borderRadius: 'var(--radius-sm)',
                          background: `var(--accent-${p.color || 'blue'}-dim)`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          <Icon size={18} color={`var(--accent-${p.color || 'blue'})`} />
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
                          background: isOver ? 'var(--accent-rose)' : `var(--accent-${p.color || 'blue'})`,
                          transition: 'width 1.5s ease',
                        }} />
                      </div>
                    </GlassCard>
                  )
                })}
              </div>
            )}
          </div>

          {/* AQI Timeline */}
          {aqiTrend.length > 0 && (
            <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
              <div className="section-title">24h AQI & PM2.5 Trend (Backend Agent)</div>
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
          )}

          {/* Station Grid */}
          {stations.length > 0 && (
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
          )}

          {/* AI Multi-Suggestion Problem Solver Module */}
          <ProblemSolverSection initialProblemId="PROB_02" />
        </>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import { Car, Gauge, Timer, Radio, AlertTriangle, MapPin, RefreshCw, Loader2 } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import ProblemSolverSection from '../components/ProblemSolverSection'
import { trafficApi, modelsApi } from '../services/api'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell
} from 'recharts'

export default function Traffic() {
  const [modelPrediction, setModelPrediction] = useState(null)
  const [kpis, setKpis] = useState(null)
  const [sensors, setSensors] = useState([])
  const [hourlyData, setHourlyData] = useState([])
  const [corridorData, setCorridorData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadTrafficData = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await trafficApi.getKPIs()
      if (data) {
        setKpis({
          active_vehicles: data.active_vehicles ?? 0,
          average_speed_kmh: data.average_speed_kmh ?? 0,
          average_delay_sec: data.average_delay_sec ?? 0,
          signal_optimizations: data.signal_optimizations ?? 0,
          active_sensors: data.active_sensors ?? (data.sensors?.length || 0),
          timestamp: data.timestamp || null,
          source: data.source || 'Traffic Agent'
        })
        if (data.sensors) {
          setSensors(data.sensors)
        }
        if (data.hourly_data) {
          setHourlyData(data.hourly_data)
        }
        if (data.corridors) {
          setCorridorData(data.corridors)
        }
      }
    } catch (err) {
      console.warn('Traffic API fetch error:', err)
      setError(err.message || 'Failed to connect to Traffic Agent backend on port 8000')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTrafficData()

    async function fetchTrafficModel() {
      try {
        const res = await modelsApi.analyzeTraffic({
          location: 'Gachibowli Flyover',
          scenario: 'live_telemetry'
        })
        setModelPrediction(res)
      } catch (e) {
        console.warn('Traffic model sync:', e)
      }
    }
    fetchTrafficModel()
  }, [])

  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><Car size={28} /> Traffic Intelligence</h1>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {loading && <span className="badge badge-info"><Loader2 size={12} className="animate-spin" /> Fetching Agent Telemetry...</span>}
          <StatusBadge status={error ? 'WARNING' : 'AI'} />
          {kpis?.timestamp && (
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
              Live Agent: {kpis.timestamp.slice(11, 19)} UTC
            </span>
          )}
          {kpis && (
            <span className="badge badge-info">{kpis.active_sensors} Active Sensors</span>
          )}
        </div>
      </div>

      {/* Offline / Error Screen when backend is down */}
      {error && !kpis && (
        <GlassCard style={{ padding: '32px', textAlign: 'center', borderColor: 'var(--accent-rose)', margin: 'var(--space-xl) 0' }}>
          <AlertTriangle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ color: 'var(--accent-rose)', marginBottom: '8px' }}>Traffic Agent Backend Offline</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '600px', margin: '0 auto 16px' }}>
            Cannot connect to backend endpoint <code>/api/v1/traffic/kpis</code> ({error}).<br />
            Please make sure the backend supervisor is running on <code>http://127.0.0.1:8000</code>:
          </p>
          <pre style={{ background: 'var(--bg-card)', padding: '10px 18px', borderRadius: 'var(--radius-sm)', display: 'inline-block', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            ..\.venv\Scripts\python -m uvicorn backend.supervisor.main:app --host 127.0.0.1 --port 8000 --reload
          </pre>
          <div style={{ marginTop: '18px' }}>
            <button onClick={loadTrafficData} className="btn-primary" style={{ padding: '8px 18px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <RefreshCw size={14} /> Retry Connection
            </button>
          </div>
        </GlassCard>
      )}

      {/* Loading Skeleton */}
      {loading && !kpis && !error && (
        <GlassCard style={{ padding: '48px', textAlign: 'center', margin: 'var(--space-xl) 0' }}>
          <Loader2 size={36} className="animate-spin" color="var(--accent-cyan)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Connecting to Traffic Agent API & loading live telemetry...</p>
        </GlassCard>
      )}

      {/* Live Content */}
      {kpis && (
        <>
          {error && (
            <div className="glass-card" style={{ padding: '12px 16px', marginBottom: 'var(--space-md)', borderColor: 'var(--accent-rose)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)', fontSize: '0.8rem' }}>
                <AlertTriangle size={16} />
                <span>Traffic Agent Notice: {error}</span>
              </div>
              <button onClick={loadTrafficData} style={{ background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: '4px 8px', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <RefreshCw size={12} /> Retry
              </button>
            </div>
          )}

          {/* KPI Cards */}
          <div className="grid-kpi">
            <MetricCard icon={Gauge} label="Avg Network Speed" value={kpis.average_speed_kmh} suffix=" km/h" decimals={2} color="cyan" trend="down" trendValue="-15%" />
            <MetricCard icon={Car} label="Total Vehicles" value={kpis.active_vehicles} color="violet" trend="up" trendValue="+12%" />
            <MetricCard icon={Timer} label="Avg Delay" value={kpis.average_delay_sec} suffix="s" decimals={0} color="amber" trend="up" trendValue="+23%" />
            <MetricCard icon={Radio} label="Signal Optimizations" value={kpis.signal_optimizations} color="emerald" subtitle="AI Adaptive Controller" />
          </div>

          {/* Charts Row */}
          <div className="grid-dashboard" style={{ marginTop: 'var(--space-xl)' }}>
            {hourlyData.length > 0 && (
              <GlassCard>
                <div className="section-title">24h Speed & Volume Forecast (Backend Agent)</div>
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
            )}

            {corridorData.length > 0 && (
              <GlassCard>
                <div className="section-title">Corridor Congestion Index</div>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={corridorData} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" horizontal={false} />
                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} width={100} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
                    <Bar dataKey="value" radius={[0, 6, 6, 0]} name="Congestion %">
                      {corridorData.map((entry, i) => <Cell key={i} fill={entry.color || '#f43f5e'} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </GlassCard>
            )}
          </div>

          {/* Sensor Table */}
          {sensors.length > 0 && (
            <GlassCard style={{ marginTop: 'var(--space-xl)', overflow: 'auto' }}>
              <div className="section-title">Live Sensor Data — {sensors.length} Intersections</div>
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
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{s.volume?.toLocaleString()}</td>
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
          )}

          {/* AI Multi-Suggestion Problem Solver Module */}
          <ProblemSolverSection initialProblemId="PROB_01" />
        </>
      )}
    </div>
  )
}

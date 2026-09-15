import { useState, useEffect } from 'react'
import { FlaskConical, Car, Timer, Radio, Leaf, AlertTriangle, Gauge, MapPin, CheckCircle, RefreshCw, Loader2 } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import { simulationApi } from '../services/api'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

export default function Simulation() {
  const [simStatus, setSimStatus] = useState(null)
  const [simResults, setSimResults] = useState(null)
  const [intersectionPerf, setIntersectionPerf] = useState([])
  const [signalTimeline, setSignalTimeline] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadSimulationData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statusRes, resultsRes] = await Promise.all([
        simulationApi.getStatus(),
        simulationApi.getResults()
      ])

      if (statusRes) {
        setSimStatus(statusRes)
      }

      if (resultsRes) {
        if (resultsRes.sim_results) setSimResults(resultsRes.sim_results)
        if (resultsRes.intersection_performance) setIntersectionPerf(resultsRes.intersection_performance)
        if (resultsRes.signal_timeline) setSignalTimeline(resultsRes.signal_timeline)
        if (resultsRes.summary) setSummary(resultsRes.summary)
      }
    } catch (err) {
      console.warn('Simulation API fetch error:', err)
      setError(err.message || 'Failed to connect to Simulation Agent backend on port 8000')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSimulationData()
  }, [])

  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><FlaskConical size={28} /> SUMO Traffic Simulation</h1>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {loading && <span className="badge badge-info"><Loader2 size={12} className="animate-spin" /> Fetching SUMO Telemetry...</span>}
          {simStatus ? (
            <div className="badge badge-smooth">
              <CheckCircle size={12} /> {simStatus.status || 'COMPLETED'}
            </div>
          ) : (
            <StatusBadge status={error ? 'WARNING' : 'AI'} />
          )}
          {simStatus?.timestamp && (
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>
              Live Agent: {simStatus.timestamp.slice(11, 19)} UTC
            </span>
          )}
          {simResults && (
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              Duration: {simResults.duration_seconds}s (1 Hour Peak)
            </span>
          )}
        </div>
      </div>

      {/* Offline / Connection Error Banner */}
      {error && !simResults && (
        <GlassCard style={{ padding: '32px', textAlign: 'center', borderColor: 'var(--accent-rose)', margin: 'var(--space-xl) 0' }}>
          <AlertTriangle size={36} color="var(--accent-rose)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ color: 'var(--accent-rose)', marginBottom: '8px' }}>Simulation Agent Backend Offline</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '600px', margin: '0 auto 16px' }}>
            Cannot connect to backend endpoint <code>/api/v1/simulation/results</code> ({error}).<br />
            Please make sure the backend supervisor is running on <code>http://127.0.0.1:8000</code>:
          </p>
          <pre style={{ background: 'var(--bg-card)', padding: '10px 18px', borderRadius: 'var(--radius-sm)', display: 'inline-block', fontSize: '0.85rem', color: 'var(--accent-cyan)' }}>
            ..\.venv\Scripts\python -m uvicorn backend.supervisor.main:app --host 127.0.0.1 --port 8000 --reload
          </pre>
          <div style={{ marginTop: '18px' }}>
            <button onClick={loadSimulationData} className="btn-primary" style={{ padding: '8px 18px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
              <RefreshCw size={14} /> Retry Connection
            </button>
          </div>
        </GlassCard>
      )}

      {/* Loading Skeleton View */}
      {loading && !simResults && !error && (
        <GlassCard style={{ padding: '48px', textAlign: 'center', margin: 'var(--space-xl) 0' }}>
          <Loader2 size={36} className="animate-spin" color="var(--accent-cyan)" style={{ margin: '0 auto 12px' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Connecting to Simulation Agent API & loading telemetry...</p>
        </GlassCard>
      )}

      {/* Live Simulation Content */}
      {simResults && (
        <>
          {error && (
            <div className="glass-card" style={{ padding: '12px 16px', marginBottom: 'var(--space-md)', borderColor: 'var(--accent-rose)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)', fontSize: '0.8rem' }}>
                <AlertTriangle size={16} />
                <span>Simulation Agent API Notice: {error}</span>
              </div>
              <button onClick={loadSimulationData} style={{ background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: '4px 8px', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <RefreshCw size={12} /> Retry
              </button>
            </div>
          )}

          {/* KPIs */}
          <div className="grid-kpi">
            <MetricCard icon={Car} label="Vehicles Simulated" value={simResults.total_vehicles_simulated} color="cyan" />
            <MetricCard icon={Gauge} label="Avg Network Speed" value={simResults.overall_avg_speed_kmh} suffix=" km/h" decimals={2} color="amber" />
            <MetricCard icon={Timer} label="Avg Delay" value={simResults.overall_avg_delay_seconds} suffix="s" decimals={0} color="rose" />
            <MetricCard icon={Radio} label="AI Signal Adaptations" value={simResults.total_signal_adaptations} color="violet" subtitle="Dynamic Actuated" />
          </div>

          <div className="grid-2" style={{ marginTop: 'var(--space-xl)' }}>
            <MetricCard icon={Leaf} label="CO₂ Emissions" value={simResults.estimated_co2_emissions_kg} suffix=" kg" decimals={1} color="emerald" subtitle="1-Hour Simulation Window" />
            <MetricCard icon={AlertTriangle} label="Max Queue Length" value={simResults.max_queue_length_meters} suffix=" m" decimals={0} color="rose" subtitle="Peak observed at t=1800s" />
          </div>

          {/* Signal Optimization Timeline */}
          {signalTimeline.length > 0 && (
            <GlassCard style={{ marginTop: 'var(--space-xl)' }}>
              <div className="section-title">Signal Optimization Timeline (60 min)</div>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={signalTimeline} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gAdapt" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gSimSpeed" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00f0ff" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="#00f0ff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" />
                  <XAxis dataKey="min" tick={{ fontSize: 10, fill: '#64748b' }} interval={9} axisLine={false} tickLine={false} label={{ value: 'Minutes', position: 'insideBottom', offset: -5, fontSize: 10, fill: '#64748b' }} />
                  <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
                  <Area type="monotone" dataKey="avgSpeed" stroke="#00f0ff" strokeWidth={2} fill="url(#gSimSpeed)" name="Avg Speed (km/h)" />
                  <Area type="monotone" dataKey="adaptations" stroke="#8b5cf6" strokeWidth={2} fill="url(#gAdapt)" name="Signal Adaptations" />
                </AreaChart>
              </ResponsiveContainer>
            </GlassCard>
          )}

          {/* Intersection Performance Table */}
          {intersectionPerf.length > 0 && (
            <GlassCard style={{ marginTop: 'var(--space-xl)', overflow: 'auto' }}>
              <div className="section-title">Intersection Performance Analysis</div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Intersection</th>
                    <th>Avg Queue (veh)</th>
                    <th>Speed (km/h)</th>
                    <th>Green Time (s)</th>
                    <th>Delay (s)</th>
                    <th>AI Status</th>
                  </tr>
                </thead>
                <tbody>
                  {intersectionPerf.map(ip => (
                    <tr key={ip.name}>
                      <td style={{ color: 'var(--text-primary)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <MapPin size={12} color="var(--text-muted)" />{ip.name}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: ip.queue > 40 ? 'var(--accent-rose)' : ip.queue > 25 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                        {ip.queue}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: ip.speed < 15 ? 'var(--accent-rose)' : ip.speed < 25 ? 'var(--accent-amber)' : 'var(--accent-emerald)' }}>
                        {ip.speed}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>{ip.green}s</td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: ip.delay > 90 ? 'var(--accent-rose)' : 'var(--text-secondary)' }}>{ip.delay}s</td>
                      <td><StatusBadge status={ip.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </GlassCard>
          )}

          {/* Bottom Summary bound dynamically to backend */}
          {summary && (
            <GlassCard style={{ marginTop: 'var(--space-xl)' }} glow="violet">
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                <FlaskConical size={20} color="var(--accent-violet)" />
                <span style={{ fontWeight: 600, fontSize: '1rem' }}>Simulation Executive Summary (Backend Agent)</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                {summary.top_bottlenecks && (
                  <div>
                    <strong style={{ color: 'var(--text-primary)' }}>Top Bottlenecks:</strong>
                    <ul style={{ marginTop: '4px', paddingLeft: '16px', lineHeight: 1.8 }}>
                      {summary.top_bottlenecks.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {summary.ai_interventions && (
                  <div>
                    <strong style={{ color: 'var(--text-primary)' }}>AI Interventions:</strong>
                    <ul style={{ marginTop: '4px', paddingLeft: '16px', lineHeight: 1.8 }}>
                      {summary.ai_interventions.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {summary.key_findings && (
                  <div>
                    <strong style={{ color: 'var(--text-primary)' }}>Key Findings:</strong>
                    <ul style={{ marginTop: '4px', paddingLeft: '16px', lineHeight: 1.8 }}>
                      {summary.key_findings.map((item, idx) => (
                        <li key={idx}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </GlassCard>
          )}
        </>
      )}
    </div>
  )
}

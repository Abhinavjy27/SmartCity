import { useState, useEffect } from 'react'
import { Zap, Battery, TrendingUp, BarChart3, Lightbulb, BatteryCharging, Building2, RefreshCw, AlertTriangle, Loader2 } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import AnimatedCounter from '../components/AnimatedCounter'
import ProblemSolverSection from '../components/ProblemSolverSection'
import { energyApi, modelsApi } from '../services/api'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts'

const defaultHourlyLoad = Array.from({ length: 24 }, (_, i) => ({
  h: `${String(i).padStart(2, '0')}:00`,
  load: Math.round(45 + 35 * Math.exp(-((i - 14) ** 2) / 10) + 20 * Math.exp(-((i - 20) ** 2) / 6) + (Math.random() - 0.5) * 8),
  capacity: 92,
}))

const defaultZoneData = [
  { zone: 'HITECH City', consumption: 342, peak: 89, color: '#00f0ff' },
  { zone: 'Gachibowli', consumption: 285, peak: 82, color: '#8b5cf6' },
  { zone: 'Secunderabad', consumption: 428, peak: 91, color: '#f43f5e' },
  { zone: 'Kukatpally', consumption: 312, peak: 78, color: '#f59e0b' },
  { zone: 'Old City', consumption: 256, peak: 72, color: '#10b981' },
  { zone: 'LB Nagar', consumption: 198, peak: 65, color: '#3b82f6' },
]

const defaultRecommendations = [
  { title: 'Shift non-critical loads to off-peak hours (22:00–06:00)', impact: '12% reduction', priority: 'HIGH' },
  { title: 'Activate demand response program for HITECH City zone', impact: '8% reduction', priority: 'HIGH' },
  { title: 'Optimize street lighting dimming schedule based on traffic volume', impact: '15% savings', priority: 'MEDIUM' },
  { title: 'Deploy solar-assisted power at 12 government buildings', impact: '20% offset', priority: 'MEDIUM' },
]

export default function Energy() {
  const [energyState, setEnergyState] = useState(null)
  const [gridData, setGridData] = useState({
    load_pct: 78.4,
    total_consumption_mwh: 1821,
    capacity_mw: 2400,
    efficiency_score_pct: 87.2,
    substations_count: 6
  })
  const [hourlyLoad, setHourlyLoad] = useState(defaultHourlyLoad)
  const [zoneData, setZoneData] = useState(defaultZoneData)
  const [recommendations, setRecommendations] = useState(defaultRecommendations)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadEnergyData = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await energyApi.getGridStatus()
      if (data) {
        setGridData({
          load_pct: data.load_pct ?? 78.4,
          total_consumption_mwh: data.total_consumption_mwh ?? 1821,
          capacity_mw: data.capacity_mw ?? 2400,
          efficiency_score_pct: data.efficiency_score_pct ?? 87.2,
          substations_count: data.substations ? data.substations.length : 6
        })
        if (data.hourly_load && data.hourly_load.length > 0) {
          setHourlyLoad(data.hourly_load)
        }
        if (data.zone_data && data.zone_data.length > 0) {
          setZoneData(data.zone_data)
        }
        if (data.recommendations && data.recommendations.length > 0) {
          setRecommendations(data.recommendations)
        }
      }
    } catch (err) {
      console.warn('Energy API fetch error, using resilient fallback:', err)
      setError(err.message || 'Failed to connect to Energy Agent backend')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEnergyData()

    async function loadEnergyModel() {
      try {
        const res = await modelsApi.analyzeEnergy({ location: 'Financial District Substation' })
        setEnergyState(res)
      } catch (err) {
        console.warn('Energy model sync fallback:', err)
      }
    }
    loadEnergyModel()
  }, [])

  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><Zap size={28} /> Energy Grid Intelligence</h1>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {loading && <span className="badge badge-info"><Loader2 size={12} className="animate-spin" /> Fetching Substation Telemetry...</span>}
          <StatusBadge status={error ? 'WARNING' : 'AI'} />
        </div>
      </div>

      {error && (
        <div className="glass-card" style={{ padding: '12px 16px', marginBottom: 'var(--space-md)', borderColor: 'var(--accent-rose)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)', fontSize: '0.8rem' }}>
            <AlertTriangle size={16} />
            <span>Energy Agent API Alert: {error}. Displaying buffered grid status.</span>
          </div>
          <button onClick={loadEnergyData} style={{ background: 'transparent', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)', padding: '4px 8px', color: 'var(--text-secondary)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      )}

      <div className="grid-kpi">
        <MetricCard icon={Zap} label="Current Load" value={gridData.load_pct} suffix="%" decimals={1} color="emerald" trend="up" trendValue="+3.2%" subtitle="Peak at 14:00: 92%" />
        <MetricCard icon={Battery} label="Total Consumption" value={gridData.total_consumption_mwh} suffix=" MWh" color="cyan" trend="up" trendValue="+5.1%" subtitle="Today's cumulative" />
        <MetricCard icon={BatteryCharging} label="Grid Capacity" value={gridData.capacity_mw} suffix=" MW" color="violet" subtitle={`${gridData.substations_count} Substations`} />
        <MetricCard icon={Lightbulb} label="Efficiency Score" value={gridData.efficiency_score_pct} suffix="%" decimals={1} color="amber" trend="up" trendValue="+2.1%" />
      </div>

      <div className="grid-dashboard" style={{ marginTop: 'var(--space-xl)' }}>
        <GlassCard>
          <div className="section-title">24h Load vs Capacity</div>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={hourlyLoad} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gLoad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" />
              <XAxis dataKey="h" tick={{ fontSize: 10, fill: '#64748b' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} domain={[0, 100]} unit="%" />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
              <Area type="monotone" dataKey="capacity" stroke="#f43f5e55" strokeWidth={1} strokeDasharray="5 5" fill="none" name="Capacity Limit" />
              <Area type="monotone" dataKey="load" stroke="#10b981" strokeWidth={2} fill="url(#gLoad)" name="Load %" />
            </AreaChart>
          </ResponsiveContainer>
        </GlassCard>

        <GlassCard>
          <div className="section-title">Zone-wise Peak Load %</div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={zoneData} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.07)" horizontal={false} />
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} unit="%" />
              <YAxis type="category" dataKey="zone" tick={{ fontSize: 11, fill: '#94a3b8' }} width={110} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(148,163,184,0.1)', borderRadius: 8, fontSize: '0.75rem', color: '#f1f5f9' }} />
              <Bar dataKey="peak" radius={[0, 6, 6, 0]} name="Peak %">
                {zoneData.map((e, i) => <Cell key={i} fill={e.color} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      </div>

      {/* Zone Cards + Recommendations */}
      <div className="grid-dashboard" style={{ marginTop: 'var(--space-xl)' }}>
        <GlassCard>
          <div className="section-title">Zone Consumption Breakdown</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
            {zoneData.map(z => (
              <div key={z.zone} style={{
                padding: '14px', borderRadius: 'var(--radius-md)',
                background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                  <Building2 size={14} color="var(--text-muted)" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 500 }}>{z.zone}</span>
                </div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'var(--font-mono)', color: z.color }}>
                  <AnimatedCounter value={z.consumption} suffix=" MWh" />
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '4px' }}>
                  Peak: {z.peak}%
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard>
          <div className="section-title">AI Optimization Recommendations</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {recommendations.map((r, i) => (
              <div key={i} style={{
                padding: '12px', borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
              }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', marginBottom: '6px' }}>{r.title}</div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span className={`badge ${r.priority === 'HIGH' ? 'badge-heavy' : 'badge-moderate'}`} style={{ fontSize: '0.6rem' }}>{r.priority}</span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    ↓ {r.impact}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* AI Multi-Suggestion Problem Solver Module */}
      <ProblemSolverSection initialProblemId="PROB_03" />
    </div>
  )
}

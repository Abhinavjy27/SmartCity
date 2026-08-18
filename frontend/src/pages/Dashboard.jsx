import {
  Car, Wind, Zap, Activity, Cpu, CloudSun,
  Shield, MapPin, Sliders, Server, Info
} from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import SparklineChart from '../components/SparklineChart'
import AnimatedCounter from '../components/AnimatedCounter'
import ProblemSolverSection from '../components/ProblemSolverSection'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

const trafficTrend = Array.from({ length: 24 }, (_, i) => ({
  h: `${i}:00`,
  speed: 55 - 30 * Math.exp(-((i - 9) ** 2) / 4) - 25 * Math.exp(-((i - 18) ** 2) / 5) + Math.random() * 4,
  volume: 800 + 2600 * Math.exp(-((i - 9) ** 2) / 4) + 2000 * Math.exp(-((i - 18) ** 2) / 5) + Math.random() * 150,
}))

const agents = [
  { name: 'Traffic Agent', icon: Car, status: 'ONLINE', color: 'cyan', load: 78 },
  { name: 'Pollution Agent', icon: Wind, status: 'ONLINE', color: 'amber', load: 65 },
  { name: 'Energy Agent', icon: Zap, status: 'ONLINE', color: 'emerald', load: 52 },
  { name: 'Weather Agent', icon: CloudSun, status: 'ONLINE', color: 'blue', load: 41 },
  { name: 'Supervisor AI', icon: Cpu, status: 'AI', color: 'violet', load: 92 },
  { name: 'Security Verification', icon: Shield, status: 'ONLINE', color: 'emerald', load: 18 },
]

const speedSpark = Array.from({ length: 20 }, () => ({ v: 22 + Math.random() * 30 }))
const aqiSpark = Array.from({ length: 20 }, () => ({ v: 90 + Math.random() * 50 }))
const energySpark = Array.from({ length: 20 }, () => ({ v: 45 + Math.random() * 35 }))

export default function Dashboard() {
  return (
    <div className="stagger-children">
      {/* City Overview Hero */}
      <div className="glass-card" style={{
        padding: '24px',
        marginBottom: 'var(--space-xl)',
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-default)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <Activity size={14} color="var(--accent-cyan)" />
          <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-cyan)', fontWeight: 600, letterSpacing: '0.1em' }}>
            URBAN OPERATIONS OVERVIEW
          </span>
        </div>
        <h1 style={{ fontSize: '1.6rem', marginBottom: '6px', fontWeight: 600 }}>
          Hyderabad Command Center
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', maxWidth: '800px', lineHeight: 1.4 }}>
          Smart Urban Planning & AI Decision Support Platform. Real-time telemetry, spatial GIS mapping, and predictive optimization models.
        </p>
      </div>

      {/* KPI Overview Row */}
      <div className="grid-kpi" style={{ marginBottom: 'var(--space-xl)' }}>
        <MetricCard icon={Car} label="Active Vehicles" value={2342} color="cyan" trend="up" trendValue="+12%" subtitle="15 Sensor Corridors" />
        <MetricCard icon={Wind} label="Current AQI" value={136} color="amber" trend="down" trendValue="-8%" subtitle="13 TSPCB Stations" />
        <MetricCard icon={Zap} label="Grid Load" value={78.4} suffix="%" decimals={1} color="emerald" trend="up" trendValue="+3.2%" subtitle="Peak: 92% today" />
        <MetricCard icon={Shield} label="AI Safety Confidence" value={98.6} suffix="%" decimals={1} color="violet" subtitle="Verification Agent Active" />
      </div>

      {/* 2-Column Command Layout */}
      <div className="grid-dashboard">

        {/* Main Column - GIS Digital Twin Map */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          <GlassCard style={{ padding: '0px', overflow: 'hidden', minHeight: '400px', display: 'flex', flexDirection: 'column' }}>
            {/* Map Header */}
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-primary)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sliders size={16} color="var(--accent-cyan)" />
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>Interactive GIS Digital Twin</span>
              </div>
              <span className="badge badge-info" style={{ fontSize: '0.65rem' }}>MapLibre Engine Active</span>
            </div>

            {/* Simulated Map Canvas */}
            <div style={{ flex: 1, position: 'relative', background: '#0a0d14', minHeight: '340px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="100%" height="100%" viewBox="0 0 400 240" style={{ position: 'absolute', inset: 0 }}>
                {/* Simulated Street Grid */}
                <line x1="0" y1="60" x2="400" y2="60" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                <line x1="0" y1="120" x2="400" y2="120" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                <line x1="0" y1="180" x2="400" y2="180" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                <line x1="100" y1="0" x2="100" y2="240" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                <line x1="200" y1="0" x2="200" y2="240" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />
                <line x1="300" y1="0" x2="300" y2="240" stroke="rgba(255,255,255,0.02)" strokeWidth="1" />

                {/* Major Corridors */}
                <path d="M 50 120 L 350 120" stroke="rgba(255,255,255,0.06)" strokeWidth="4" strokeLinecap="round" />
                <path d="M 200 40 L 200 200" stroke="rgba(255,255,255,0.06)" strokeWidth="4" strokeLinecap="round" />
                <path d="M 80 50 L 320 190" stroke="rgba(255,255,255,0.06)" strokeWidth="3" strokeLinecap="round" />

                {/* Live Traffic Highlight layers */}
                <path d="M 120 120 L 200 120" stroke="var(--accent-amber)" strokeWidth="4" strokeLinecap="round" />
                <path d="M 200 120 L 280 120" stroke="var(--accent-emerald)" strokeWidth="4" strokeLinecap="round" />
                <path d="M 200 40 L 200 120" stroke="var(--accent-rose)" strokeWidth="4" strokeLinecap="round" />

                {/* Spatial Nodes */}
                <circle cx="120" cy="120" r="4" fill="var(--accent-amber)" />
                <circle cx="200" cy="120" r="6" fill="var(--accent-cyan)" />
                <circle cx="280" cy="120" r="4" fill="var(--accent-emerald)" />
                <circle cx="200" cy="40" r="4" fill="var(--accent-rose)" />

                {/* Labels */}
                <text x="210" y="115" fill="var(--text-primary)" fontSize="7" fontWeight="bold">J_PUNJAGUTTA</text>
                <text x="65" y="115" fill="var(--text-muted)" fontSize="6">Gachibowli Corridor</text>
                <text x="290" y="115" fill="var(--text-muted)" fontSize="6">Secunderabad Line</text>
                <text x="210" y="45" fill="var(--accent-rose)" fontSize="6" fontWeight="bold">J_HITECH_CITY (CONGESTED)</text>
              </svg>

              {/* Floating Layer Controls (Functional Glass Overlay) */}
              <div style={{
                position: 'absolute', bottom: '16px', left: '16px',
                display: 'flex', gap: '8px'
              }}>
                <div style={{ padding: '6px 12px', fontSize: '0.7rem', color: 'var(--text-secondary)', background: 'var(--bg-glass)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)' }}>
                  Active Layers: Traffic Speed, AQI Sensors, Energy Substations
                </div>
              </div>
            </div>
          </GlassCard>

          {/* 24h Traffic Speed & Volume Chart */}
          <GlassCard>
            <div className="section-title">24h Traffic Volumetric Forecast</div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={trafficTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="gSpeed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.05)" />
                <XAxis dataKey="h" tick={{ fontSize: 9, fill: '#64748b' }} interval={3} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 9, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem', color: 'var(--text-primary)' }} />
                <Area type="monotone" dataKey="speed" stroke="var(--accent-cyan)" strokeWidth={1.5} fill="url(#gSpeed)" name="Speed (km/h)" />
              </AreaChart>
            </ResponsiveContainer>
          </GlassCard>
        </div>

        {/* Sidebar Column - Real-time metrics & AI Agents */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          {/* Sparkline Indicators */}
          <GlassCard>
            <div className="section-title">Telemetry Sparklines</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Network Avg Speed</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    <AnimatedCounter value={23.7} decimals={1} suffix=" km/h" />
                  </span>
                </div>
                <SparklineChart data={speedSpark} color="var(--accent-cyan)" height={30} />
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Average Urban AQI</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--accent-amber)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    <AnimatedCounter value={136} suffix=" AQI" />
                  </span>
                </div>
                <SparklineChart data={aqiSpark} color="var(--accent-amber)" height={30} />
              </div>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Substation Load</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                    <AnimatedCounter value={78.4} decimals={1} suffix="%" />
                  </span>
                </div>
                <SparklineChart data={energySpark} color="var(--accent-emerald)" height={30} />
              </div>
            </div>
          </GlassCard>

          {/* AI Domain Agents status */}
          <GlassCard>
            <div className="section-title">AI Domain Agents</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {agents.map(a => {
                const Icon = a.icon
                return (
                  <div key={a.name} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Icon size={16} color={`var(--accent-${a.color})`} />
                      <span style={{ fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-primary)' }}>{a.name}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <StatusBadge status={a.status} />
                      <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{a.load}% load</span>
                    </div>
                  </div>
                )
              })}
            </div>
          </GlassCard>
        </div>

      </div>

      {/* AI Multi-Suggestion Problem Solver Module */}
      <ProblemSolverSection />
    </div>
  )
}

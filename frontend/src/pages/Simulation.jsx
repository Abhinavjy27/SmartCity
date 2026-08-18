import { FlaskConical, Car, Timer, Radio, Leaf, AlertTriangle, Gauge, MapPin, Play, CheckCircle } from 'lucide-react'
import MetricCard from '../components/MetricCard'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import AnimatedCounter from '../components/AnimatedCounter'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

const simResults = {
  total_vehicles_simulated: 2342,
  overall_avg_speed_kmh: 23.67,
  overall_avg_delay_seconds: 87.64,
  total_signal_adaptations: 106,
  estimated_co2_emissions_kg: 284.7,
  max_queue_length_meters: 3051.82,
  duration_seconds: 3600,
}

const intersectionPerf = [
  { name: 'Gachibowli Flyover', queue: 48.2, speed: 18.5, green: 50, status: 'OPTIMIZED', delay: 95 },
  { name: 'HITECH City Mindspace', queue: 54.7, speed: 15.2, green: 55, status: 'OPTIMIZED', delay: 112 },
  { name: 'Jubilee Hills', queue: 32.1, speed: 22.1, green: 40, status: 'OPTIMIZED', delay: 72 },
  { name: 'Punjagutta Junction', queue: 42.1, speed: 12.8, green: 60, status: 'OPTIMIZED', delay: 98 },
  { name: 'Begumpet Flyover', queue: 28.4, speed: 28.3, green: 35, status: 'SMOOTH', delay: 55 },
  { name: 'Secunderabad Paradise', queue: 22.7, speed: 31.2, green: 35, status: 'SMOOTH', delay: 42 },
  { name: 'Ameerpet Metro', queue: 45.3, speed: 13.5, green: 55, status: 'OPTIMIZED', delay: 104 },
  { name: 'Kukatpally Y Junction', queue: 35.6, speed: 24.7, green: 40, status: 'OPTIMIZED', delay: 78 },
  { name: 'Mehdipatnam Bus Station', queue: 38.9, speed: 16.3, green: 45, status: 'OPTIMIZED', delay: 88 },
  { name: 'LB Nagar Ring Road', queue: 18.2, speed: 42.5, green: 40, status: 'SMOOTH', delay: 32 },
]

const signalTimeline = Array.from({ length: 60 }, (_, i) => ({
  min: i,
  adaptations: Math.round(Math.max(0, 3 * Math.exp(-((i - 30) ** 2) / 200) + (Math.random() - 0.3) * 2)),
  avgSpeed: Math.max(8, 55 - 40 * Math.exp(-((i - 30) ** 2) / 250) + (Math.random() - 0.5) * 5),
}))

export default function Simulation() {
  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><FlaskConical size={28} /> SUMO Traffic Simulation</h1>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div className="badge badge-smooth">
            <CheckCircle size={12} /> Completed
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Duration: {simResults.duration_seconds}s (1 Hour Peak)
          </span>
        </div>
      </div>

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

      {/* Intersection Performance Table */}
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

      {/* Bottom Summary */}
      <GlassCard style={{ marginTop: 'var(--space-xl)' }} glow="violet">
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
          <FlaskConical size={20} color="var(--accent-violet)" />
          <span style={{ fontWeight: 600, fontSize: '1rem' }}>Simulation Executive Summary</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
          <div>
            <strong style={{ color: 'var(--text-primary)' }}>Top Bottlenecks:</strong>
            <ul style={{ marginTop: '4px', paddingLeft: '16px', lineHeight: 1.8 }}>
              <li>HITECH City Mindspace (Queue: 54.7 veh)</li>
              <li>Gachibowli Flyover (Queue: 48.2 veh)</li>
              <li>Ameerpet Metro (Queue: 45.3 veh)</li>
            </ul>
          </div>
          <div>
            <strong style={{ color: 'var(--text-primary)' }}>AI Interventions:</strong>
            <ul style={{ marginTop: '4px', paddingLeft: '16px', lineHeight: 1.8 }}>
              <li>106 adaptive green-time adjustments</li>
              <li>Dynamic actuated signal control</li>
              <li>Queue-responsive optimization</li>
            </ul>
          </div>
          <div>
            <strong style={{ color: 'var(--text-primary)' }}>Key Findings:</strong>
            <ul style={{ marginTop: '4px', paddingLeft: '16px', lineHeight: 1.8 }}>
              <li>IT Corridor needs capacity expansion</li>
              <li>AI reduced peak delay by ~18%</li>
              <li>CO₂ can be reduced 12% with off-peak shift</li>
            </ul>
          </div>
        </div>
      </GlassCard>
    </div>
  )
}

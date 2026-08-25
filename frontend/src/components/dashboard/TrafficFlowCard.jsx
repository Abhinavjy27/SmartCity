import { Car, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AnimatedCounter from '../AnimatedCounter'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'

const trafficData = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  vehicles: Math.round(800 + 2600 * Math.exp(-((i - 9) ** 2) / 4) + 2000 * Math.exp(-((i - 18) ** 2) / 5) + (Math.random() - 0.5) * 200),
}))

const donutData = [
  { label: 'Free Flow', count: 1245, pct: 53, color: '#2F8F72' },
  { label: 'Moderate', count: 742, pct: 32, color: '#F4A62A' },
  { label: 'Congested', count: 355, pct: 15, color: '#E5483F' },
]

function DonutChart() {
  const total = donutData.reduce((s, d) => s + d.count, 0)
  const size = 110
  const strokeWidth = 18
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {donutData.map((d) => {
          const dashArray = (d.pct / 100) * circumference
          const dashOffset = -offset
          offset += dashArray
          return (
            <circle
              key={d.label}
              cx={size / 2} cy={size / 2} r={radius}
              fill="none" stroke={d.color} strokeWidth={strokeWidth}
              strokeDasharray={`${dashArray} ${circumference - dashArray}`}
              strokeDashoffset={dashOffset}
              transform={`rotate(-90 ${size / 2} ${size / 2})`}
              style={{ transition: 'stroke-dasharray 0.8s ease' }}
            />
          )
        })}
      </svg>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Total</span>
      </div>
    </div>
  )
}

export default function TrafficFlowCard() {
  const navigate = useNavigate()

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border-card)',
      borderRadius: 'var(--radius-lg)',
      padding: '24px',
      boxShadow: 'var(--shadow-card)',
    }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'var(--accent-traffic-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Car size={16} color="var(--accent-traffic)" strokeWidth={1.8} />
          </div>
          <div>
            <h3 style={{
              fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.06em',
              fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
            }}>TRAFFIC FLOW OVERVIEW</h3>
          </div>
        </div>
        <button
          onClick={() => navigate('/traffic')}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '4px',
            fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)', letterSpacing: '0.04em',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
          onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}
        >
          VIEW DETAILS <ArrowRight size={12} />
        </button>
      </div>

      {/* Content grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '180px 160px 1fr', gap: '24px', alignItems: 'center' }}>
        {/* Left - Big number */}
        <div>
          <div style={{
            fontSize: '2.4rem', fontWeight: 700, color: 'var(--text-primary)',
            fontFamily: 'var(--font-heading)', lineHeight: 1.1,
          }}>
            <AnimatedCounter value={2342} />
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>Total Vehicles</div>
        </div>

        {/* Middle - Donut + legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <DonutChart />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {donutData.map(d => (
              <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: d.color }} />
                <div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{d.label}</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {d.count.toLocaleString()} ({d.pct}%)
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right - Line chart */}
        <div style={{ height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={trafficData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="trafficGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#2F8F72" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#2F8F72" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#8F9295' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: '#8F9295' }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                  borderRadius: 8, fontSize: '0.72rem', color: 'var(--text-primary)',
                  boxShadow: 'var(--shadow-elevated)',
                }}
              />
              <Area type="monotone" dataKey="vehicles" stroke="#2F8F72" strokeWidth={1.5} fill="url(#trafficGrad)" name="Vehicles" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

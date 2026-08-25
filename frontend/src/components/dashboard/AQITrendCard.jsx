import { Wind, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AnimatedCounter from '../AnimatedCounter'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine
} from 'recharts'

const aqiData = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  aqi: Math.round(80 + 60 * Math.exp(-((i - 8) ** 2) / 8) + 45 * Math.exp(-((i - 20) ** 2) / 6) + (Math.random() - 0.5) * 15),
}))

export default function AQITrendCard() {
  const navigate = useNavigate()

  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border-card)',
      borderRadius: 'var(--radius-lg)',
      padding: '24px',
      boxShadow: 'var(--shadow-card)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'var(--accent-air-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Wind size={16} color="var(--accent-air)" strokeWidth={1.8} />
          </div>
          <div>
            <h3 style={{
              fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.06em',
              fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
            }}>AQI TREND (24 HOURS)</h3>
          </div>
        </div>
        <button
          onClick={() => navigate('/pollution')}
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

      {/* Content */}
      <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: '24px', alignItems: 'center' }}>
        {/* Left - Big number */}
        <div>
          <div style={{
            fontSize: '2.4rem', fontWeight: 700, color: 'var(--text-primary)',
            fontFamily: 'var(--font-heading)', lineHeight: 1.1,
          }}>
            <AnimatedCounter value={136} />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <span style={{
              padding: '2px 10px', borderRadius: 'var(--radius-full)',
              fontSize: '0.65rem', fontWeight: 600,
              background: 'var(--accent-energy-dim)', color: '#B8860B',
              border: '1px solid rgba(244,166,42,0.2)',
            }}>Moderate</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>US AQI</div>
        </div>

        {/* Right - Area chart */}
        <div style={{ height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={aqiData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="aqiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4C9E9B" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#4C9E9B" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#8F9295' }} interval={3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: '#8F9295' }} axisLine={false} tickLine={false} domain={[0, 300]} />
              <ReferenceLine y={100} stroke="rgba(0,0,0,0.08)" strokeDasharray="4 4" label={{ value: '', position: 'right' }} />
              <ReferenceLine y={200} stroke="rgba(0,0,0,0.08)" strokeDasharray="4 4" />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                  borderRadius: 8, fontSize: '0.72rem', color: 'var(--text-primary)',
                  boxShadow: 'var(--shadow-elevated)',
                }}
              />
              <Area type="monotone" dataKey="aqi" stroke="#4C9E9B" strokeWidth={1.5} fill="url(#aqiGrad)" name="AQI" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

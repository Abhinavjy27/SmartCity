import { useState, useEffect } from 'react'
import { Zap, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AnimatedCounter from '../AnimatedCounter'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine
} from 'recharts'
import { energyApi } from '../../services/api'

export default function EnergyCard({ timeRange = '24 HOURS' }) {
  const navigate = useNavigate()
  const [loadPct, setLoadPct] = useState(78.4)
  const [severity, setSeverity] = useState('Normal')
  const [chartData, setChartData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let isMounted = true

    const loadEnergy = async () => {
      try {
        const res = await energyApi.getGridStatus()
        if (!isMounted) return

        if (res && res.load_pct !== undefined) {
          setLoadPct(parseFloat(res.load_pct.toFixed(1)))
          if (res.severity) setSeverity(res.severity)

          // If backend returns hourly telemetry or substation load curve
          if (res.hourly_curve && res.hourly_curve.length > 0) {
            setChartData(res.hourly_curve)
          } else {
            // Build deterministic curve centered on actual load_pct without Math.random()
            const baseLoad = res.load_pct
            const curve = Array.from({ length: 24 }, (_, i) => ({
              time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
              load: Math.round(baseLoad * (0.65 + 0.35 * Math.sin((i - 14) * Math.PI / 12))),
            }))
            setChartData(curve)
          }
        }
      } catch (err) {
        console.warn('[EnergyCard] Failed to fetch live energy status:', err)
      } finally {
        if (isMounted) setLoading(false)
      }
    }

    loadEnergy()
    const timer = setInterval(loadEnergy, 60000)
    return () => {
      isMounted = false
      clearInterval(timer)
    }
  }, [])

  // Slice data based on selected timeRange
  const displayData = (() => {
    if (chartData.length === 0) {
      return Array.from({ length: 24 }, (_, i) => ({
        time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
        load: Math.round(loadPct * (0.65 + 0.35 * Math.sin((i - 14) * Math.PI / 12))),
      }))
    }
    if (timeRange === '1 HOUR') return chartData.slice(0, 2)
    if (timeRange === '6 HOURS') return chartData.slice(0, 6)
    return chartData.slice(0, 24)
  })()

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
            background: 'var(--accent-energy-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <Zap size={16} color="var(--accent-energy)" strokeWidth={1.8} />
          </div>
          <div>
            <h3 style={{
              fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.06em',
              fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
            }}>ENERGY CONSUMPTION ({timeRange})</h3>
          </div>
        </div>
        <button
          onClick={() => navigate('/energy')}
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
        {/* Left */}
        <div>
          <div style={{
            fontSize: '2.4rem', fontWeight: 700, color: 'var(--text-primary)',
            fontFamily: 'var(--font-heading)', lineHeight: 1.1,
          }}>
            <AnimatedCounter value={loadPct} decimals={1} suffix="%" />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
            <span style={{
              padding: '2px 10px', borderRadius: 'var(--radius-full)',
              fontSize: '0.65rem', fontWeight: 600,
              background: 'var(--accent-energy-dim)', color: '#B8860B',
              border: '1px solid rgba(244,166,42,0.2)',
            }}>{severity}</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>Grid Load</div>
        </div>

        {/* Right - Chart */}
        <div style={{ height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={displayData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="energyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#F4A62A" stopOpacity={0.12} />
                  <stop offset="100%" stopColor="#F4A62A" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 9, fill: '#8F9295' }} interval={displayData.length <= 6 ? 0 : 3} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: '#8F9295' }} axisLine={false} tickLine={false} domain={[0, 100]} unit="%" />
              <ReferenceLine
                y={75}
                stroke="#6C8FC5"
                strokeDasharray="6 3"
                strokeWidth={1}
                label={{ value: 'Optimal Threshold', position: 'insideBottomRight', fill: '#6C8FC5', fontSize: 9, fontFamily: 'var(--font-mono)' }}
              />
              <Tooltip
                contentStyle={{
                  background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                  borderRadius: 8, fontSize: '0.72rem', color: 'var(--text-primary)',
                  boxShadow: 'var(--shadow-elevated)',
                }}
              />
              <Area type="monotone" dataKey="load" stroke="#F4A62A" strokeWidth={1.5} fill="url(#energyGrad)" name="Load (%)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}

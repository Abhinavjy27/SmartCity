import { useState, useEffect } from 'react'
import { Car, ArrowRight } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AnimatedCounter from '../AnimatedCounter'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts'
import { trafficApi } from '../../services/api'

function DonutChart({ data, total }) {
  const size = 110
  const strokeWidth = 16
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="var(--border-divider, #ECEAE5)" strokeWidth={strokeWidth}
        />
        {data.filter(d => d.pct > 0).map((d) => {
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
        alignItems: 'center', justifyContent: 'center', pointerEvents: 'none',
      }}>
        <span style={{ fontSize: '1.1rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: 'var(--text-primary)', lineHeight: 1 }}>
          {total}
        </span>
        <span style={{ fontSize: '0.58rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
          Corridors
        </span>
      </div>
    </div>
  )
}

export default function TrafficFlowCard() {
  const navigate = useNavigate()
  const [congestion, setCongestion] = useState({
    value_pct: null,
    delta_pp: null,
    baseline_available: false,
    valid_points: 0,
    total_points: 21,
    level: null,
    updated_at: null,
    status: 'unavailable',
  })
  const [corridors, setCorridors] = useState([])
  const [history, setHistory] = useState([])

  useEffect(() => {
    let isMounted = true

    const loadData = async () => {
      if (typeof document !== 'undefined' && document.hidden) return

      try {
        const [congData, corrData, histData] = await Promise.allSettled([
          trafficApi.getCongestionIndex(),
          trafficApi.getCorridors(),
          trafficApi.getCongestionHistory(24),
        ])

        if (!isMounted) return

        if (congData.status === 'fulfilled' && congData.value) {
          setCongestion(prev => {
            if (congData.value.value_pct === null && prev?.value_pct !== null) {
              return { ...prev, status: 'stale' }
            }
            return congData.value
          })
        }

        if (corrData.status === 'fulfilled' && corrData.value?.corridors) {
          setCorridors(corrData.value.corridors)
        }

        if (histData.status === 'fulfilled' && Array.isArray(histData.value)) {
          setHistory(histData.value)
        }
      } catch (err) {
        console.warn('[TrafficFlowCard] Fetch error:', err)
      }
    }

    loadData()
    const interval = setInterval(loadData, 60000)

    const handleVisibility = () => {
      if (!document.hidden) loadData()
    }
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      isMounted = false
      clearInterval(interval)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [])

  // Derive corridor donut metrics
  const totalCorridors = corridors.length
  const freeCount = corridors.filter(c => c.status === 'Free Flow' || c.status === 'Good').length
  const modCount = corridors.filter(c => c.status === 'Moderate').length
  const congCount = corridors.filter(c => c.status === 'Congested' || c.status === 'Severe' || c.status === 'High Delay').length

  const freePct = totalCorridors > 0 ? Math.round((freeCount / totalCorridors) * 100) : 0
  const modPct = totalCorridors > 0 ? Math.round((modCount / totalCorridors) * 100) : 0
  const congPct = totalCorridors > 0 ? Math.max(0, 100 - freePct - modPct) : 0

  const donutData = [
    { label: 'Free Flow', count: freeCount, pct: freePct, color: '#2F8F72' },
    { label: 'Moderate', count: modCount, pct: modPct, color: '#F4A62A' },
    { label: 'Congested', count: congCount, pct: congPct, color: '#E5483F' },
  ]

  // Chart data from real TomTom history snapshots
  const chartData = history.map(item => {
    const d = new Date(item.t)
    const hour = d.getHours()
    const ampm = hour >= 12 ? 'PM' : 'AM'
    const displayHour = hour % 12 === 0 ? 12 : hour % 12
    const min = d.getMinutes().toString().padStart(2, '0')
    return {
      time: `${displayHour}:${min} ${ampm}`,
      congestion: item.value_pct,
    }
  })

  const displayChartData = chartData.length === 1
    ? [{ time: 'Earlier', congestion: chartData[0].congestion }, chartData[0]]
    : chartData

  // Level Badge configuration
  const level = congestion.level || (congestion.value_pct !== null ? (
    congestion.value_pct < 15 ? 'light' :
    congestion.value_pct < 30 ? 'moderate' :
    congestion.value_pct < 50 ? 'heavy' : 'severe'
  ) : null)

  const levelStyles = {
    light: { bg: 'rgba(47, 143, 114, 0.1)', color: '#2F8F72', border: 'rgba(47, 143, 114, 0.25)' },
    moderate: { bg: 'rgba(244, 166, 42, 0.12)', color: '#B8860B', border: 'rgba(244, 166, 42, 0.25)' },
    heavy: { bg: 'rgba(229, 72, 63, 0.12)', color: '#E5483F', border: 'rgba(229, 72, 63, 0.25)' },
    severe: { bg: 'rgba(139, 0, 0, 0.12)', color: '#8B0000', border: 'rgba(139, 0, 0, 0.25)' },
  }
  const currentBadgeStyle = level ? (levelStyles[level.toLowerCase()] || levelStyles.moderate) : null

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
      <div style={{ display: 'grid', gridTemplateColumns: '180px 180px 1fr', gap: '24px', alignItems: 'center' }}>
        {/* Left - Big number */}
        <div>
          <div style={{
            fontSize: '2.4rem', fontWeight: 700, color: 'var(--text-primary)',
            fontFamily: 'var(--font-heading)', lineHeight: 1.1,
          }}>
            {congestion.value_pct !== null && congestion.value_pct !== undefined ? (
              <AnimatedCounter value={congestion.value_pct} decimals={1} suffix="%" />
            ) : (
              '—'
            )}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px', fontWeight: 500 }}>
            Congestion Index
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px', flexWrap: 'wrap' }}>
            {currentBadgeStyle && (
              <span style={{
                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                fontSize: '0.65rem', fontWeight: 600,
                background: currentBadgeStyle.bg, color: currentBadgeStyle.color,
                border: `1px solid ${currentBadgeStyle.border}`,
                textTransform: 'capitalize',
              }}>
                {level}
              </span>
            )}
            {congestion.baseline_available && congestion.delta_pp !== null ? (
              <span style={{
                fontSize: '0.65rem', fontWeight: 600,
                fontFamily: 'var(--font-mono)',
                color: congestion.delta_pp > 0 ? '#E5483F' : '#2F8F72',
              }}>
                {congestion.delta_pp > 0 ? `▲ +${congestion.delta_pp.toFixed(1)}%` : `▼ ${congestion.delta_pp.toFixed(1)}%`}
              </span>
            ) : (
              <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {congestion.status === 'live' ? '● Live' : congestion.status === 'stale' ? '● Stale' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Middle - Donut + legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <DonutChart data={donutData} total={totalCorridors} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {donutData.map(d => (
              <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: d.color, flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', fontWeight: 500 }}>{d.label}</div>
                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {d.count} ({d.pct}%)
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right - Line chart */}
        <div style={{ height: 140 }}>
          {displayChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={displayChartData} margin={{ top: 8, right: 12, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="trafficGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2F8F72" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#2F8F72" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 9, fill: '#8F9295' }}
                  interval="preserveStartEnd"
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 9, fill: '#8F9295' }}
                  axisLine={false}
                  tickLine={false}
                  unit="%"
                  domain={[0, (dataMax) => Math.max(35, Math.ceil((dataMax + 5) / 10) * 10)]}
                />
                <Tooltip
                  formatter={(val) => [`${Number(val).toFixed(1)}%`, 'Congestion Index']}
                  contentStyle={{
                    background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                    borderRadius: 8, fontSize: '0.72rem', color: 'var(--text-primary)',
                    boxShadow: 'var(--shadow-elevated)',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="congestion"
                  stroke="#2F8F72"
                  strokeWidth={2}
                  fill="url(#trafficGrad)"
                  name="Congestion Index"
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{
              height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--text-muted)', fontSize: '0.72rem', fontFamily: 'var(--font-mono)'
            }}>
              Awaiting 24h congestion snapshots...
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

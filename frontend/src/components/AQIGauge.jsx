import { useState, useEffect } from 'react'

export default function AQIGauge({ value = 0, maxValue = 500, size = 200 }) {
  const [animatedValue, setAnimatedValue] = useState(0)

  useEffect(() => {
    let raf
    const start = performance.now()
    const animate = (now) => {
      const progress = Math.min((now - start) / 1500, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setAnimatedValue(eased * value)
      if (progress < 1) raf = requestAnimationFrame(animate)
    }
    raf = requestAnimationFrame(animate)
    return () => cancelAnimationFrame(raf)
  }, [value])

  const getAQIInfo = (val) => {
    if (val <= 50) return { label: 'Good', color: '#10b981', bg: 'rgba(16,185,129,0.15)' }
    if (val <= 100) return { label: 'Satisfactory', color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' }
    if (val <= 200) return { label: 'Moderate', color: '#f59e0b', bg: 'rgba(245,158,11,0.15)' }
    if (val <= 300) return { label: 'Poor', color: '#f97316', bg: 'rgba(249,115,22,0.15)' }
    if (val <= 400) return { label: 'Very Poor', color: '#ef4444', bg: 'rgba(239,68,68,0.15)' }
    return { label: 'Severe', color: '#dc2626', bg: 'rgba(220,38,38,0.15)' }
  }

  const info = getAQIInfo(animatedValue)
  const radius = (size - 20) / 2
  const cx = size / 2
  const cy = size / 2 + 10
  const circumference = Math.PI * radius
  const progress = Math.min(animatedValue / maxValue, 1)
  const offset = circumference * (1 - progress)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
      <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`}>
        {/* Background arc */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke="var(--bg-tertiary)"
          strokeWidth="12"
          strokeLinecap="round"
        />
        {/* Colored progress arc */}
        <path
          d={`M ${cx - radius} ${cy} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
          fill="none"
          stroke={info.color}
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{
            transition: 'stroke 0.3s ease',
          }}
        />
        {/* Value text */}
        <text x={cx} y={cy - 20} textAnchor="middle" fill={info.color}
          style={{ fontSize: '2.2rem', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
          {Math.round(animatedValue)}
        </text>
        <text x={cx} y={cy + 2} textAnchor="middle" fill="var(--text-muted)"
          style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}>
          US AQI
        </text>
      </svg>
      <span className="badge" style={{
        background: info.bg, color: info.color,
        border: `1px solid ${info.color}33`,
        fontSize: '0.8rem', padding: '5px 16px',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: '50%', background: info.color, animation: 'pulse-glow 2s infinite' }} />
        {info.label}
      </span>
    </div>
  )
}

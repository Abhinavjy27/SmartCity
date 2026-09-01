import { Car, Wind, Zap, CloudSun, Shield } from 'lucide-react'
import AnimatedCounter from '../AnimatedCounter'

const kpis = [
  {
    icon: Car, label: 'ACTIVE VEHICLES', value: 2342, decimals: 0,
    trend: '12.3%', trendDir: 'up', trendLabel: 'vs yesterday',
    color: '#2F8F72', bgColor: 'rgba(47, 143, 114, 0.08)',
  },
  {
    icon: Wind, label: 'CURRENT AQI', value: 136, decimals: 0,
    trend: '8.0%', trendDir: 'down', trendLabel: 'vs yesterday',
    color: '#4C9E9B', bgColor: 'rgba(76, 158, 155, 0.08)',
  },
  {
    icon: Zap, label: 'GRID LOAD', value: 78.4, suffix: '%', decimals: 1,
    trend: '3.2%', trendDir: 'up', trendLabel: 'vs yesterday',
    color: '#F4A62A', bgColor: 'rgba(244, 166, 42, 0.08)',
  },
  {
    icon: CloudSun, label: 'TEMPERATURE', value: 29, suffix: '°C', decimals: 0,
    staticLabel: 'Clear Skies',
    color: '#6C8FC5', bgColor: 'rgba(108, 143, 197, 0.08)',
  },
  {
    icon: Shield, label: 'ACTIVE INCIDENTS', value: 24, decimals: 0,
    staticLabel: '3 new today',
    color: '#E5483F', bgColor: 'rgba(229, 72, 63, 0.08)',
  },
]

export default function CommandCenterKPI() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'stretch',
      background: 'var(--bg-card)',
      border: '1px solid var(--border-card)',
      borderRadius: 'var(--radius-lg)',
      padding: '20px 8px',
      boxShadow: 'var(--shadow-card)',
      gap: '0',
      overflowX: 'auto',
    }}>
      {kpis.map((kpi, idx) => {
        const Icon = kpi.icon
        return (
          <div key={kpi.label} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: '170px' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '14px',
              padding: '0 16px', flex: 1,
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
              onMouseEnter={e => e.currentTarget.style.opacity = '0.85'}
              onMouseLeave={e => e.currentTarget.style.opacity = '1'}
            >
              {/* Icon circle */}
              <div style={{
                width: 42, height: 42, borderRadius: '50%',
                background: kpi.bgColor,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
              }}>
                <Icon size={18} color={kpi.color} strokeWidth={1.8} />
              </div>
              {/* Content */}
              <div>
                <div style={{
                  fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)',
                  letterSpacing: '0.1em', marginBottom: '2px',
                  fontFamily: 'var(--font-mono)', textTransform: 'uppercase',
                }}>
                  {kpi.label}
                </div>
                <div style={{
                  fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)',
                  lineHeight: 1.1, fontFamily: 'var(--font-heading)',
                }}>
                  <AnimatedCounter value={kpi.value} decimals={kpi.decimals} suffix={kpi.suffix || ''} />
                </div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '3px' }}>
                  {kpi.trend ? (
                    <>
                      <span style={{ color: kpi.trendDir === 'up' ? 'var(--accent-traffic)' : 'var(--accent-warning)', fontWeight: 600 }}>
                        {kpi.trendDir === 'up' ? '▲' : '▼'} {kpi.trend}
                      </span>
                      <span>{kpi.trendLabel}</span>
                    </>
                  ) : (
                    <span>{kpi.staticLabel}</span>
                  )}
                </div>
              </div>
            </div>
            {/* Divider */}
            {idx < kpis.length - 1 && (
              <div style={{
                width: '1px', height: '50px',
                background: 'var(--border-default)',
                flexShrink: 0,
              }} />
            )}
          </div>
        )
      })}
    </div>
  )
}

import AnimatedCounter from './AnimatedCounter'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function MetricCard({ icon: Icon, label, value, suffix = '', prefix = '', decimals = 0, trend, trendValue, color = 'cyan', subtitle }) {
  const colorMap = {
    cyan: { bg: 'var(--accent-cyan-dim)', fg: 'var(--accent-cyan)' },
    emerald: { bg: 'var(--accent-emerald-dim)', fg: 'var(--accent-emerald)' },
    violet: { bg: 'var(--accent-violet-dim)', fg: 'var(--accent-violet)' },
    amber: { bg: 'var(--accent-amber-dim)', fg: 'var(--accent-amber)' },
    rose: { bg: 'var(--accent-rose-dim)', fg: 'var(--accent-rose)' },
    blue: { bg: 'var(--accent-blue-dim)', fg: 'var(--accent-blue)' },
  }
  const c = colorMap[color] || colorMap.cyan

  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus

  return (
    <div className="glass-card">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{
          width: 40, height: 40, borderRadius: 'var(--radius-sm)',
          background: c.bg, display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: `1px solid rgba(255, 255, 255, 0.05)`,
        }}>
          {Icon && <Icon size={20} color={c.fg} />}
        </div>
        {trend && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: '4px',
            padding: '3px 8px', borderRadius: 'var(--radius-full)',
            background: trend === 'up' ? 'var(--accent-emerald-dim)' : trend === 'down' ? 'var(--accent-rose-dim)' : 'var(--bg-elevated)',
            fontSize: '0.7rem', fontFamily: 'var(--font-mono)', fontWeight: 600,
            color: trend === 'up' ? 'var(--accent-emerald)' : trend === 'down' ? 'var(--accent-rose)' : 'var(--text-muted)',
          }}>
            <TrendIcon size={12} />
            {trendValue}
          </div>
        )}
      </div>

      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '4px', fontWeight: 500 }}>
        {label}
      </div>
      <div style={{ fontSize: '1.6rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.1 }}>
        <AnimatedCounter value={value} prefix={prefix} suffix={suffix} decimals={decimals} />
      </div>
      {subtitle && (
        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>
          {subtitle}
        </div>
      )}
    </div>
  )
}

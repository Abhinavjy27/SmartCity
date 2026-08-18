export default function GlassCard({ children, style = {}, className = '', glow = '', hover = true, ...props }) {
  const glowMap = {
    cyan: 'var(--shadow-glow-cyan)',
    emerald: 'var(--shadow-glow-emerald)',
    violet: 'var(--shadow-glow-violet)',
    amber: 'var(--shadow-glow-amber)',
    rose: 'var(--shadow-glow-rose)',
  }

  return (
    <div
      className={`glass-card ${className}`}
      style={{
        boxShadow: glow ? glowMap[glow] : undefined,
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  )
}

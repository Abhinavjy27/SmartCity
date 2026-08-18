export default function StatusBadge({ status }) {
  const map = {
    SMOOTH: { className: 'badge-smooth', label: 'Smooth' },
    MODERATE: { className: 'badge-moderate', label: 'Moderate' },
    HEAVY: { className: 'badge-heavy', label: 'Heavy' },
    GOOD: { className: 'badge-smooth', label: 'Good' },
    SATISFACTORY: { className: 'badge-info', label: 'Satisfactory' },
    MODERATE_AQI: { className: 'badge-moderate', label: 'Moderate' },
    POOR: { className: 'badge-heavy', label: 'Poor' },
    SEVERE: { className: 'badge-heavy', label: 'Severe' },
    ONLINE: { className: 'badge-smooth', label: 'Online' },
    OFFLINE: { className: 'badge-heavy', label: 'Offline' },
    OPTIMIZED: { className: 'badge-info', label: 'AI Optimized' },
    WARNING: { className: 'badge-moderate', label: 'Warning' },
    CRITICAL: { className: 'badge-heavy', label: 'Critical' },
    AI: { className: 'badge-ai', label: 'AI Active' },
  }

  const { className, label } = map[status] || { className: 'badge-info', label: status }

  return (
    <span className={`badge ${className}`}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: 'currentColor',
        animation: 'pulse-glow 2s ease-in-out infinite',
      }} />
      {label}
    </span>
  )
}

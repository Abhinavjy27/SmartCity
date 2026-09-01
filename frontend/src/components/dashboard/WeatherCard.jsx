import { CloudSun, Droplets, Wind as WindIcon, CloudRain, Gauge, ArrowRight, Sun, Moon, Cloud } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const forecast = [
  { time: '11 AM', temp: 30, icon: 'sun' },
  { time: '2 PM', temp: 31, icon: 'sun' },
  { time: '5 PM', temp: 29, icon: 'cloud-sun' },
  { time: '8 PM', temp: 27, icon: 'cloud' },
  { time: '11 PM', temp: 26, icon: 'moon' },
]

const weatherDetails = [
  { icon: Droplets, label: 'Humidity', value: '48%' },
  { icon: WindIcon, label: 'Wind', value: '12 km/h' },
  { icon: CloudRain, label: 'Rainfall', value: '0 mm' },
  { icon: Gauge, label: 'Pressure', value: '1012 hPa' },
]

function WeatherIcon({ type, size = 20 }) {
  const iconMap = {
    'sun': Sun,
    'cloud-sun': CloudSun,
    'cloud': Cloud,
    'moon': Moon,
  }
  const Icon = iconMap[type] || Sun
  const colorMap = {
    'sun': '#F4A62A',
    'cloud-sun': '#F4A62A',
    'cloud': '#8F9295',
    'moon': '#6C8FC5',
  }
  return <Icon size={size} color={colorMap[type] || '#F4A62A'} strokeWidth={1.5} />
}

export default function WeatherCard() {
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
            background: 'var(--accent-weather-dim)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <CloudSun size={16} color="var(--accent-weather)" strokeWidth={1.8} />
          </div>
          <div>
            <h3 style={{
              fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.06em',
              fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
            }}>WEATHER OVERVIEW</h3>
          </div>
        </div>
        <button
          onClick={() => navigate('/weather')}
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
      <div style={{ display: 'flex', alignItems: 'center', gap: '32px', flexWrap: 'wrap' }}>
        {/* Temperature */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Sun size={32} color="#F4A62A" strokeWidth={1.5} />
          <div>
            <div style={{
              fontSize: '2.2rem', fontWeight: 700, color: 'var(--text-primary)',
              fontFamily: 'var(--font-heading)', lineHeight: 1.1,
            }}>
              29°C
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Clear Skies</div>
          </div>
        </div>

        {/* Weather details */}
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          {weatherDetails.map(detail => {
            const Icon = detail.icon
            return (
              <div key={detail.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Icon size={15} color="var(--text-muted)" strokeWidth={1.5} />
                <div>
                  <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{detail.label}</div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>{detail.value}</div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Divider */}
        <div style={{ width: '1px', height: '50px', background: 'var(--border-default)', flexShrink: 0 }} />

        {/* Forecast timeline */}
        <div style={{ display: 'flex', gap: '12px', flex: 1, justifyContent: 'space-around', minWidth: '280px' }}>
          {forecast.map(f => (
            <div key={f.time} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
              padding: '10px 12px',
              background: 'var(--bg-workspace)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-divider)',
              minWidth: '60px',
            }}>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{f.time}</span>
              <WeatherIcon type={f.icon} size={18} />
              <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>{f.temp}°C</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

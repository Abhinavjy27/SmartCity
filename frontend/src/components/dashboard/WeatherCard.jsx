import { useState, useEffect } from 'react'
import { CloudSun, Droplets, Wind as WindIcon, CloudRain, Gauge, ArrowRight, Sun, Moon, Cloud, CloudLightning } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { weatherApi } from '../../services/api'

function WeatherIcon({ type, size = 20 }) {
  const iconMap = {
    'sun': Sun,
    'cloud-sun': CloudSun,
    'cloud': Cloud,
    'moon': Moon,
    'cloud-rain': CloudRain,
    'cloud-lightning': CloudLightning,
  }
  const Icon = iconMap[type] || Sun
  const colorMap = {
    'sun': '#F4A62A',
    'cloud-sun': '#F4A62A',
    'cloud': '#8F9295',
    'moon': '#6C8FC5',
    'cloud-rain': '#6C8FC5',
    'cloud-lightning': '#E5483F',
  }
  return <Icon size={size} color={colorMap[type] || '#F4A62A'} strokeWidth={1.5} />
}

export default function WeatherCard({ timeRange = '24 HOURS' }) {
  const navigate = useNavigate()
  const [currentWeather, setCurrentWeather] = useState({
    temp: 29,
    condition: 'Clear Skies',
    humidity: '48%',
    wind: '12 km/h',
    rainfall: '0.0 mm',
    pressure: '1012 hPa',
    isLive: false,
  })
  const [forecastItems, setForecastItems] = useState([
    { time: 'Now', temp: 29, icon: 'sun' },
    { time: '+2h', temp: 31, icon: 'sun' },
    { time: '+4h', temp: 29, icon: 'cloud-sun' },
    { time: '+6h', temp: 27, icon: 'cloud' },
    { time: '+8h', temp: 26, icon: 'moon' },
  ])

  useEffect(() => {
    let isMounted = true

    const loadWeather = async () => {
      try {
        const data = await weatherApi.getCurrent('Hyderabad')
        if (!isMounted || !data) return

        const t = data.temperature_c ?? 29
        const cond = data.condition || 'Partly Cloudy'
        const hum = data.humidity_pct ?? 50
        const wSpeed = data.wind_speed_kmh ?? 10
        const pMm = data.precipitation_mm ?? 0.0
        const pres = data.pressure_hpa ?? 1012

        setCurrentWeather({
          temp: Math.round(t),
          condition: cond,
          humidity: `${hum}%`,
          wind: `${wSpeed} km/h`,
          rainfall: `${pMm} mm`,
          pressure: `${pres} hPa`,
          isLive: data.is_live ?? true,
        })

        if (data.hourly_temp && data.hourly_temp.length >= 5) {
          // Pick 5 points across the hourly forecast
          const step = timeRange === '1 HOUR' ? 1 : timeRange === '6 HOURS' ? 1 : 4
          const points = data.hourly_temp.filter((_, idx) => idx % step === 0).slice(0, 5).map(h => {
            let ic = 'sun'
            if (h.rain_chance > 40) ic = 'cloud-rain'
            else if (h.temp > 30) ic = 'sun'
            else ic = 'cloud-sun'

            return {
              time: h.h || h.time,
              temp: Math.round(h.temp),
              icon: ic,
            }
          })
          if (points.length > 0) setForecastItems(points)
        }
      } catch (err) {
        console.warn('[WeatherCard] Failed to fetch live weather:', err)
      }
    }

    loadWeather()
    const timer = setInterval(loadWeather, 60000)
    return () => {
      isMounted = false
      clearInterval(timer)
    }
  }, [timeRange])

  const detailsList = [
    { icon: Droplets, label: 'Humidity', value: currentWeather.humidity },
    { icon: WindIcon, label: 'Wind', value: currentWeather.wind },
    { icon: CloudRain, label: 'Rainfall', value: currentWeather.rainfall },
    { icon: Gauge, label: 'Pressure', value: currentWeather.pressure },
  ]

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
            }}>WEATHER OVERVIEW ({timeRange})</h3>
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
              {currentWeather.temp}°C
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{currentWeather.condition}</div>
          </div>
        </div>

        {/* Weather details */}
        <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
          {detailsList.map(detail => {
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
          {forecastItems.map(f => (
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

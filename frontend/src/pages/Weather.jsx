import { useState, useEffect, useCallback } from 'react'
import {
  CloudSun, Thermometer, Droplets, Wind, Gauge, CloudRain, Sun, Cloud,
  CloudLightning, AlertTriangle, ArrowRight, RefreshCw, MapPin, Send, MessageSquare, Search
} from 'lucide-react'
import AnimatedCounter from '../components/AnimatedCounter'
import {
  Area, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ComposedChart
} from 'recharts'
import { weatherApi } from '../services/api/weatherApi'

/* ── Fallback Seed Data ── */
const defaultHourly = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  temp: Math.round((28 + 8 * Math.sin((i - 6) * Math.PI / 12)) * 10) / 10,
  humidity: Math.round(60 - 20 * Math.sin((i - 6) * Math.PI / 12)),
  pressure: 1012,
  rain: Math.max(0, Math.round(Math.max(0, 20 * Math.exp(-((i - 22) ** 2) / 8)))),
}))

const defaultWeekForecast = [
  { day: 'Today', weather: '☀️', maxMin: '34° / 24°', rain: '0%' },
  { day: 'Tomorrow', weather: '⛅', maxMin: '33° / 24°', rain: '15%' },
  { day: 'Day 3', weather: '🌧️', maxMin: '31° / 23°', rain: '55%' },
  { day: 'Day 4', weather: '⛈️', maxMin: '30° / 22°', rain: '75%' },
  { day: 'Day 5', weather: '⛅', maxMin: '32° / 23°', rain: '30%' },
  { day: 'Day 6', weather: '🌤️', maxMin: '33° / 24°', rain: '10%' },
  { day: 'Day 7', weather: '☀️', maxMin: '35° / 25°', rain: '5%' },
]

const defaultRainfallWeek = [
  { day: 'Mon', rain: 0, thisWeek: 0, lastWeek: 2 },
  { day: 'Tue', rain: 2, thisWeek: 2, lastWeek: 4 },
  { day: 'Wed', rain: 0, thisWeek: 0, lastWeek: 1 },
  { day: 'Thu', rain: 8, thisWeek: 8, lastWeek: 5 },
  { day: 'Fri', rain: 5, thisWeek: 5, lastWeek: 3 },
  { day: 'Sat', rain: 12, thisWeek: 12, lastWeek: 8 },
  { day: 'Sun', rain: 0, thisWeek: 0, lastWeek: 2 },
]

const defaultHumidityPressure = Array.from({ length: 24 }, (_, i) => ({
  time: `${i % 12 === 0 ? 12 : i % 12} ${i < 12 ? 'AM' : 'PM'}`,
  humidity: Math.round(60 - 20 * Math.sin((i - 6) * Math.PI / 12)),
  pressure: Math.round(1008 + 6 * Math.sin((i - 12) * Math.PI / 12)),
}))

const windDirections = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']

const PRESET_LOCALITIES = [
  'Hyderabad',
  'Narayanguda',
  'Begumpet',
  'Gachibowli',
  'Hitec City',
  'Madhapur',
  'Kukatpally',
  'Secunderabad',
  'Charminar',
  'Sanathnagar',
  'Banjara Hills',
  'Jubilee Hills',
]

export default function Weather() {
  const [timeRange, setTimeRange] = useState('24 Hours')
  const [selectedLocality, setSelectedLocality] = useState('Hyderabad')
  const [customLocationInput, setCustomLocationInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [weatherData, setWeatherData] = useState(null)
  const [alertsData, setAlertsData] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(new Date().toLocaleTimeString())

  // Conversational Assistant State
  const [chatQuestion, setChatQuestion] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [chatResponse, setChatResponse] = useState(null)

  const loadWeather = useCallback(async (locality) => {
    setLoading(true)
    try {
      const [currentRes, alertsRes] = await Promise.all([
        weatherApi.getCurrent(locality),
        weatherApi.getAlerts(locality),
      ])
      if (currentRes && currentRes.temperature_c !== undefined) {
        setWeatherData(currentRes)
      }
      if (alertsRes && alertsRes.alerts) {
        setAlertsData(alertsRes)
      }
      setLastUpdated(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
    } catch (e) {
      console.warn('Weather fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadWeather(selectedLocality)
  }, [selectedLocality, loadWeather])

  const handleCustomLocationSubmit = (e) => {
    e.preventDefault()
    if (customLocationInput.trim()) {
      setSelectedLocality(customLocationInput.trim())
      setCustomLocationInput('')
    }
  }

  const handleAskWeatherQuestion = async (queryText) => {
    const q = (queryText || chatQuestion).trim()
    if (!q) return
    setChatLoading(true)
    try {
      const res = await weatherApi.chat(q, selectedLocality)
      if (res && res.text) {
        setChatResponse(res)
      }
    } catch (err) {
      console.error('Weather chat error:', err)
    } finally {
      setChatLoading(false)
    }
  }

  // Extract live metrics with fallbacks
  const temp = weatherData?.temperature_c ?? 29.5
  const feelsLike = weatherData?.feels_like_c ?? Math.round(temp + 2)
  const condition = weatherData?.condition ?? 'Partly Cloudy'
  const humidity = weatherData?.humidity_pct ?? 54
  const windSpeed = weatherData?.wind_speed_kmh ?? 12
  const windDir = weatherData?.wind_direction ?? 'NE'
  const pressure = weatherData?.pressure_hpa ?? 1012
  const visibility = weatherData?.visibility_km ?? 10
  const dewPoint = weatherData?.dew_point_c ?? 18
  const uvIndex = weatherData?.uv_index ?? 6
  const isLive = weatherData?.is_live ?? false
  const providerName = weatherData?.provider ?? 'Live Telemetry'
  const resolvedLocalityName = weatherData?.city || selectedLocality

  // Hourly chart data from live API
  const hourlyData = weatherData?.hourly_temp && weatherData.hourly_temp.length > 0
    ? weatherData.hourly_temp.map(h => ({
        time: h.h || h.time,
        temp: h.temp,
        humidity: h.humidity,
        pressure: h.pressure || pressure,
        rain: h.rain_chance || 0,
      }))
    : defaultHourly

  // 7-Day forecast cards from live API
  const forecastDays = weatherData?.forecast_7d && weatherData.forecast_7d.length > 0
    ? weatherData.forecast_7d.map(f => {
        let emoji = '⛅'
        const cLower = (f.condition || '').toLowerCase()
        if (cLower.includes('clear') || cLower.includes('sun')) emoji = '☀️'
        else if (cLower.includes('thunder')) emoji = '⛈️'
        else if (cLower.includes('rain') || cLower.includes('drizzle')) emoji = '🌧️'
        else if (cLower.includes('overcast') || cLower.includes('cloud')) emoji = '☁️'
        return {
          day: f.day,
          weather: emoji,
          maxMin: `${f.high}° / ${f.low}°`,
          rain: f.rain || '0%',
        }
      })
    : defaultWeekForecast

  // Live 7-day rainfall data from API
  const rainfallData = weatherData?.weekly_precipitation && weatherData.weekly_precipitation.length > 0
    ? weatherData.weekly_precipitation.map(r => ({
        day: r.day,
        thisWeek: r.rain ?? r.thisWeek ?? 0,
        lastWeek: r.lastWeek ?? Math.round(Math.max(0, (r.rain || 0) * 0.7)),
      }))
    : defaultRainfallWeek

  // Today's summary extremes
  const todayHigh = weatherData?.forecast_7d?.[0]?.high ?? 34
  const todayLow = weatherData?.forecast_7d?.[0]?.low ?? 24
  const todayRain = weatherData?.precipitation_mm ?? 0.0

  // Alerts
  const alertsList = alertsData?.alerts && alertsData.alerts.length > 0
    ? alertsData.alerts
    : [
        { title: 'Normal Conditions', desc: 'No severe weather warnings active.', time: 'Now', color: '#2F8F72' }
      ]

  const riskLevel = alertsData?.risk_level ?? 'Low'
  const primaryRisk = alertsData?.primary_risk ?? 'None'
  const riskProb = alertsData?.probability_pct ?? 10
  const timeWindow = alertsData?.time_window ?? 'All Day'
  const pollenCount = alertsData?.pollen_count ?? 32
  const pollenLevel = alertsData?.pollen_level ?? 'Low'
  const airComfort = alertsData?.air_comfort ?? 'Good'
  const outdoorActivity = alertsData?.outdoor_activity ?? 'Good'
  const asthmaRisk = alertsData?.asthma_risk ?? 'Low'

  return (
    <div className="stagger-children">
      {/* Top Search & Controls Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: 'var(--space-lg)', flexWrap: 'wrap' }}>
        {/* Locality Selector Dropdown */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-full)', padding: '4px 12px' }}>
          <MapPin size={13} color="#6C8FC5" />
          <select
            value={PRESET_LOCALITIES.includes(selectedLocality) ? selectedLocality : ''}
            onChange={(e) => {
              if (e.target.value) setSelectedLocality(e.target.value)
            }}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.72rem',
              fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              outline: 'none',
            }}
          >
            <option value="" disabled>Popular Areas</option>
            {PRESET_LOCALITIES.map((loc) => (
              <option key={loc} value={loc} style={{ background: 'var(--bg-card)', color: 'var(--text-primary)' }}>
                {loc}
              </option>
            ))}
          </select>
        </div>

        {/* Custom Location Free-text Search Input */}
        <form onSubmit={handleCustomLocationSubmit} style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-full)', padding: '3px 8px 3px 12px', gap: '6px' }}>
          <Search size={12} color="var(--text-muted)" />
          <input
            type="text"
            value={customLocationInput}
            onChange={(e) => setCustomLocationInput(e.target.value)}
            placeholder="Type any area (e.g. Madhapur, Kukatpally)..."
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.72rem',
              outline: 'none',
              width: '190px',
            }}
          />
          <button
            type="submit"
            style={{
              background: '#6C8FC5',
              border: 'none',
              borderRadius: 'var(--radius-full)',
              color: '#fff',
              fontSize: '0.65rem',
              fontWeight: 600,
              padding: '3px 8px',
              cursor: 'pointer',
            }}
          >
            Search
          </button>
        </form>

        {['Now', '1 Hour', '6 Hours', '24 Hours', '7 Days'].map(t => (
          <button key={t} onClick={() => setTimeRange(t)} style={{
            padding: '6px 14px', borderRadius: 'var(--radius-full)',
            fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
            background: timeRange === t ? '#6C8FC5' : 'var(--bg-card)',
            color: timeRange === t ? '#fff' : 'var(--text-secondary)',
            border: timeRange === t ? 'none' : '1px solid var(--border-default)',
          }}>{t}</button>
        ))}

        <button
          onClick={() => loadWeather(selectedLocality)}
          disabled={loading}
          title="Refresh Live Weather from API"
          style={{
            padding: '6px 10px',
            borderRadius: 'var(--radius-full)',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            fontSize: '0.72rem',
          }}
        >
          <RefreshCw size={12} className={loading ? 'spin' : ''} />
          {loading ? 'Fetching...' : 'Sync'}
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '14px' }}>
          {/* Live Data Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.65rem',
            fontFamily: 'var(--font-mono)',
            padding: '3px 9px',
            borderRadius: 'var(--radius-full)',
            background: isLive ? 'rgba(47, 143, 114, 0.12)' : 'rgba(244, 166, 42, 0.12)',
            color: isLive ? '#2F8F72' : '#F4A62A',
            border: `1px solid ${isLive ? 'rgba(47, 143, 114, 0.3)' : 'rgba(244, 166, 42, 0.3)'}`
          }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: isLive ? '#2F8F72' : '#F4A62A', display: 'inline-block' }} />
            {isLive ? `LIVE API: ${providerName}` : 'OFFLINE BASELINE'}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            <span>☀️</span> <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{temp}°C</span> <span>{condition}</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', borderLeft: '1px solid var(--border-default)', paddingLeft: '14px' }}>
            {lastUpdated}
          </div>
        </div>
      </div>

      {/* Top Row: Current Weather + Today's Summary + Weather Alerts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 300px', gap: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        {/* Current Weather Card */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Current Weather — {resolvedLocalityName}
            </h3>
            <span style={{ fontSize: '0.62rem', color: isLive ? '#2F8F72' : 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {isLive ? '100% Live Telemetry' : 'Cached Baseline'}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' }}>
            <Sun size={40} color="#F4A62A" strokeWidth={1.5} />
            <div>
              <div style={{ fontSize: '2.8rem', fontWeight: 700, fontFamily: 'var(--font-heading)', lineHeight: 1 }}>
                <AnimatedCounter value={temp} decimals={1} suffix="°C" />
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Feels like {feelsLike}°C</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{condition}</div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '0.72rem' }}>
            {[
              { icon: Droplets, label: 'Humidity', value: `${humidity}%` },
              { icon: Wind, label: 'Wind', value: `${windSpeed} km/h ${windDir}` },
              { icon: Gauge, label: 'Pressure', value: `${pressure} hPa` },
              { icon: Sun, label: 'Visibility', value: `${visibility} km` },
              { icon: Thermometer, label: 'Dew Point', value: `${dewPoint}°C` },
              { icon: Sun, label: 'UV Index', value: `${uvIndex}` },
            ].map(d => {
              const Icon = d.icon
              return (
                <div key={d.label} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Icon size={13} color="var(--text-muted)" strokeWidth={1.5} />
                  <span style={{ color: 'var(--text-muted)' }}>{d.label}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', marginLeft: 'auto' }}>{d.value}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Today's Summary Card */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '16px' }}>Today's Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '16px' }}>
            {[
              { label: 'Max Temp', value: `${todayHigh}°C`, sub: 'Peak Day', icon: '🌡️', color: '#E5483F' },
              { label: 'Min Temp', value: `${todayLow}°C`, sub: 'Night Min', icon: '🌡️', color: '#6C8FC5' },
              { label: 'Rainfall', value: `${todayRain} mm`, sub: 'Precipitation', icon: '🌧️', color: 'var(--text-primary)' },
              { label: 'Wind Speed', value: `${windSpeed} km/h`, sub: windDir, icon: '💨', color: 'var(--text-primary)' },
            ].map(s => (
              <div key={s.label} style={{ textAlign: 'center', padding: '14px 8px', borderRadius: 'var(--radius-md)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)' }}>
                <span style={{ fontSize: '1.2rem' }}>{s.icon}</span>
                <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '6px' }}>{s.label}</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: s.color, fontFamily: 'var(--font-heading)', marginTop: '2px' }}>{s.value}</div>
                <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', marginTop: '2px' }}>{s.sub}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Weather Alerts Card */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Weather Alerts</h3>
            <span style={{ fontSize: '0.65rem', color: '#2F8F72', fontFamily: 'var(--font-mono)' }}>LIVE</span>
          </div>
          {alertsList.map((a, i) => (
            <div key={i} style={{ display: 'flex', gap: '10px', padding: '12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)', marginBottom: '10px' }}>
              <AlertTriangle size={16} color={a.color || '#F4A62A'} style={{ flexShrink: 0, marginTop: '2px' }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 600, color: a.color || '#F4A62A' }}>{a.title}</div>
                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>{a.desc}</div>
              </div>
              <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>{a.time}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Middle Row: 24h Forecast + 7-Day Forecast + Rainfall Overview */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr', gap: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        {/* 24-Hour Forecast Chart */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>
            24-Hour Live Temperature & Precipitation Curve
          </h3>
          <ResponsiveContainer width="100%" height={220}>
            <ComposedChart data={hourlyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="tempGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#E5483F" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#E5483F" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval={2} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit="°" />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem' }} />
              <Area type="monotone" dataKey="temp" stroke="#E5483F" strokeWidth={2} fill="url(#tempGrad)" name="Temperature (°C)" />
              <Bar dataKey="rain" fill="#6C8FC5" radius={[3, 3, 0, 0]} name="Rain Probability (%)" opacity={0.6} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* 7-Day Forecast */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>
            7-Day Outlook ({resolvedLocalityName})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {forecastDays.map((d, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', borderRadius: 'var(--radius-sm)', background: i === 0 ? 'rgba(108,143,197,0.08)' : 'transparent', fontSize: '0.72rem' }}>
                <span style={{ fontWeight: i === 0 ? 700 : 500, width: '70px', color: i === 0 ? '#6C8FC5' : 'var(--text-primary)' }}>{d.day}</span>
                <span style={{ fontSize: '0.9rem' }}>{d.weather}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: '0.68rem' }}>{d.maxMin}</span>
                <span style={{ fontFamily: 'var(--font-mono)', color: '#6C8FC5', fontSize: '0.65rem' }}>{d.rain}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 7-Day Rainfall Overview from live API */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>Rainfall Overview</h3>
            <span style={{ fontSize: '0.65rem', color: '#2F8F72', fontFamily: 'var(--font-mono)' }}>LIVE API</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
            <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)' }}>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Current Inflow</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                {todayRain} <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 400 }}>mm</span>
              </div>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>Surface accumulation</div>
            </div>
            <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)' }}>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Weekly Total</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
                {rainfallData.reduce((acc, curr) => acc + (curr.thisWeek || 0), 0).toFixed(1)} <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 400 }}>mm</span>
              </div>
              <div style={{ fontSize: '0.55rem', color: '#2F8F72', fontWeight: 600 }}>7-day cumulative</div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={rainfallData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <XAxis dataKey="day" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem' }} />
              <Bar dataKey="thisWeek" fill="#6C8FC5" radius={[3, 3, 0, 0]} name="Precipitation (mm)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row: Wind + Humidity/Pressure + Severe Weather + Pollen */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr 1fr 1fr', gap: 'var(--space-lg)', marginBottom: 'var(--space-lg)' }}>
        {/* Wind Overview */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Wind Vectors</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <div style={{ position: 'relative', width: 100, height: 100 }}>
              <svg width="100" height="100" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border-default)" strokeWidth="1" />
                <circle cx="50" cy="50" r="30" fill="none" stroke="var(--border-divider)" strokeWidth="0.5" />
                {windDirections.map((d, i) => {
                  const angle = (i * 45 - 90) * (Math.PI / 180)
                  const x = 50 + 42 * Math.cos(angle)
                  const y = 50 + 42 * Math.sin(angle)
                  return <text key={d} x={x} y={y} textAnchor="middle" dominantBaseline="middle" fontSize="7" fill={d === windDir ? '#6C8FC5' : 'var(--text-muted)'} fontFamily="var(--font-mono)" fontWeight={d === windDir ? 700 : 400}>{d}</text>
                })}
                <line x1="50" y1="50" x2="72" y2="28" stroke="#6C8FC5" strokeWidth="2" strokeLinecap="round" />
                <circle cx="50" cy="50" r="3" fill="#6C8FC5" />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>{windSpeed}</span>
                <span style={{ fontSize: '0.45rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>km/h</span>
                <span style={{ fontSize: '0.5rem', fontWeight: 600, color: '#6C8FC5' }}>{windDir}</span>
              </div>
            </div>
            <div style={{ fontSize: '0.68rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Wind Speed</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{windSpeed} km/h</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Direction</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>{windDir}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Dispersion</span>
                <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)', color: windSpeed > 10 ? '#2F8F72' : '#F4A62A' }}>
                  {windSpeed > 10 ? 'Advective' : 'Low'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Humidity & Pressure Trend using live hourly API data */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>
            Humidity & Surface Pressure Trend (Live)
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <ComposedChart data={hourlyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 7, fill: '#8F9295' }} interval={4} axisLine={false} tickLine={false} />
              <YAxis yAxisId="hum" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit="%" domain={[20, 100]} />
              <YAxis yAxisId="pres" orientation="right" tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} unit=" hPa" domain={['auto', 'auto']} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem' }} />
              <Area yAxisId="hum" type="monotone" dataKey="humidity" stroke="#6C8FC5" strokeWidth={1.5} fill="rgba(108,143,197,0.1)" name="Humidity (%)" />
              <Line yAxisId="pres" type="monotone" dataKey="pressure" stroke="#F4A62A" strokeWidth={1.5} dot={false} name="Pressure (hPa)" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        {/* Severe Weather Risk */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Severe Weather Risk</h3>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px' }}>
            <div style={{ position: 'relative', width: 110, height: 110 }}>
              <svg width="110" height="110" viewBox="0 0 110 110">
                <circle cx="55" cy="55" r="48" fill="none" stroke="rgba(0,0,0,0.04)" strokeWidth="6" />
                <circle cx="55" cy="55" r="48" fill="none" stroke={riskLevel === 'High' ? '#E5483F' : '#F4A62A'} strokeWidth="6"
                  strokeDasharray={`${(riskProb / 100) * 301.6} 301.6`}
                  strokeLinecap="round" transform="rotate(-90 55 55)" />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <CloudLightning size={22} color={riskLevel === 'High' ? '#E5483F' : '#F4A62A'} />
                <span style={{ fontSize: '0.9rem', fontWeight: 700, color: riskLevel === 'High' ? '#E5483F' : '#F4A62A', marginTop: '2px' }}>{riskLevel}</span>
                <span style={{ fontSize: '0.5rem', color: 'var(--text-muted)' }}>Risk Level</span>
              </div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.65rem' }}>
            <div><span style={{ color: 'var(--text-muted)' }}>Primary Risk</span><div style={{ fontWeight: 600 }}>{primaryRisk}</div></div>
            <div><span style={{ color: 'var(--text-muted)' }}>Probability</span><div style={{ fontWeight: 600 }}>{riskProb}%</div></div>
            <div><span style={{ color: 'var(--text-muted)' }}>Time Window</span><div style={{ fontWeight: 600 }}>{timeWindow}</div></div>
          </div>
        </div>

        {/* Pollen & Air Comfort */}
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>Pollen & Air Comfort</h3>
          <div style={{ textAlign: 'center', marginBottom: '16px' }}>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Pollen Count</div>
            <div style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: '#2F8F72' }}>{pollenCount}</div>
            <div style={{ fontSize: '0.65rem', color: '#2F8F72', fontWeight: 600 }}>{pollenLevel}</div>
            <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>(Grasses & Trees)</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.68rem' }}>
            {[
              { label: 'Air Comfort', value: airComfort, color: '#2F8F72' },
              { label: 'Outdoor Activity', value: outdoorActivity, color: '#2F8F72' },
              { label: 'Asthma Risk', value: asthmaRisk, color: '#2F8F72' },
            ].map(item => (
              <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>{item.label}</span>
                <span style={{ fontWeight: 600, color: item.color }}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* NEW: Weather AI Assistant Interactive Question & Answer Box */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '20px 24px', boxShadow: 'var(--shadow-card)', marginBottom: 'var(--space-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <MessageSquare size={16} color="#6C8FC5" />
          <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>
            Ask the Weather Agent — Conversational Intelligence
          </h3>
          <span style={{ fontSize: '0.65rem', color: '#2F8F72', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>
            ● Grounded in Live API Telemetry
          </span>
        </div>

        {/* Pre-canned prompt chips */}
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '14px' }}>
          {[
            `Is it going to rain in ${resolvedLocalityName} today?`,
            `What is the temperature in ${resolvedLocalityName} right now?`,
            `Show 7-day forecast for ${resolvedLocalityName}`,
            `Are there any storm alerts in Hyderabad?`,
            `How does weather affect traffic in ${resolvedLocalityName}?`,
          ].map((promptChip) => (
            <button
              key={promptChip}
              onClick={() => {
                setChatQuestion(promptChip)
                handleAskWeatherQuestion(promptChip)
              }}
              style={{
                fontSize: '0.68rem',
                background: 'var(--bg-workspace)',
                border: '1px solid var(--border-divider)',
                borderRadius: 'var(--radius-full)',
                padding: '4px 10px',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
              }}
            >
              {promptChip}
            </button>
          ))}
        </div>

        {/* Input Form */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: chatResponse ? '16px' : '0' }}>
          <input
            type="text"
            value={chatQuestion}
            onChange={(e) => setChatQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAskWeatherQuestion()
            }}
            placeholder={`Ask any weather question about ${resolvedLocalityName} or any location...`}
            style={{
              flex: 1,
              background: 'var(--bg-workspace)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
              padding: '10px 14px',
              color: 'var(--text-primary)',
              fontSize: '0.78rem',
              outline: 'none',
            }}
          />
          <button
            onClick={() => handleAskWeatherQuestion()}
            disabled={chatLoading || !chatQuestion.trim()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: '#6C8FC5',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              padding: '10px 18px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: chatLoading || !chatQuestion.trim() ? 'not-allowed' : 'pointer',
              opacity: chatLoading || !chatQuestion.trim() ? 0.6 : 1,
            }}
          >
            <Send size={13} />
            {chatLoading ? 'Thinking...' : 'Ask Agent'}
          </button>
        </div>

        {/* Response Card */}
        {chatResponse && (
          <div style={{ marginTop: '16px', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)', borderRadius: 'var(--radius-md)', padding: '16px' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '10px', lineHeight: 1.5 }}>
              {chatResponse.text}
            </div>
            {chatResponse.insights && chatResponse.insights.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginBottom: '10px' }}>
                {chatResponse.insights.map((insight, idx) => (
                  <div key={idx} style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ color: '#6C8FC5' }}>•</span> {insight}
                  </div>
                ))}
              </div>
            )}
            {chatResponse.suggestions && chatResponse.suggestions.length > 0 && (
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border-divider)' }}>
                {chatResponse.suggestions.map((sug, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setChatQuestion(sug)
                      handleAskWeatherQuestion(sug)
                    }}
                    style={{
                      fontSize: '0.65rem',
                      background: 'rgba(108,143,197,0.1)',
                      border: '1px solid rgba(108,143,197,0.3)',
                      borderRadius: 'var(--radius-full)',
                      padding: '3px 8px',
                      color: '#6C8FC5',
                      cursor: 'pointer',
                    }}
                  >
                    {sug}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom Cross-Domain Insight Bar */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-card)', borderRadius: 'var(--radius-lg)', padding: '16px 24px', boxShadow: 'var(--shadow-card)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <CloudSun size={18} color="#6C8FC5" />
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Cross-Domain Weather Intelligence</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '12px' }}>
              {weatherData?.correlations?.[0]?.insight ||
                `Ambient temperature (${temp}°C) and wind (${windSpeed} km/h ${windDir}) telemetry are dynamically synced with Pollution and Energy planning agents.`}
            </span>
          </div>
        </div>
        <button
          onClick={() => loadWeather(selectedLocality)}
          style={{
            padding: '8px 18px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid #6C8FC5',
            background: 'transparent',
            color: '#6C8FC5',
            fontSize: '0.72rem',
            fontWeight: 600,
            fontFamily: 'var(--font-mono)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            whiteSpace: 'nowrap',
          }}
        >
          Refresh Live Intelligence <ArrowRight size={12} />
        </button>
      </div>
    </div>
  )
}

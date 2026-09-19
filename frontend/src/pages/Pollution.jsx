import { useState, useEffect, useCallback } from 'react'
import {
  Wind, Droplets, Flame, CloudRain, Factory, Thermometer,
  AlertTriangle, ArrowRight, Info, CheckCircle2, Shield
} from 'lucide-react'
import AnimatedCounter from '../components/AnimatedCounter'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Cell, ReferenceLine
} from 'recharts'
import { pollutionApi } from '../services/api/pollutionApi'
import { invalidatePollutionCache } from '../hooks/usePollution'

/* ── Icon mapping for pollutants ── */
const pollutantIcons = {
  'PM2.5': Droplets, PM10: Wind, NO2: Factory,
  SO2: CloudRain, O3: Thermometer, CO: Flame,
}

/* ── Time range mapping ── */
const TIME_RANGE_MAP = {
  'Live': 'live', 'Latest': 'live', 'Latest Archive': 'live', '1 Hour': '1h', '6 Hours': '6h',
  '24 Hours': '24h', '7 Days': '7d', '30 Days': '30d',
}

export default function Pollution() {
  const [timeRange, setTimeRange] = useState('24 Hours')

  // Data state — all from backend, no hardcoded values
  const [current, setCurrent] = useState(null)
  const [pollutants, setPollutants] = useState([])
  const [trendData, setTrendData] = useState([])
  const [hotspots, setHotspots] = useState([])
  const [distribution, setDistribution] = useState([])
  const [areaTrends, setAreaTrends] = useState([])
  const [forecast, setForecast] = useState(null)
  const [extendedForecast, setExtendedForecast] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Fetch summary (all-in-one for initial load)
  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const summary = await pollutionApi.getSummary()
      if (summary.status === 'error') {
        setError(summary.message)
        return
      }
      if (summary.current) setCurrent(summary.current)
      if (summary.pollutants) setPollutants(summary.pollutants)
      if (summary.hotspots) setHotspots(summary.hotspots)
      if (summary.distribution) setDistribution(summary.distribution)
      if (summary.area_trends) setAreaTrends(summary.area_trends)
      if (summary.forecast) setForecast(summary.forecast)
      if (summary.extended_forecast) setExtendedForecast(summary.extended_forecast)

      // Also fetch quality info
      if (summary.quality) {
        setCurrent(prev => prev ? { ...prev, quality: summary.quality } : prev)
      }
    } catch (err) {
      setError(err.message)
    }
    setLoading(false)
  }, [])

  // Fetch trend when timeRange changes
  const fetchTrend = useCallback(async () => {
    const rangeKey = TIME_RANGE_MAP[timeRange] || '24h'
    try {
      const result = await pollutionApi.getTrend(rangeKey)
      if (result.data) setTrendData(result.data)
      else setTrendData([])
    } catch { setTrendData([]) }
  }, [timeRange])

  // Fetch alerts separately to not block main data
  const fetchAlerts = useCallback(async () => {
    try {
      const result = await pollutionApi.getAlerts()
      if (result.alerts) setAlerts(result.alerts)
    } catch { /* alerts failure is non-critical */ }
  }, [])

  useEffect(() => { fetchData(); fetchAlerts() }, [fetchData, fetchAlerts])
  useEffect(() => { fetchTrend() }, [fetchTrend])

  // Derived values with safe defaults
  const isLive = current?.is_live ?? false
  const dataMode = current?.data_mode ?? 'historical'
  const obsTimestamp = current?.timestamp || current?.observation_timestamp
  const obsDate = obsTimestamp ? new Date(obsTimestamp) : null

  const aqi = current?.aqi ?? null
  const category = current?.category ?? 'Loading...'
  const aqiColor = current?.color ?? '#999'
  const dominant = current?.dominant_pollutant ?? '--'
  const dominantValue = current?.dominant_value ?? '--'
  const quality = current?.quality ?? {}
  const stationCount = quality?.total_stations ?? 0
  const activeStations = quality?.active_stations ?? 0
  const coveragePct = quality?.coverage_percent ?? 0

  // Top pollutants (sorted by value/limit ratio)
  const topPollutants = [...pollutants]
    .sort((a, b) => (b.value / b.limit) - (a.value / a.limit))
    .slice(0, 5)

  // AQI gauge
  const aqiGaugeValue = aqi != null ? Math.min(aqi, 300) : 0
  const aqiDash = (aqiGaugeValue / 300) * 289

  // Daily stats from current
  const dailyMax = current?.daily_max ?? null
  const dailyMin = current?.daily_min ?? null
  const dailyAvg = current?.daily_avg ?? null

  const forecastTrend = (() => {
    if (!forecast || !current || forecast.forecast_aqi == null || current.aqi == null) return null
    const diff = forecast.forecast_aqi - current.aqi
    const catShift = forecast.category !== current.category
    if (Math.abs(diff) >= 3 || catShift) {
      return diff > 0 ? 'up' : 'down'
    }
    return 'stable'
  })()

  if (loading && !current) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
        Loading pollution data...
      </div>
    )
  }

  return (
    <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* ── Time Range Bar ───────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {[(isLive ? 'Live' : 'Latest'), '1 Hour', '6 Hours', '24 Hours', '7 Days', '30 Days'].map(t => (
          <button key={t} onClick={() => { setTimeRange(t); invalidatePollutionCache(`trend-${TIME_RANGE_MAP[t]}`) }} style={{
            padding: '6px 16px', borderRadius: 'var(--radius-full)',
            fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
            background: timeRange === t ? '#4C9E9B' : 'var(--bg-card)',
            color: timeRange === t ? '#fff' : 'var(--text-secondary)',
            border: timeRange === t ? 'none' : '1px solid var(--border-default)',
          }}>{t}</button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            padding: '3px 8px', borderRadius: 'var(--radius-full)',
            fontSize: '0.62rem', fontWeight: 600, fontFamily: 'var(--font-mono)',
            background: isLive ? 'rgba(47,143,114,0.15)' : 'rgba(244,166,42,0.15)',
            color: isLive ? '#2F8F72' : '#F4A62A',
            border: `1px solid ${isLive ? 'rgba(47,143,114,0.3)' : 'rgba(244,166,42,0.3)'}`,
            textTransform: 'uppercase', letterSpacing: '0.05em',
          }}>
            {isLive ? 'Live Telemetry' : 'Historical Archive'}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', borderLeft: '1px solid var(--border-default)', paddingLeft: '12px', textAlign: 'right' }}>
            {obsDate ? obsDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--'}<br />
            {obsDate ? obsDate.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) : 'No Data'}
          </div>
        </div>
      </div>

      {/* ── 1. Top Section: Current AQI Card + Hotspots ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 340px',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* Current AQI Summary Card */}
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          gap: '20px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                fontSize: '0.6rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
                background: 'rgba(47,143,114,0.12)', color: '#2F8F72',
                border: '1px solid rgba(47,143,114,0.25)', letterSpacing: '0.04em'
              }}>
                OBSERVED
              </span>
              <h3 style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                letterSpacing: '0.06em',
              }}>
                {isLive ? 'Current Air Quality Index' : 'Air Quality Index (Latest Archive)'}
              </h3>
            </div>
            <span style={{
              fontSize: '0.65rem',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
            }}>
              Hyderabad Metropolitan Average · {stationCount} Stations{isLive ? '' : ' · Historical Dataset'}
            </span>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: '150px 1fr 1fr 1fr 1fr',
            gap: '16px',
            alignItems: 'center',
          }}>
            {/* Circular AQI Gauge */}
            <div style={{ textAlign: 'center' }}>
              <div style={{ position: 'relative', width: 110, height: 110, margin: '0 auto' }}>
                <svg width="110" height="110" viewBox="0 0 110 110">
                  <circle cx="55" cy="55" r="46" fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth="8" />
                  <circle cx="55" cy="55" r="46" fill="none" stroke={aqiColor} strokeWidth="8"
                    strokeDasharray={`${aqiDash} 289`}
                    strokeLinecap="round" transform="rotate(-90 55 55)"
                    style={{ transition: 'stroke-dasharray 1s ease' }}
                  />
                </svg>
                <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <Wind size={16} color={aqiColor} strokeWidth={1.5} />
                  <span style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'var(--font-heading)', lineHeight: 1 }}>
                    {aqi != null ? <AnimatedCounter value={aqi} /> : '--'}
                  </span>
                  <span style={{ fontSize: '0.52rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{isLive ? 'CPCB AQI' : 'CPCB METHOD'}</span>
                </div>
              </div>
              <span style={{
                padding: '2px 10px', borderRadius: 'var(--radius-full)',
                fontSize: '0.6rem', fontWeight: 600,
                background: 'var(--accent-energy-dim)', color: aqiColor,
                border: `1px solid ${aqiColor}22`,
                marginTop: '6px', display: 'inline-block',
              }}>
                {category}
              </span>
            </div>

            {/* Dominant Pollutant */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                DOMINANT POLLUTANT
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-heading)' }}>
                {dominant}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#E5483F', fontWeight: 600 }}>
                {dominantValue != null && dominantValue !== '--' ? `${dominantValue} μg/m³` : '--'}
              </div>
              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Source: {isLive ? 'Live Observed' : 'TSPCB Archive'}
              </div>
            </div>

            {/* AQI Trend */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                AQI TREND ({timeRange.toUpperCase()})
              </div>
              {trendData.length >= 2 ? (() => {
                const first = trendData[0]?.aqi
                const last = trendData[trendData.length - 1]?.aqi
                if (first && last && first > 0) {
                  const changePct = Math.round((last - first) / first * 100)
                  const isUp = changePct > 0
                  return (
                    <>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ color: isUp ? '#E5483F' : '#2F8F72', fontWeight: 700, fontSize: '1.2rem', fontFamily: 'var(--font-heading)' }}>
                          {isUp ? '▲' : '▼'} {Math.abs(changePct)}%
                        </span>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                        vs period start
                      </div>
                    </>
                  )
                }
                return <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Insufficient data</div>
              })() : <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Loading...</div>}
            </div>

            {/* Sensitive Groups */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                SENSITIVE GROUPS
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                {aqi != null && aqi > 100 ? (
                  <>
                    <AlertTriangle size={14} color="#F4A62A" />
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                      {aqi > 200 ? 'Avoid Outdoors' : 'Limit Exertion'}
                    </span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={14} color="#2F8F72" />
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                      Low Risk
                    </span>
                  </>
                )}
              </div>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '4px', lineHeight: 1.3 }}>
                {aqi != null && aqi > 100 ? 'Limit strenuous outdoor activity' : 'No restrictions needed'}
              </div>
            </div>

            {/* Data Coverage */}
            <div style={{ padding: '0 8px', borderLeft: '1px solid var(--border-divider)' }}>
              <div style={{ fontSize: '0.6rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px' }}>
                DATA COVERAGE
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px' }}>
                <span style={{ fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: coveragePct >= 80 ? '#2F8F72' : '#F4A62A' }}>
                  {coveragePct > 0 ? `${Math.round(coveragePct)}%` : '--'}
                </span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                {activeStations}/{stationCount} Stations
              </div>
              <div style={{ fontSize: '0.58rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                {quality?.status === 'good' ? 'Coverage Good' : quality?.status === 'degraded' ? 'Coverage Degraded' : 'Data Status'}
              </div>
            </div>
          </div>

          {/* Daily Quick Stats Row */}
          <div style={{
            display: 'flex',
            gap: '24px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-divider)',
            fontSize: '0.72rem',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Daily Max:</span>
              <span style={{ fontWeight: 700, color: '#E5483F', fontFamily: 'var(--font-mono)' }}>
                {dailyMax != null ? `${dailyMax} AQI` : '--'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Daily Min:</span>
              <span style={{ fontWeight: 700, color: '#2F8F72', fontFamily: 'var(--font-mono)' }}>
                {dailyMin != null ? `${dailyMin} AQI` : '--'}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Daily Average:</span>
              <span style={{ fontWeight: 700, color: '#F4A62A', fontFamily: 'var(--font-mono)' }}>
                {dailyAvg != null ? `${dailyAvg} AQI` : '--'}
              </span>
              {dailyAvg != null && (
                <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)' }}>
                  ({aqi != null && aqi <= 50 ? 'Good' : aqi != null && aqi <= 100 ? 'Satisfactory' : aqi != null && aqi <= 200 ? 'Moderate' : category})
                </span>
              )}
            </div>
          </div>
        </div>

        {/* AQI Hotspots Card */}
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              AQI Hotspots (Current)
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', cursor: 'pointer' }}>
              VIEW ALL
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
            {hotspots.length > 0 ? hotspots.map((h, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '7px 10px', borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
              }}>
                <div style={{ width: 36, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.95rem', fontWeight: 700, color: h.color, fontFamily: 'var(--font-heading)', lineHeight: 1.1 }}>{h.aqi}</div>
                  <div style={{ fontSize: '0.48rem', color: h.color, fontWeight: 600 }}>{h.category}</div>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {h.area}
                  </div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {h.dominant_pollutant}: {h.pm25 != null ? `${Math.round(h.pm25)} μg/m³` : '--'}
                  </div>
                </div>
              </div>
            )) : (
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
                No hotspot data available
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── 2. Middle Row: Trend + Pollutant Grid + Top Pollutants ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.2fr 1.3fr 280px',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* AQI Trend Chart */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              AQI Trend ({timeRange})
            </h3>
            <Info size={12} color="var(--text-muted)" />
          </div>
          {trendData.length > 0 ? (
            <ResponsiveContainer width="100%" height={210}>
              <AreaChart data={trendData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="aqiAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#F4A62A" stopOpacity={0.18} />
                    <stop offset="100%" stopColor="#F4A62A" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#8F9295' }} interval="preserveStartEnd" axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 8, fill: '#8F9295' }} axisLine={false} tickLine={false} domain={[0, 'auto']} />
                <ReferenceLine y={50} stroke="rgba(47,143,114,0.3)" strokeDasharray="3 3" />
                <ReferenceLine y={100} stroke="rgba(244,166,42,0.3)" strokeDasharray="3 3" />
                <ReferenceLine y={150} stroke="rgba(229,72,63,0.3)" strokeDasharray="3 3" />
                <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border-default)', borderRadius: 8, fontSize: '0.7rem', boxShadow: 'var(--shadow-elevated)' }} />
                <Area type="monotone" dataKey="aqi" stroke="#F4A62A" strokeWidth={1.5} fill="url(#aqiAreaGrad)" name="CPCB AQI" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 210, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              No trend data for selected range
            </div>
          )}
        </div>

        {/* Pollutant Concentration Grid */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Pollutant Concentration (Current)
            </h3>
            <Info size={12} color="var(--text-muted)" />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
            {pollutants.length > 0 ? pollutants.map((p) => {
              const Icon = pollutantIcons[p.name] || Wind
              const overLimit = p.value > p.limit
              return (
                <div key={p.name} style={{
                  padding: '10px', borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)',
                  textAlign: 'center',
                }}>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '2px' }}>{p.name}</div>
                  <div style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-heading)' }}>{p.value}</div>
                  <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>{p.unit}</div>
                  <div style={{ fontSize: '0.55rem', color: overLimit ? '#E5483F' : '#2F8F72', fontWeight: 600, marginTop: '2px' }}>
                    {Math.round(p.pct_of_limit)}% of limit
                  </div>
                </div>
              )
            }) : (
              <div style={{ gridColumn: '1 / -1', textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', padding: '20px' }}>
                No pollutant data available
              </div>
            )}
          </div>
        </div>

        {/* Top Pollutants Breakdown */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Top Pollutants (Observed)
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {topPollutants.map(p => (
              <div key={p.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontSize: '0.72rem', fontWeight: 500, color: 'var(--text-primary)' }}>{p.name}</span>
                  <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{p.value} {p.unit}</span>
                </div>
                <div style={{ height: 5, borderRadius: 3, background: 'var(--bg-workspace)', overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.min(p.pct_of_limit || (p.value / p.limit * 100), 100)}%`, height: '100%', borderRadius: 3,
                    background: (p.pct_of_limit || p.value / p.limit * 100) > 80 ? '#E5483F' : '#4C9E9B',
                    transition: 'width 1s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── 3. Forecast Section ── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        boxShadow: 'var(--shadow-card)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                padding: '2px 8px', borderRadius: 'var(--radius-full)',
                fontSize: '0.6rem', fontWeight: 700, fontFamily: 'var(--font-mono)',
                background: 'rgba(107,70,193,0.12)', color: '#6B46C1',
                border: '1px solid rgba(107,70,193,0.25)', letterSpacing: '0.04em'
              }}>
                PREDICTED
              </span>
              <h3 style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
                Next-Day Air Quality Forecast
              </h3>
            </div>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Unified spatial-temporal AQI forecast for Hyderabad (1-day model horizon).
            </p>
          </div>
          <span style={{ fontSize: '0.65rem', color: '#4C9E9B', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
            {forecast?.forecast_status === 'success' ? 'Model: Ready' : 'Model: Unavailable'}
          </span>
        </div>

        {forecast?.forecast_status === 'success' ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px', padding: '16px', background: 'var(--bg-workspace)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-divider)' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '4px' }}>NEXT-DAY FORECAST</div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                <div style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'var(--font-heading)', color: (() => {
                  const fAqi = forecast.forecast_aqi
                  if (fAqi <= 50) return '#2F8F72'
                  if (fAqi <= 100) return '#6BBF59'
                  if (fAqi <= 200) return '#F4A62A'
                  if (fAqi <= 300) return '#E5483F'
                  return '#8B0000'
                })() }}>
                  {forecast.forecast_aqi}
                </div>
                {forecastTrend && (
                  <span style={{ fontSize: '1.2rem', color: forecastTrend === 'up' ? '#E5483F' : forecastTrend === 'down' ? '#2F8F72' : 'var(--text-muted)' }} title={forecastTrend === 'up' ? 'Rising Trend' : forecastTrend === 'down' ? 'Falling Trend' : 'Stable'}>
                    {forecastTrend === 'up' ? '▲' : forecastTrend === 'down' ? '▼' : '−'}
                  </span>
                )}
              </div>
              <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>AQI (Unified Model)</div>
            </div>
            <div style={{ flex: 1, fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <div style={{ marginBottom: '4px' }}>
                <strong>Source:</strong> Unified Model: {forecast.model_name || 'Temporal GRU'} ({forecast.sequence_days}-day input sequence)
              </div>
              <div style={{ marginBottom: '4px' }}>
                <strong>Horizon:</strong> {forecast.forecast_horizon} {forecast.display_date ? `(${forecast.display_date})` : forecast.forecast_date ? `(Target: ${forecast.forecast_date})` : ''}
              </div>
              <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                Validated empirical forecast derived from TSPCB ambient observations.
              </div>
            </div>
          </div>
        ) : (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem', background: 'var(--bg-workspace)', borderRadius: 'var(--radius-md)' }}>
            {forecast?.reason || 'Forecast unavailable'}
          </div>
        )}

        {/* Extended forecast (7-Day Multi-Horizon) */}
        <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-divider)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              EXTENDED FORECAST (7-DAY MULTI-HORIZON)
            </div>
            {extendedForecast?.status === 'success' && (
              <span style={{ fontSize: '0.62rem', color: '#4C9E9B', fontFamily: 'var(--font-mono)' }}>
                Model: {extendedForecast.architecture || 'Unified Forecaster'} · Origin: {extendedForecast.forecast_origin_date}
              </span>
            )}
          </div>

          {extendedForecast?.status === 'success' && extendedForecast?.forecast?.length > 0 ? (
            <div>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '10px',
              }}>
                {extendedForecast.forecast.map((d) => {
                  const targetDt = d.target_date ? new Date(d.target_date + 'T00:00:00') : null
                  const dateStr = d.display_date || (targetDt && !isNaN(targetDt.getTime())
                    ? targetDt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', weekday: 'short' })
                    : `Day ${d.horizon_days}`)

                  return (
                    <div key={d.horizon_days} style={{
                      padding: '12px 10px',
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--bg-workspace)',
                      border: '1px solid var(--border-divider)',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      textAlign: 'center',
                      transition: 'transform 0.15s ease',
                    }}>
                      <div style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', marginBottom: '2px' }}>
                        {dateStr}
                      </div>
                      <div style={{ fontSize: '0.55rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '6px' }}>
                        HORIZON +{d.horizon_days}D
                      </div>
                      <div style={{
                        fontSize: '1.5rem',
                        fontWeight: 700,
                        fontFamily: 'var(--font-heading)',
                        color: d.color || '#F4A62A',
                        lineHeight: 1.1,
                      }}>
                        {d.aqi}
                      </div>
                      <div style={{
                        fontSize: '0.55rem',
                        fontWeight: 600,
                        color: d.color || '#F4A62A',
                        marginTop: '2px',
                        marginBottom: '8px',
                      }}>
                        {d.category}
                      </div>
                      <div style={{
                        width: '100%',
                        paddingTop: '6px',
                        borderTop: '1px solid var(--border-divider)',
                        fontSize: '0.58rem',
                        color: 'var(--text-muted)',
                        fontFamily: 'var(--font-mono)',
                        lineHeight: 1.4,
                      }}>
                        <div>Dom: <strong style={{ color: 'var(--text-primary)' }}>{d.dominant_pollutant}</strong></div>
                        <div>PM2.5: {d.pollutants?.['PM2.5'] != null ? Math.round(d.pollutants['PM2.5']) : '--'}</div>
                        <div>PM10: {d.pollutants?.['PM10'] != null ? Math.round(d.pollutants['PM10']) : '--'}</div>
                      </div>
                    </div>
                  )
                })}
              </div>
              <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                <span>Provenance: TSPCB CAAQMS (2024–2025) → {extendedForecast.architecture || 'GRU'} → CPCB AQI Engine</span>
                <span>Uncertainty: ±{extendedForecast?.uncertainty?.overall_aqi_mae || 12.25} AQI (90% conf.)</span>
              </div>
            </div>
          ) : (
            <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.7rem', background: 'var(--bg-workspace)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-divider)' }}>
              {extendedForecast?.reason || 'The 7-day multi-horizon forecasting pipeline is unavailable.'}
            </div>
          )}
        </div>
      </div>

      {/* ── 4. Lower Row: Distribution + Trend vs Yesterday + Alerts ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.1fr 1.1fr 1.2fr',
        gap: 'var(--space-lg)',
        alignItems: 'stretch',
      }}>
        {/* AQI Distribution */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>
            AQI Distribution (City)
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ position: 'relative', width: 100, height: 100 }}>
              <svg width="100" height="100" viewBox="0 0 100 100">
                {(() => {
                  const r = 38; const c = 2 * Math.PI * r; let off = 0;
                  const totalVal = distribution.reduce((s, d) => s + d.value, 0)
                  if (totalVal === 0) return <circle cx="50" cy="50" r={r} fill="none" stroke="#eee" strokeWidth="12" />
                  return distribution.filter(d => d.value > 0).map(d => {
                    const pct = d.value / totalVal * 100
                    const dash = (pct / 100) * c; const o = -off; off += dash;
                    return <circle key={d.name} cx="50" cy="50" r={r} fill="none" stroke={d.color} strokeWidth="12" strokeDasharray={`${dash} ${c - dash}`} strokeDashoffset={o} transform="rotate(-90 50 50)" />
                  })
                })()}
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, fontFamily: 'var(--font-heading)' }}>{stationCount}</span>
                <span style={{ fontSize: '0.5rem', color: 'var(--text-muted)' }}>Stations</span>
              </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.62rem' }}>
              {distribution.map(d => (
                <div key={d.name} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: d.color }} />
                  <span style={{ color: 'var(--text-secondary)' }}>{d.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginLeft: 'auto' }}>{d.value} ({d.pct}%)</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AQI Trend vs Yesterday */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '14px' }}>
            AQI Trend vs Yesterday (By Area)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {areaTrends.length > 0 ? areaTrends.slice(0, 6).map(t => (
              <div key={t.area} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-primary)', width: '90px', fontWeight: 500 }}>{t.area}</span>
                <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--bg-workspace)', overflow: 'hidden', display: 'flex', justifyContent: t.dir === 'up' ? 'flex-end' : 'flex-start' }}>
                  <div style={{ width: `${Math.min(t.change * 3, 100)}%`, height: '100%', borderRadius: 3, background: t.dir === 'up' ? '#E5483F' : '#2F8F72' }} />
                </div>
                <span style={{ fontSize: '0.6rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: t.dir === 'up' ? '#E5483F' : '#2F8F72', width: '40px', textAlign: 'right' }}>
                  {t.dir === 'up' ? '▲' : '▼'} {Math.round(t.change)}%
                </span>
              </div>
            )) : (
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
                No trend data available
              </div>
            )}
          </div>
        </div>

        {/* Alerts & Advisories */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)', padding: '20px', boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.8rem', fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em' }}>
              Alerts & Advisories
            </h3>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>VIEW ALL</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {alerts.length > 0 ? alerts.slice(0, 3).map((a, i) => (
              <div key={i} style={{ display: 'flex', gap: '8px', padding: '9px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-workspace)', border: '1px solid var(--border-divider)' }}>
                <AlertTriangle size={15} color={a.color} style={{ flexShrink: 0, marginTop: '2px' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.7rem', fontWeight: 600, color: a.color }}>{a.type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>{a.message}</div>
                </div>
                <div style={{ fontSize: '0.52rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>{a.severity}</div>
              </div>
            )) : (
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
                No active alerts
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── 5. Bottom Insight Bar ─────────────────────────── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '16px 24px',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Wind size={16} color="#4C9E9B" />
          <div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>Air Quality Tip</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginLeft: '12px' }}>
              Consider using public transport and carpooling to reduce emissions and improve air quality.
            </span>
          </div>
        </div>
        <button style={{
          padding: '8px 18px', borderRadius: 'var(--radius-md)',
          border: '1px solid #4C9E9B', background: 'transparent',
          color: '#4C9E9B', fontSize: '0.72rem', fontWeight: 600,
          fontFamily: 'var(--font-mono)', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: '6px', whiteSpace: 'nowrap',
        }}>
          View Recommendations <ArrowRight size={12} />
        </button>
      </div>
    </div>
  )
}

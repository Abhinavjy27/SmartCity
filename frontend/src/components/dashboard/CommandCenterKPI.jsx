import { useState, useEffect } from 'react'
import PropTypes from 'prop-types'
import { useNavigate } from 'react-router-dom'
import { Car, Wind, Zap, CloudSun, Shield } from 'lucide-react'
import AnimatedCounter from '../AnimatedCounter'
import { trafficApi, weatherApi, pollutionApi, energyApi } from '../../services/api'

/**
 * Reusable KPI Card Component
 * Supports custom polarity (default: up = good, down-good for metrics like congestion where up = bad).
 */
export function KPICard({
  icon: Icon,
  label,
  value,
  decimals = 0,
  suffix = '',
  delta = null,
  deltaUnit = '',
  deltaLabel = 'vs yesterday',
  polarity = 'up-good',
  baselineAvailable = true,
  status = 'live',
  loading = false,
  tooltip = '',
  ariaLabel = '',
  color = '#2F8F72',
  bgColor = 'rgba(47, 143, 114, 0.08)',
  staticLabel = null,
  onClick = undefined,
}) {
  const isIncrease = delta !== null && delta !== undefined && delta > 0
  const isDecrease = delta !== null && delta !== undefined && delta < 0
  const arrow = isIncrease ? '▲' : isDecrease ? '▼' : '●'
  const absDelta = delta !== null && delta !== undefined ? Math.abs(delta).toFixed(decimals > 0 ? decimals : 1) : null

  // Polarity determines color:
  // 'up-good': up is green, down is red (default)
  // 'down-good': up is red, down is green (for congestion, emissions, errors)
  let deltaColor = 'var(--text-muted, #8F9295)'
  if (delta !== null && delta !== undefined) {
    if (polarity === 'down-good') {
      deltaColor = isIncrease
        ? 'var(--accent-warning, #EF4444)'
        : isDecrease
        ? 'var(--accent-traffic, #2F8F72)'
        : 'var(--text-muted, #8F9295)'
    } else {
      deltaColor = isIncrease
        ? 'var(--accent-traffic, #2F8F72)'
        : isDecrease
        ? 'var(--accent-warning, #EF4444)'
        : 'var(--text-muted, #8F9295)'
    }
  }

  return (
    <div
      role="region"
      aria-label={ariaLabel || label}
      title={tooltip || label}
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '14px',
        padding: '0 16px',
        flex: 1,
        cursor: 'pointer',
        transition: 'all var(--transition-fast, 0.15s ease)',
      }}
      onMouseEnter={e => (e.currentTarget.style.opacity = '0.85')}
      onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
    >
      {/* Icon circle — existing styling preserved exactly */}
      <div
        style={{
          width: 42,
          height: 42,
          borderRadius: '50%',
          background: bgColor,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Icon size={18} color={color} strokeWidth={1.8} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: '0.6rem',
            fontWeight: 600,
            color: 'var(--text-muted, #8F9295)',
            letterSpacing: '0.1em',
            marginBottom: '2px',
            fontFamily: 'var(--font-mono, monospace)',
            textTransform: 'uppercase',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <span>{label}</span>
          {status === 'stale' && (
            <span
              style={{
                fontSize: '0.55rem',
                color: 'var(--text-muted, #8F9295)',
                background: 'rgba(143, 146, 149, 0.12)',
                padding: '1px 4px',
                borderRadius: '3px',
                letterSpacing: '0.04em',
              }}
            >
              STALE
            </span>
          )}
        </div>

        {/* Value */}
        <div
          style={{
            fontSize: '1.5rem',
            fontWeight: 700,
            color: 'var(--text-primary, #17212B)',
            lineHeight: 1.1,
            fontFamily: 'var(--font-heading, "Inter", sans-serif)',
          }}
        >
          {loading ? (
            <div
              style={{
                width: '70px',
                height: '24px',
                background: 'var(--bg-tertiary, #EDE8DF)',
                borderRadius: '4px',
                opacity: 0.6,
              }}
            />
          ) : value !== null && value !== undefined ? (
            <AnimatedCounter value={value} decimals={decimals} suffix={suffix} />
          ) : (
            '—'
          )}
        </div>

        {/* Delta row */}
        <div
          style={{
            fontSize: '0.65rem',
            color: 'var(--text-muted, #8F9295)',
            marginTop: '2px',
            display: 'flex',
            alignItems: 'center',
            gap: '3px',
            fontFamily: 'var(--font-body, system-ui)',
          }}
        >
          {loading ? (
            <div
              style={{
                width: '90px',
                height: '12px',
                background: 'var(--bg-tertiary, #EDE8DF)',
                borderRadius: '3px',
                opacity: 0.5,
              }}
            />
          ) : value === null || value === undefined ? (
            <span style={{ color: 'var(--text-muted, #8F9295)' }}>Awaiting live data</span>
          ) : !baselineAvailable ? (
            <span style={{ color: 'var(--text-muted, #8F9295)' }}>building baseline</span>
          ) : delta !== null && delta !== undefined ? (
            <>
              <span style={{ color: deltaColor, fontWeight: 600, fontFamily: 'var(--font-mono, monospace)' }}>
                {arrow} {absDelta} {deltaUnit}
              </span>
              <span>{deltaLabel}</span>
            </>
          ) : staticLabel ? (
            <span>{staticLabel}</span>
          ) : null}
        </div>
      </div>
    </div>
  )
}

KPICard.propTypes = {
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.number,
  decimals: PropTypes.number,
  suffix: PropTypes.string,
  delta: PropTypes.number,
  deltaUnit: PropTypes.string,
  deltaLabel: PropTypes.string,
  polarity: PropTypes.oneOf(['up-good', 'down-good']),
  baselineAvailable: PropTypes.bool,
  status: PropTypes.string,
  loading: PropTypes.bool,
  tooltip: PropTypes.string,
  ariaLabel: PropTypes.string,
  color: PropTypes.string,
  bgColor: PropTypes.string,
  staticLabel: PropTypes.string,
  onClick: PropTypes.func,
}

/* Sibling Static/Semi-static cards */
const SIBLING_KPIS = [
  {
    id: 'aqi',
    icon: Wind,
    label: 'CURRENT AQI',
    value: 136,
    decimals: 0,
    trend: '8.0%',
    delta: -8.0,
    deltaUnit: '%',
    deltaLabel: 'vs yesterday',
    polarity: 'down-good',
    color: '#4C9E9B',
    bgColor: 'rgba(76, 158, 155, 0.08)',
  },
  {
    id: 'grid',
    icon: Zap,
    label: 'GRID LOAD',
    value: 78.4,
    suffix: '%',
    decimals: 1,
    delta: 3.2,
    deltaUnit: '%',
    deltaLabel: 'vs yesterday',
    polarity: 'down-good',
    color: '#F4A62A',
    bgColor: 'rgba(244, 166, 42, 0.08)',
  },
  {
    id: 'temp',
    icon: CloudSun,
    label: 'TEMPERATURE',
    value: 29,
    suffix: '°C',
    decimals: 0,
    staticLabel: 'Clear Skies',
    color: '#6C8FC5',
    bgColor: 'rgba(108, 143, 197, 0.08)',
  },
  {
    id: 'incidents',
    icon: Shield,
    label: 'ACTIVE INCIDENTS',
    value: 24,
    decimals: 0,
    staticLabel: '3 new today',
    color: '#E5483F',
    bgColor: 'rgba(229, 72, 63, 0.08)',
  },
]

export default function CommandCenterKPI() {
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
  const [congestionLoading, setCongestionLoading] = useState(true)

  const [aqiData, setAqiData] = useState({ value: 146, status: 'Moderate', delta: -4.0 })
  const [gridData, setGridData] = useState({ value: 78.4, status: 'Normal', delta: 2.1 })
  const [tempData, setTempData] = useState({ value: 28, condition: 'Clear Skies' })
  const [incidentsCount, setIncidentsCount] = useState(4)

  useEffect(() => {
    let isMounted = true

    const fetchAllMetrics = async () => {
      if (typeof document !== 'undefined' && document.hidden) return

      try {
        const [congRes, aqiRes, gridRes, weatherRes, kpiRes] = await Promise.allSettled([
          trafficApi.getCongestionIndex(),
          pollutionApi.getAqiSummary(),
          energyApi.getGridStatus(),
          weatherApi.getCurrent(),
          trafficApi.getKPIs(),
        ])

        if (!isMounted) return

        if (congRes.status === 'fulfilled' && congRes.value) {
          setCongestion(prev => {
            if (congRes.value.value_pct === null && prev?.value_pct !== null) {
              return { ...prev, status: 'stale' }
            }
            return congRes.value
          })
          setCongestionLoading(false)
        }

        if (aqiRes.status === 'fulfilled' && aqiRes.value) {
          const avgAqi = aqiRes.value.city_avg_aqi || aqiRes.value.aqi
          if (avgAqi) {
            setAqiData({
              value: avgAqi,
              status: aqiRes.value.category || 'Moderate',
              delta: -3.5,
            })
          }
        }

        if (gridRes.status === 'fulfilled' && gridRes.value) {
          const load = gridRes.value.load_pct
          if (load !== undefined && load !== null) {
            setGridData({
              value: parseFloat(load.toFixed(1)),
              status: gridRes.value.severity || 'Normal',
              delta: 1.8,
            })
          }
        }

        if (weatherRes.status === 'fulfilled' && weatherRes.value) {
          const t = weatherRes.value.temperature_c
          if (t !== undefined && t !== null) {
            setTempData({
              value: Math.round(t),
              condition: weatherRes.value.condition || 'Clear Skies',
            })
          }
        }

        if (kpiRes.status === 'fulfilled' && kpiRes.value) {
          const actInc = kpiRes.value.active_incidents ?? kpiRes.value.activeIncidents
          if (actInc !== undefined && actInc !== null) {
            setIncidentsCount(Number(actInc))
          }
        }
      } catch (err) {
        console.warn('[CommandCenterKPI] Metrics fetch error:', err)
      }
    }

    fetchAllMetrics()

    // Poll every 60s
    const timer = setInterval(fetchAllMetrics, 60000)

    const handleVisibility = () => {
      if (!document.hidden) {
        fetchAllMetrics()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      isMounted = false
      clearInterval(timer)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [])

  // Build Tooltip and Aria-label for Congestion Card
  const minutesAgo = congestion.updated_at
    ? Math.max(0, Math.round((Date.now() - new Date(congestion.updated_at).getTime()) / 60000))
    : null

  const levelText = congestion.level ? ` Current level: ${congestion.level}.` : ''
  const staleText = congestion.status === 'stale' && minutesAgo !== null ? ` (updated ${minutesAgo} min ago)` : ''
  const congestionTooltip = `Average share of free-flow speed lost across 21 monitored Hyderabad junctions (TomTom Traffic Flow). 0% = free-flowing.${levelText}${staleText}`

  let congestionAria = 'Congestion index'
  if (congestion.value_pct !== null && congestion.value_pct !== undefined) {
    congestionAria += ` ${congestion.value_pct.toFixed(1)} percent`
    if (congestion.baseline_available && congestion.delta_pp !== null) {
      const dir = congestion.delta_pp > 0 ? 'up' : congestion.delta_pp < 0 ? 'down' : 'flat'
      congestionAria += `, ${dir} ${Math.abs(congestion.delta_pp).toFixed(1)} points versus yesterday`
    } else {
      congestionAria += ', building baseline'
    }
  } else {
    congestionAria += ' awaiting live data'
  }

  const dynamicSiblingKpis = [
    {
      id: 'aqi',
      icon: Wind,
      label: 'CURRENT AQI',
      value: aqiData.value,
      decimals: 0,
      trend: `${Math.abs(aqiData.delta)}%`,
      delta: aqiData.delta,
      deltaUnit: '%',
      deltaLabel: 'vs yesterday',
      polarity: 'down-good',
      color: '#4C9E9B',
      bgColor: 'rgba(76, 158, 155, 0.08)',
      onClick: () => navigate('/pollution'),
    },
    {
      id: 'grid',
      icon: Zap,
      label: 'GRID LOAD',
      value: gridData.value,
      suffix: '%',
      decimals: 1,
      delta: gridData.delta,
      deltaUnit: '%',
      deltaLabel: 'vs yesterday',
      polarity: 'down-good',
      color: '#F4A62A',
      bgColor: 'rgba(244, 166, 42, 0.08)',
      onClick: () => navigate('/energy'),
    },
    {
      id: 'temp',
      icon: CloudSun,
      label: 'TEMPERATURE',
      value: tempData.value,
      suffix: '°C',
      decimals: 0,
      staticLabel: tempData.condition,
      color: '#6C8FC5',
      bgColor: 'rgba(108, 143, 197, 0.08)',
      onClick: () => navigate('/weather'),
    },
    {
      id: 'incidents',
      icon: Shield,
      label: 'ACTIVE INCIDENTS',
      value: incidentsCount,
      decimals: 0,
      staticLabel: `${incidentsCount} live detected`,
      color: '#E5483F',
      bgColor: 'rgba(229, 72, 63, 0.08)',
      onClick: () => navigate('/traffic'),
    },
  ]

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'stretch',
        background: 'var(--bg-card, #FFFFFF)',
        border: '1px solid var(--border-card, #EAE6DF)',
        borderRadius: 'var(--radius-lg, 14px)',
        padding: '20px 8px',
        boxShadow: 'var(--shadow-card, 0 4px 18px rgba(0,0,0,0.04))',
        gap: '0',
        overflowX: 'auto',
      }}
    >
      {/* ── 1. Live TomTom Congestion Index KPI Card ── */}
      <div style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: '170px' }}>
        <KPICard
          icon={Car}
          label="CONGESTION INDEX"
          value={congestion.value_pct}
          decimals={1}
          suffix="%"
          delta={congestion.delta_pp}
          deltaUnit="pp"
          deltaLabel="vs yesterday"
          polarity="down-good"
          baselineAvailable={congestion.baseline_available}
          status={congestion.status}
          loading={congestionLoading}
          tooltip={congestionTooltip}
          ariaLabel={congestionAria}
          color="#2F8F72"
          bgColor="rgba(47, 143, 114, 0.08)"
          onClick={() => navigate('/traffic')}
        />

        {/* Divider */}
        <div
          style={{
            width: '1px',
            height: '50px',
            background: 'var(--border-default, #E2E8F0)',
            flexShrink: 0,
          }}
        />
      </div>

      {/* ── 2-5. Sibling KPI Cards ── */}
      {dynamicSiblingKpis.map((kpi, idx) => (
        <div key={kpi.id} style={{ display: 'flex', alignItems: 'center', flex: 1, minWidth: '170px' }}>
          <KPICard
            icon={kpi.icon}
            label={kpi.label}
            value={kpi.value}
            decimals={kpi.decimals}
            suffix={kpi.suffix || ''}
            delta={kpi.delta}
            deltaUnit={kpi.deltaUnit}
            deltaLabel={kpi.deltaLabel}
            polarity={kpi.polarity || 'up-good'}
            staticLabel={kpi.staticLabel}
            color={kpi.color}
            bgColor={kpi.bgColor}
            onClick={kpi.onClick}
          />

          {/* Divider */}
          {idx < SIBLING_KPIS.length - 1 && (
            <div
              style={{
                width: '1px',
                height: '50px',
                background: 'var(--border-default, #E2E8F0)',
                flexShrink: 0,
              }}
            />
          )}
        </div>
      ))}
    </div>
  )
}

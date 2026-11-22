import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import CommandCenterKPI from '../components/dashboard/CommandCenterKPI'
import DigitalTwinMap from '../components/dashboard/DigitalTwinMap'
import TrafficFlowCard from '../components/dashboard/TrafficFlowCard'
import AQITrendCard from '../components/dashboard/AQITrendCard'
import EnergyCard from '../components/dashboard/EnergyCard'
import WeatherCard from '../components/dashboard/WeatherCard'

export default function Dashboard() {
  const [timeRange, setTimeRange] = useState('24 HOURS')
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const timeRangeOptions = ['1 HOUR', '6 HOURS', '24 HOURS', '7 DAYS']

  return (
    <div className="stagger-children">
      {/* KPI Strip */}
      <CommandCenterKPI />

      {/* City Digital Twin */}
      <div style={{ marginTop: 'var(--space-lg)' }}>
        <DigitalTwinMap />
      </div>

      {/* Live City Metrics Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginTop: 'var(--space-2xl)', marginBottom: 'var(--space-lg)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2 style={{
            fontSize: '0.9rem', fontWeight: 700, letterSpacing: '0.08em',
            fontFamily: 'var(--font-mono)', color: 'var(--text-primary)',
            textTransform: 'uppercase',
          }}>
            LIVE CITY METRICS
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div className="live-dot" />
            <span style={{
              fontSize: '0.7rem', fontWeight: 600, color: 'var(--accent-traffic)',
              fontFamily: 'var(--font-mono)',
            }}>Live</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', position: 'relative' }}>
          <span style={{
            fontSize: '0.65rem', color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', fontWeight: 600,
          }}>TIME RANGE</span>
          <button
            onClick={() => setDropdownOpen(prev => !prev)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '6px 14px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.7rem', fontWeight: 600,
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              letterSpacing: '0.04em',
            }}
          >
            {timeRange}
            <ChevronDown size={12} color="var(--text-muted)" style={{ transform: dropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
          </button>

          {dropdownOpen && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                right: 0,
                marginTop: '4px',
                background: 'var(--bg-card)',
                border: '1px solid var(--border-card)',
                borderRadius: 'var(--radius-sm)',
                boxShadow: 'var(--shadow-elevated)',
                zIndex: 50,
                minWidth: '120px',
                overflow: 'hidden',
              }}
            >
              {timeRangeOptions.map((opt) => (
                <div
                  key={opt}
                  onClick={() => {
                    setTimeRange(opt)
                    setDropdownOpen(false)
                  }}
                  style={{
                    padding: '8px 12px',
                    fontSize: '0.68rem',
                    fontWeight: 600,
                    fontFamily: 'var(--font-mono)',
                    color: timeRange === opt ? '#2F8F72' : 'var(--text-primary)',
                    background: timeRange === opt ? 'rgba(47, 143, 114, 0.08)' : 'transparent',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                  }}
                  onMouseEnter={e => {
                    if (timeRange !== opt) e.currentTarget.style.background = 'var(--bg-tertiary, #f4f2ee)'
                  }}
                  onMouseLeave={e => {
                    if (timeRange !== opt) e.currentTarget.style.background = 'transparent'
                  }}
                >
                  {opt}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Vertically Stacked Metric Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
        <TrafficFlowCard timeRange={timeRange} />
        <AQITrendCard timeRange={timeRange} />
        <EnergyCard timeRange={timeRange} />
        <WeatherCard timeRange={timeRange} />
      </div>
    </div>
  )
}

import { useState } from 'react'
import {
  AlertTriangle, Brain, CheckCircle2, Zap, ArrowRight, ShieldCheck,
  TrendingDown, Sparkles, Filter, RefreshCw, Cpu
} from 'lucide-react'
import GlassCard from './GlassCard'
import StatusBadge from './StatusBadge'

export const urbanProblems = [
  {
    id: 'PROB_01',
    title: 'Evening Traffic Gridlock at Gachibowli Flyover & Mindspace Corridor',
    domain: 'Traffic & Mobility',
    location: 'Gachibowli — HITECH City',
    severity: 'CRITICAL',
    metrics: { 'Avg Speed': '15.2 km/h', 'Occupancy': '91.3%', 'Avg Delay': '142 sec' },
    description: 'Severe bottleneck causing 3.4 km vehicle queues during peak evening office rush.',
    suggestions: [
      {
        id: 'SUGG_1_1',
        title: 'AI Adaptive Signal Phase Extension',
        agent: 'Traffic Agent',
        agentColor: 'cyan',
        mechanism: 'Increase green light phase by +25s on heavy ingress corridors and adjust cycle times dynamically.',
        predictedImpact: '-34% Queue Length | +12.5 km/h Avg Speed',
        confidence: 95,
        timeToEffect: '2 mins',
        tag: 'Recommended'
      },
      {
        id: 'SUGG_1_2',
        title: 'Dynamic Route Divergence via Financial District Bypass',
        agent: 'Routing AI',
        agentColor: 'violet',
        mechanism: 'Broadcast real-time rerouting alerts to VMS road signs & GPS mapping apps.',
        predictedImpact: '-22% Traffic Volume on Main Flyover',
        confidence: 89,
        timeToEffect: '5 mins',
        tag: 'Route Diversion'
      },
      {
        id: 'SUGG_1_3',
        title: 'Metro & Express Feeder Shuttle Priority Dispatch',
        agent: 'Public Transit AI',
        agentColor: 'emerald',
        mechanism: 'Increase Ameerpet-Mindspace Metro frequency to 3-min intervals and deploy express EV feeders.',
        predictedImpact: '-18% Private Vehicle Commutes',
        confidence: 92,
        timeToEffect: '10 mins',
        tag: 'Public Transit'
      },
      {
        id: 'SUGG_1_4',
        title: 'Dynamic Reversible Lane Activation',
        agent: 'Infrastructure AI',
        agentColor: 'amber',
        mechanism: 'Lower automated bollards on Bio-Diversity stretch to convert counter-flow lane into ingress route.',
        predictedImpact: '+40% Corridor Flow Throughput',
        confidence: 87,
        timeToEffect: '4 mins',
        tag: 'Infrastructure'
      }
    ]
  },
  {
    id: 'PROB_02',
    title: 'Severe Particulate Air Pollution Spike (PM2.5 / PM10) in Nacharam & Sanathnagar',
    domain: 'Air Quality & Environment',
    location: 'Nacharam — Sanathnagar Industrial Belt',
    severity: 'HAZARDOUS',
    metrics: { 'AQI': '342 (Severe)', 'PM2.5': '185 µg/m³', 'Wind Speed': '4.2 km/h' },
    description: 'Industrial emissions combined with stagnant low-wind conditions creating localized smog pocket.',
    suggestions: [
      {
        id: 'SUGG_2_1',
        title: 'AI Industrial Boiler Emission Cap Command',
        agent: 'Pollution Agent',
        agentColor: 'rose',
        mechanism: 'Send automated IoT telemetry commands to temporarily cap industrial boiler output at 50% capacity.',
        predictedImpact: '-28% Particulate Emission within 2 hours',
        confidence: 94,
        timeToEffect: '15 mins',
        tag: 'Regulatory Cap'
      },
      {
        id: 'SUGG_2_2',
        title: 'Deploy Smog-Tower Mist Cannons & Sprinklers',
        agent: 'Environmental AI',
        agentColor: 'cyan',
        mechanism: 'Trigger 12 automated urban mist cannons along key industrial perimeters to bind particulates.',
        predictedImpact: '-18% Ambient PM10 Settling Rate',
        confidence: 91,
        timeToEffect: '3 mins',
        tag: 'Physical Suppression'
      },
      {
        id: 'SUGG_2_3',
        title: 'Heavy Commercial Diesel Truck Restriction',
        agent: 'Traffic-Pollution Co-op AI',
        agentColor: 'amber',
        mechanism: 'Reroute BS-IV and below heavy cargo trucks away from inner ring road until 10 PM.',
        predictedImpact: '-35% NOx & Soot Accumulation',
        confidence: 96,
        timeToEffect: '10 mins',
        tag: 'Traffic Control'
      },
      {
        id: 'SUGG_2_4',
        title: 'Zonal Green Belt Bio-Filter Array Activation',
        agent: 'Ecology AI',
        agentColor: 'emerald',
        mechanism: 'Activate urban forestry misting arrays and high-efficiency roadside bio-filters.',
        predictedImpact: '-15% Localized AQI Reduction',
        confidence: 85,
        timeToEffect: '20 mins',
        tag: 'Ecology'
      }
    ]
  },
  {
    id: 'PROB_03',
    title: 'Peak Evening Power Surge & Grid Overload in HITEC City Substation',
    domain: 'Smart Energy Grid',
    location: 'HITEC City — Knowledge City Substation',
    severity: 'WARNING',
    metrics: { 'Grid Load': '94.8%', 'Peak Demand': '142 MW', 'Voltage Dip Risk': 'High' },
    description: 'Substation operating near maximum safe threshold due to simultaneous commercial HVAC and EV charging loads.',
    suggestions: [
      {
        id: 'SUGG_3_1',
        title: 'Commercial HVAC Smart Thermostat Pre-Cooling Adjustment',
        agent: 'Energy Supervisor',
        agentColor: 'emerald',
        mechanism: 'Signal 45 IT park building management systems to adjust thermostat setpoints by +1.5°C.',
        predictedImpact: '-18 MW Peak Load Offset',
        confidence: 96,
        timeToEffect: '5 mins',
        tag: 'Demand Response'
      },
      {
        id: 'SUGG_3_2',
        title: 'Grid Injection from BESS Battery Storage Systems',
        agent: 'Storage AI',
        agentColor: 'cyan',
        mechanism: 'Discharge 25 MWh from local Gachibowli Battery Storage Facility into grid.',
        predictedImpact: 'Stabilizes Frequency to 50.0 Hz',
        confidence: 98,
        timeToEffect: 'Immediate',
        tag: 'Grid Storage'
      },
      {
        id: 'SUGG_3_3',
        title: 'Smart Streetlight Dimming to 60% Capacity',
        agent: 'Municipal IoT AI',
        agentColor: 'violet',
        mechanism: 'Automatically dim 14,000 non-critical LED streetlights along major expressways.',
        predictedImpact: '-4.2 MW Load Reduction',
        confidence: 99,
        timeToEffect: '1 min',
        tag: 'IoT Automation'
      },
      {
        id: 'SUGG_3_4',
        title: 'EV Fast-Charging Rate Throttling',
        agent: 'Grid Load AI',
        agentColor: 'amber',
        mechanism: 'Temporarily throttle commercial EV fast chargers to 50% charging speed during 6 PM - 8 PM window.',
        predictedImpact: '-8.5 MW Peak Demand Relief',
        confidence: 90,
        timeToEffect: '2 mins',
        tag: 'EV Management'
      }
    ]
  },
  {
    id: 'PROB_04',
    title: 'Monsoonal Flood Waterlogging Hazard at Begumpet Flyover Underpass',
    domain: 'Weather & Stormwater',
    location: 'Begumpet Airport Flyover Underpass',
    severity: 'CRITICAL',
    metrics: { 'Water Depth': '38 cm', 'Rainfall Rate': '48 mm/hr', 'Drainage Flow': 'Restricted' },
    description: 'Flash rain accumulation creating hazardous waterlogging and immobilizing low-clearance vehicles.',
    suggestions: [
      {
        id: 'SUGG_4_1',
        title: 'High-Capacity Drainage Auxiliary Pump Trigger',
        agent: 'Stormwater AI',
        agentColor: 'cyan',
        mechanism: 'Engage 4 auxiliary 500-HP stormwater pumps at Begumpet Nala drainage outlet.',
        predictedImpact: '-15 cm Water Depth per 10 mins',
        confidence: 97,
        timeToEffect: '1 min',
        tag: 'Automated Pumping'
      },
      {
        id: 'SUGG_4_2',
        title: 'Automated Road Barrier Underpass Closure & Diversion',
        agent: 'Public Safety AI',
        agentColor: 'rose',
        mechanism: 'Lower automated barrier gates at underpass entry and route traffic onto elevated flyover.',
        predictedImpact: '0 Stranded Vehicles | 100% Safety Guarantee',
        confidence: 99,
        timeToEffect: '30 secs',
        tag: 'Safety Diversion'
      },
      {
        id: 'SUGG_4_3',
        title: 'Upstream Hussain Sagar Sluice Gate Discharge Adjustment',
        agent: 'Hydrology AI',
        agentColor: 'violet',
        mechanism: 'Adjust retention basin sluice gates to increase drainage intake velocity.',
        predictedImpact: '+35% Drainage Discharge Velocity',
        confidence: 91,
        timeToEffect: '5 mins',
        tag: 'Hydraulics'
      },
      {
        id: 'SUGG_4_4',
        title: 'Geo-Targeted Citizen Emergency Push Notification',
        agent: 'Civic Alert AI',
        agentColor: 'emerald',
        mechanism: 'Send emergency push broadcasts to mobile devices within 3 km radius.',
        predictedImpact: '85% Traffic Bypass Avoidance',
        confidence: 95,
        timeToEffect: 'Immediate',
        tag: 'Civic Warning'
      }
    ]
  }
]

export default function ProblemSolverSection({ initialProblemId = 'PROB_01' }) {
  const [selectedProbId, setSelectedProbId] = useState(initialProblemId)
  const [appliedSuggestions, setAppliedSuggestions] = useState({})
  const [activeDomainFilter, setActiveDomainFilter] = useState('ALL')

  const currentProblem = urbanProblems.find(p => p.id === selectedProbId) || urbanProblems[0]

  const handleApplySuggestion = (suggId) => {
    setAppliedSuggestions(prev => ({
      ...prev,
      [suggId]: true
    }))
  }

  const filteredProblems = activeDomainFilter === 'ALL'
    ? urbanProblems
    : urbanProblems.filter(p => p.domain.toLowerCase().includes(activeDomainFilter.toLowerCase()))

  return (
    <div style={{ marginTop: 'var(--space-xl)' }}>
      
      {/* Header Banner */}
      <GlassCard glow="cyan" style={{ marginBottom: 'var(--space-lg)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <Brain size={24} color="var(--accent-cyan)" />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, background: 'linear-gradient(90deg, #fff, var(--accent-cyan))', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                AI Multi-Suggestion Problem Solver
              </h2>
              <span className="badge badge-ai" style={{ fontSize: '0.65rem' }}>3-4 AI Solutions / Problem</span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              Select any urban problem to inspect 3-4 specialized AI-generated mitigation strategies with live predicted impacts.
            </p>
          </div>

          {/* Domain Filter Pills */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {['ALL', 'Traffic', 'Air Quality', 'Energy', 'Weather'].map(domain => (
              <button
                key={domain}
                onClick={() => setActiveDomainFilter(domain)}
                style={{
                  padding: '5px 12px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid',
                  borderColor: activeDomainFilter === domain ? 'var(--accent-cyan)' : 'var(--border-default)',
                  background: activeDomainFilter === domain ? 'var(--accent-cyan-dim)' : 'var(--bg-tertiary)',
                  color: activeDomainFilter === domain ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)'
                }}
              >
                {domain}
              </button>
            ))}
          </div>
        </div>
      </GlassCard>

      {/* Main 2-Column Workspace */}
      <div className="grid-dashboard" style={{ gridTemplateColumns: '320px 1fr' }}>
        
        {/* Left Column: Problem Selector List */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600, letterSpacing: '0.05em' }}>
            ACTIVE URBAN PROBLEMS ({filteredProblems.length})
          </div>

          {filteredProblems.map(prob => {
            const isSelected = prob.id === selectedProbId
            const isCritical = prob.severity === 'CRITICAL' || prob.severity === 'HAZARDOUS'
            const appliedCount = prob.suggestions.filter(s => appliedSuggestions[s.id]).length

            return (
              <div
                key={prob.id}
                onClick={() => setSelectedProbId(prob.id)}
                style={{
                  padding: '14px',
                  borderRadius: 'var(--radius-md)',
                  background: isSelected ? 'var(--bg-secondary)' : 'var(--bg-tertiary)',
                  border: `1px solid ${isSelected ? 'var(--accent-cyan)' : 'var(--border-default)'}`,
                  cursor: 'pointer',
                  boxShadow: isSelected ? '0 0 16px rgba(0,240,255,0.15)' : 'none',
                  transition: 'all var(--transition-fast)'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span className="badge" style={{
                    fontSize: '0.6rem',
                    background: isCritical ? 'rgba(244,63,94,0.15)' : 'rgba(245,158,11,0.15)',
                    color: isCritical ? 'var(--accent-rose)' : 'var(--accent-amber)',
                    border: `1px solid ${isCritical ? 'rgba(244,63,94,0.3)' : 'rgba(245,158,11,0.3)'}`
                  }}>
                    {prob.severity}
                  </span>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {prob.domain}
                  </span>
                </div>

                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)', lineHeight: 1.3, marginBottom: '8px' }}>
                  {prob.title}
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  <span>📍 {prob.location.split('—')[0]}</span>
                  {appliedCount > 0 && (
                    <span style={{ color: 'var(--accent-emerald)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '3px' }}>
                      <CheckCircle2 size={12} /> {appliedCount} Applied
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Right Column: Selected Problem Details & 3-4 AI Suggestions Grid */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          
          {/* Selected Problem Overview Banner */}
          <GlassCard glow="rose">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <AlertTriangle size={18} color="var(--accent-rose)" />
                  <span style={{ fontSize: '0.7rem', color: 'var(--accent-rose)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                    PROBLEM IDENTIFIED — {currentProblem.id}
                  </span>
                </div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  {currentProblem.title}
                </h3>
              </div>
              <StatusBadge status={currentProblem.severity} />
            </div>

            <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', margin: '0 0 14px 0', lineHeight: 1.4 }}>
              {currentProblem.description}
            </p>

            {/* Metric Pills */}
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', paddingTop: '12px', borderTop: '1px solid var(--border-default)' }}>
              {Object.entries(currentProblem.metrics).map(([k, v]) => (
                <div key={k} style={{ padding: '6px 12px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)', fontSize: '0.75rem' }}>
                  <span style={{ color: 'var(--text-muted)', marginRight: '6px' }}>{k}:</span>
                  <strong style={{ color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>{v}</strong>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* 3-4 AI Suggestions Cards Grid */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Sparkles size={16} color="var(--accent-cyan)" />
                AI AGENT SUGGESTIONS TO TACKLE THIS PROBLEM ({currentProblem.suggestions.length} OPTIONS)
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                Multi-Agent Supervisor Evaluation
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
              {currentProblem.suggestions.map((sugg, idx) => {
                const isApplied = appliedSuggestions[sugg.id]

                return (
                  <GlassCard
                    key={sugg.id}
                    glow={isApplied ? 'emerald' : 'cyan'}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      justify: 'space-between',
                      position: 'relative',
                      border: isApplied ? '1px solid var(--accent-emerald)' : undefined
                    }}
                  >
                    <div>
                      {/* Top Bar */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <span className="badge" style={{
                          fontSize: '0.65rem',
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-default)',
                          color: `var(--accent-${sugg.agentColor || 'cyan'})`
                        }}>
                          <Cpu size={12} style={{ marginRight: '4px' }} />
                          {sugg.agent}
                        </span>

                        <span style={{
                          fontSize: '0.65rem',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          color: sugg.confidence > 90 ? 'var(--accent-emerald)' : 'var(--accent-amber)'
                        }}>
                          {sugg.confidence}% CONFIDENCE
                        </span>
                      </div>

                      {/* Title */}
                      <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 8px 0', lineHeight: 1.3 }}>
                        Option {idx + 1}: {sugg.title}
                      </h4>

                      {/* Mechanism */}
                      <p style={{ fontSize: '0.775rem', color: 'var(--text-muted)', lineHeight: 1.4, margin: '0 0 14px 0' }}>
                        {sugg.mechanism}
                      </p>

                      {/* Impact Banner */}
                      <div style={{
                        padding: '8px 10px',
                        background: isApplied ? 'var(--accent-emerald-dim)' : 'var(--bg-primary)',
                        borderRadius: 'var(--radius-sm)',
                        border: `1px solid ${isApplied ? 'rgba(16,185,129,0.3)' : 'var(--border-default)'}`,
                        marginBottom: '14px'
                      }}>
                        <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '2px' }}>
                          PREDICTED IMPACT & TIMELINE ({sugg.timeToEffect})
                        </div>
                        <div style={{ fontSize: '0.775rem', fontWeight: 700, color: isApplied ? 'var(--accent-emerald)' : 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                          {sugg.predictedImpact}
                        </div>
                      </div>
                    </div>

                    {/* Action Button */}
                    <button
                      onClick={() => handleApplySuggestion(sugg.id)}
                      disabled={isApplied}
                      style={{
                        width: '100%',
                        padding: '10px',
                        borderRadius: 'var(--radius-sm)',
                        border: 'none',
                        background: isApplied ? 'var(--accent-emerald)' : 'var(--accent-blue)',
                        color: '#fff',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: isApplied ? 'default' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        transition: 'all var(--transition-fast)'
                      }}
                    >
                      {isApplied ? (
                        <>
                          <CheckCircle2 size={16} />
                          <span>AI Suggestion Applied & Executed</span>
                        </>
                      ) : (
                        <>
                          <Zap size={16} />
                          <span>Execute AI Suggestion</span>
                        </>
                      )}
                    </button>
                  </GlassCard>
                )
              })}
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}

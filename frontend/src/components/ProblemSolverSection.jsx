import { useState } from 'react'
import {
  AlertTriangle, Brain, CheckCircle2, Zap, ArrowRight, ShieldCheck,
  TrendingDown, Sparkles, Filter, RefreshCw, Cpu
} from 'lucide-react'
import GlassCard from './GlassCard'
import StatusBadge from './StatusBadge'
import { alertsApi, planningApi } from '../services/api'

export const urbanProblems = []

export default function ProblemSolverSection({ problems = urbanProblems, initialProblemId = null }) {
  const [selectedProbId, setSelectedProbId] = useState(initialProblemId)
  const [appliedSuggestions, setAppliedSuggestions] = useState({})
  const [activeDomainFilter, setActiveDomainFilter] = useState('ALL')
  const [isExecuting, setIsExecuting] = useState(false)

  const problemList = Array.isArray(problems) ? problems : []

  const filteredProblems = problemList.filter(p => {
    if (activeDomainFilter === 'ALL') return true
    return (p.domain || '').toLowerCase().includes(activeDomainFilter.toLowerCase())
  })

  const currentProblem = filteredProblems.find(p => p.id === selectedProbId) || filteredProblems[0] || null

  const handleApplySuggestion = async (suggId) => {
    if (!currentProblem) return
    setIsExecuting(true)
    const sugg = (currentProblem.suggestions || []).find(s => s.id === suggId)

    try {
      // Dispatch Planner Central Coordinator with suggestion objective
      await planningApi.executePlanner({
        objective: sugg ? `${sugg.title} for ${currentProblem.title}` : 'Execute AI Suggestion',
        location: currentProblem.location || 'Hyderabad'
      })

      // Acknowledge corresponding system alert if exists
      if (currentProblem.id) {
        await alertsApi.acknowledgeAlert(currentProblem.id, 'URBAN_PLANNER_01', `Executed: ${sugg?.title || suggId}`)
      }
    } catch (err) {
      console.warn('Planner suggestion dispatch warning:', err)
    } finally {
      setIsExecuting(false)
      setAppliedSuggestions(prev => ({
        ...prev,
        [suggId]: true
      }))
    }
  }

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
              <span className="badge badge-ai" style={{ fontSize: '0.65rem' }}>Active Incidents & Mitigations</span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: 0 }}>
              Inspect AI-generated mitigation strategies and real-time intervention plans for detected urban incidents.
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

      {/* Empty State or Main 2-Column Workspace */}
      {problemList.length === 0 ? (
        <GlassCard glow="none" style={{ textAlign: 'center', padding: 'var(--space-2xl) var(--space-xl)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '4px'
            }}>
              <ShieldCheck size={26} color="var(--accent-emerald)" />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              No active incidents detected
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '480px', margin: 0, lineHeight: 1.5 }}>
              All monitored urban sectors are currently operating within normal parameters. Real-time incidents detected via sensor telemetry and live simulations will appear here.
            </p>
          </div>
        </GlassCard>
      ) : filteredProblems.length === 0 ? (
        <GlassCard glow="none" style={{ textAlign: 'center', padding: 'var(--space-xl)' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
            No active incidents detected for domain: <strong style={{ color: 'var(--text-primary)' }}>{activeDomainFilter}</strong>
          </p>
        </GlassCard>
      ) : (
        <div className="grid-dashboard" style={{ gridTemplateColumns: '320px 1fr' }}>
          {/* Left Column: Problem Selector List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600, letterSpacing: '0.05em' }}>
              ACTIVE URBAN PROBLEMS ({filteredProblems.length})
            </div>

            {filteredProblems.map(prob => {
              const isSelected = prob.id === (currentProblem?.id || selectedProbId)
              const isCritical = prob.severity === 'CRITICAL' || prob.severity === 'HAZARDOUS'
              const appliedCount = (prob.suggestions || []).filter(s => appliedSuggestions[s.id]).length

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
                      {prob.severity || 'ACTIVE'}
                    </span>
                    <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      {prob.domain}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)', lineHeight: 1.3, marginBottom: '8px' }}>
                    {prob.title}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    <span>📍 {(prob.location || '').split('—')[0]}</span>
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

          {/* Right Column: Selected Problem Details & AI Suggestions Grid */}
          {currentProblem && (
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
                  {currentProblem.severity && <StatusBadge status={currentProblem.severity} />}
                </div>

                {currentProblem.description && (
                  <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary)', margin: '0 0 14px 0', lineHeight: 1.4 }}>
                    {currentProblem.description}
                  </p>
                )}

                {/* Metric Pills */}
                {currentProblem.metrics && Object.keys(currentProblem.metrics).length > 0 && (
                  <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', paddingTop: '12px', borderTop: '1px solid var(--border-default)' }}>
                    {Object.entries(currentProblem.metrics).map(([k, v]) => (
                      <div key={k} style={{ padding: '6px 12px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)', fontSize: '0.75rem' }}>
                        <span style={{ color: 'var(--text-muted)', marginRight: '6px' }}>{k}:</span>
                        <strong style={{ color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>{v}</strong>
                      </div>
                    ))}
                  </div>
                )}
              </GlassCard>

              {/* AI Suggestions Cards Grid */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Sparkles size={16} color="var(--accent-cyan)" />
                    AI AGENT SUGGESTIONS ({(currentProblem.suggestions || []).length} OPTIONS)
                  </div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    Multi-Agent Supervisor Evaluation
                  </span>
                </div>

                {(currentProblem.suggestions || []).length === 0 ? (
                  <GlassCard glow="none" style={{ padding: 'var(--space-lg)', textAlign: 'center' }}>
                    <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', margin: 0 }}>
                      No automated suggestions registered for this incident.
                    </p>
                  </GlassCard>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                    {(currentProblem.suggestions || []).map((sugg, idx) => {
                      const isApplied = appliedSuggestions[sugg.id]

                      return (
                        <GlassCard
                          key={sugg.id}
                          glow={isApplied ? 'emerald' : 'cyan'}
                          style={{
                            display: 'flex',
                            flexDirection: 'column',
                            justifyContent: 'space-between',
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
                                {sugg.agent || 'AI Specialist'}
                              </span>

                              {sugg.confidence !== undefined && (
                                <span style={{
                                  fontSize: '0.65rem',
                                  fontFamily: 'var(--font-mono)',
                                  fontWeight: 700,
                                  color: sugg.confidence > 90 ? 'var(--accent-emerald)' : 'var(--accent-amber)'
                                }}>
                                  {sugg.confidence}% CONFIDENCE
                                </span>
                              )}
                            </div>

                            {/* Title */}
                            <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 8px 0', lineHeight: 1.3 }}>
                              Option {idx + 1}: {sugg.title}
                            </h4>

                            {/* Mechanism */}
                            {sugg.mechanism && (
                              <p style={{ fontSize: '0.775rem', color: 'var(--text-muted)', lineHeight: 1.4, margin: '0 0 14px 0' }}>
                                {sugg.mechanism}
                              </p>
                            )}

                            {/* Impact Banner */}
                            {(sugg.predictedImpact || sugg.timeToEffect) && (
                              <div style={{
                                padding: '8px 10px',
                                background: isApplied ? 'var(--accent-emerald-dim)' : 'var(--bg-primary)',
                                borderRadius: 'var(--radius-sm)',
                                border: `1px solid ${isApplied ? 'rgba(16,185,129,0.3)' : 'var(--border-default)'}`,
                                marginBottom: '14px'
                              }}>
                                {sugg.timeToEffect && (
                                  <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '2px' }}>
                                    PREDICTED IMPACT & TIMELINE ({sugg.timeToEffect})
                                  </div>
                                )}
                                {sugg.predictedImpact && (
                                  <div style={{ fontSize: '0.775rem', fontWeight: 700, color: isApplied ? 'var(--accent-emerald)' : 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                                    {sugg.predictedImpact}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>

                          {/* Action Button */}
                          <button
                            onClick={() => handleApplySuggestion(sugg.id)}
                            disabled={isApplied || isExecuting}
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
                )}
              </div>

            </div>
          )}

        </div>
      )}
    </div>
  )
}

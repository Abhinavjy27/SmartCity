import { useState } from 'react'
import {
  Brain, Send, Cpu, Database, AlertCircle, CheckCircle2,
  Play, FileText, BarChart3, ShieldCheck, HelpCircle, ArrowRight
} from 'lucide-react'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import AnimatedCounter from '../components/AnimatedCounter'
import ProblemSolverSection from '../components/ProblemSolverSection'

const templates = [
  {
    label: "Cross-Domain Infrastructure",
    text: "Identify the best areas for infrastructure investment while considering traffic, pollution, and energy grid load impact."
  },
  {
    label: "Traffic Congestion Corridor",
    text: "Traffic congestion has increased significantly around the Gachibowli Flyover corridor during evening rush hours. Suggest mitigation."
  },
  {
    label: "Industrial Zone Air Quality",
    text: "Air quality has deteriorated around the Nacharam Industrial Zone. Identify likely causes and recommend mitigation plans."
  }
]

export default function Planning() {
  const [query, setQuery] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [step, setStep] = useState(0) // 0: Idle, 1: Supervisor Parse, 2: Context Load, 3: Agent Exec, 4: Complete
  const [approvalStatus, setApprovalStatus] = useState('Generated') // Generated, Under Review, Approved

  const handleRunAnalysis = () => {
    if (!query.trim()) return
    setIsProcessing(true)
    setStep(1)

    setTimeout(() => {
      setStep(2) // Context Loading
      setTimeout(() => {
        setStep(3) // Specialist Agent Execution
        setTimeout(() => {
          setStep(4) // Complete
          setIsProcessing(false)
        }, 1800)
      }, 1500)
    }, 1200)
  }

  const handleApplyTemplate = (txt) => {
    setQuery(txt)
  }

  return (
    <div className="stagger-children">
      <div className="page-header">
        <h1><Brain size={28} /> Planning Assistant</h1>
        <div style={{ display: 'flex', gap: '8px' }}>
          <StatusBadge status="AI" />
          <span className="badge badge-info">Supervisor AI Platform</span>
        </div>
      </div>

      <div className="grid-dashboard" style={{ gridTemplateColumns: '1fr 1fr' }}>

        {/* Left Column: Planning Request Input Workspace */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
          <GlassCard>
            <div className="section-title">Planner Input Workspace</div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
              Submit natural-language observations, infrastructure suggestions, or operational issues to the Supervisor AI.
            </p>

            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Enter planning request or analysis parameters here..."
              style={{
                width: '100%', minHeight: '140px', padding: '12px',
                background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)', color: 'var(--text-primary)',
                fontFamily: 'var(--font-body)', fontSize: '0.875rem', resize: 'vertical',
                outline: 'none', transition: 'border-color var(--transition-fast)'
              }}
              onFocus={e => e.currentTarget.style.borderColor = 'var(--accent-cyan)'}
              onBlur={e => e.currentTarget.style.borderColor = 'var(--border-default)'}
            />

            {/* Template Buttons */}
            <div style={{ marginTop: '12px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '8px', fontFamily: 'var(--font-mono)' }}>
                PLANNING INQUIRY TEMPLATES
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {templates.map((t, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleApplyTemplate(t.text)}
                    style={{
                      padding: '6px 12px', background: 'var(--bg-tertiary)',
                      border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                      color: 'var(--text-secondary)', fontSize: '0.75rem', cursor: 'pointer',
                      transition: 'all var(--transition-fast)'
                    }}
                    onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-cyan)'; e.currentTarget.style.color = 'var(--text-primary)' }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-default)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Submit Button */}
            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={handleRunAnalysis}
                disabled={isProcessing || !query.trim()}
                style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  padding: '10px 20px', background: isProcessing || !query.trim() ? 'var(--bg-tertiary)' : 'var(--accent-blue)',
                  color: isProcessing || !query.trim() ? 'var(--text-muted)' : '#fff',
                  border: 'none', borderRadius: 'var(--radius-sm)',
                  fontSize: '0.85rem', fontWeight: 600, cursor: isProcessing || !query.trim() ? 'not-allowed' : 'pointer',
                  transition: 'background var(--transition-fast)'
                }}
              >
                <Cpu size={16} />
                <span>{isProcessing ? 'Orchestrating Agents...' : 'Dispatch Request'}</span>
              </button>
            </div>
          </GlassCard>

          {/* Supervisor AI Orchestration Workflow Visualizer */}
          {(isProcessing || step > 0) && (
            <GlassCard>
              <div className="section-title">Supervisor AI Agent Orchestration Flow</div>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
                Visualization of structural routing flow within the SUPADSP Agent Architecture.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative' }}>
                {/* Intent Understanding */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  opacity: step >= 1 ? 1 : 0.4, transition: 'opacity 0.3s'
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: step === 1 ? 'var(--accent-cyan-dim)' : (step > 1 ? 'var(--accent-emerald-dim)' : 'var(--bg-tertiary)'),
                    border: `1px solid ${step === 1 ? 'var(--accent-cyan)' : (step > 1 ? 'var(--accent-emerald)' : 'var(--border-default)')}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {step > 1 ? <CheckCircle2 size={14} color="var(--accent-emerald)" /> : <Cpu size={14} color={step === 1 ? 'var(--accent-cyan)' : 'var(--text-muted)'} />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>Intent Parsing & Capability Resolution</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Supervisor AI evaluating cross-domain query dependencies</div>
                  </div>
                </div>

                {/* Context Manager */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  opacity: step >= 2 ? 1 : 0.4, transition: 'opacity 0.3s'
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: step === 2 ? 'var(--accent-cyan-dim)' : (step > 2 ? 'var(--accent-emerald-dim)' : 'var(--bg-tertiary)'),
                    border: `1px solid ${step === 2 ? 'var(--accent-cyan)' : (step > 2 ? 'var(--accent-emerald)' : 'var(--border-default)')}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {step > 2 ? <CheckCircle2 size={14} color="var(--accent-emerald)" /> : <Database size={14} color={step === 2 ? 'var(--accent-cyan)' : 'var(--text-muted)'} />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>Spatial & Historical Context Loading</div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Fetching location maps, weather coefficients, and 3-year telemetry</div>
                  </div>
                </div>

                {/* Specialist Agent Resolution */}
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '12px',
                  opacity: step >= 3 ? 1 : 0.4, transition: 'opacity 0.3s'
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%',
                    background: step === 3 ? 'var(--accent-cyan-dim)' : (step > 3 ? 'var(--accent-emerald-dim)' : 'var(--bg-tertiary)'),
                    border: `1px solid ${step === 3 ? 'var(--accent-cyan)' : (step > 3 ? 'var(--accent-emerald)' : 'var(--border-default)')}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    {step > 3 ? <CheckCircle2 size={14} color="var(--accent-emerald)" /> : <Play size={14} color={step === 3 ? 'var(--accent-cyan)' : 'var(--text-muted)'} />}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>Domain Specialist Executions</div>
                    <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                      <span className="badge badge-info" style={{ fontSize: '0.6rem' }}>Traffic Agent</span>
                      <span className="badge badge-ai" style={{ fontSize: '0.6rem' }}>Pollution Agent</span>
                      <span className="badge badge-smooth" style={{ fontSize: '0.6rem' }}>Optimization Agent</span>
                    </div>
                  </div>
                </div>
              </div>
            </GlassCard>
          )}
        </div>

        {/* Right Column: Structured Decision Artifact Output */}
        <div>
          {step === 4 ? (
            <GlassCard glow="violet">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-default)', paddingBottom: '12px', marginBottom: '16px' }}>
                <div>
                  <span style={{ fontSize: '0.7rem', color: 'var(--accent-violet)', fontFamily: 'var(--font-mono)', fontWeight: 600, letterSpacing: '0.05em' }}>
                    DECISION SUPPORT ARTIFACT
                  </span>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '2px' }}>AI Planning Recommendation</h3>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)' }}>94.2%</div>
                  <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>CONFIDENCE SCORE</div>
                </div>
              </div>

              {/* Recommendation */}
              <div style={{ marginBottom: '16px' }}>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>RECOMMENDATION</span>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: 1.4, fontWeight: 500, marginTop: '2px' }}>
                  Deploy AI-Actuated Traffic Signal overrides at Mindspace Intersection, adjust the street-lighting dimming offsets to balance grid loads, and introduce industrial emission caps in the Nacharam Sector.
                </p>
              </div>

              {/* Domain Analysis */}
              <div style={{ marginBottom: '16px' }}>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>AGENTIC CO-ORDINATION ANALYSIS</span>
                <div style={{
                  display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '4px',
                  padding: '10px 12px', background: 'var(--bg-primary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)'
                }}>
                  <div style={{ fontSize: '0.75rem' }}>
                    <strong style={{ color: 'var(--accent-cyan)' }}>Traffic Agent:</strong> Evening corridor congestion index predicted to decrease by 18% with phase dimming.
                  </div>
                  <div style={{ fontSize: '0.75rem' }}>
                    <strong style={{ color: 'var(--accent-amber)' }}>Pollution Agent:</strong> Dispersion modeling predicts a local reduction of 22 ppm in particulate matter blocks.
                  </div>
                  <div style={{ fontSize: '0.75rem' }}>
                    <strong style={{ color: 'var(--accent-emerald)' }}>Energy Agent:</strong> Dimming saves 15% grid load margin to offset signal priority consumption.
                  </div>
                </div>
              </div>

              {/* GIS Map Evidence Graphic */}
              <div style={{ marginBottom: '16px' }}>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>SPATIAL LAYERING EVIDENCE</span>
                <div style={{
                  height: '120px', background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-sm)', marginTop: '4px', position: 'relative', overflow: 'hidden',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <svg width="100%" height="100%" viewBox="0 0 200 100" style={{ position: 'absolute', inset: 0 }}>
                    <circle cx="50" cy="50" r="4" fill="var(--accent-cyan)" />
                    <circle cx="100" cy="50" r="4" fill="var(--accent-emerald)" />
                    <circle cx="150" cy="50" r="4" fill="var(--accent-amber)" />
                    <line x1="54" y1="50" x2="96" y2="50" stroke="var(--border-default)" strokeWidth="1" />
                    <line x1="104" y1="50" x2="146" y2="50" stroke="var(--border-default)" strokeWidth="1" />
                    <text x="35" y="40" fill="var(--text-muted)" fontSize="5">Mindspace</text>
                    <text x="88" y="40" fill="var(--text-muted)" fontSize="5">Substation</text>
                    <text x="135" y="40" fill="var(--text-muted)" fontSize="5">Nacharam</text>
                  </svg>
                  <div style={{ position: 'absolute', bottom: '6px', right: '10px', fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    GIS Overlay Active
                  </div>
                </div>
              </div>

              {/* Explainability & Alternatives */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>EXPLAINABILITY FACTORS</span>
                  <ul style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', paddingLeft: '12px', marginTop: '2px', lineHeight: 1.4 }}>
                    <li>Wind speed &lt; 12 km/h prevents dispersion</li>
                    <li>Street-light savings offset signal draw</li>
                  </ul>
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>ALTERNATIVES CONSIDERED</span>
                  <p style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: '2px' }}>
                    Route divergence via ORR corridor (Confidence: 81.4%, 12-min travel delay offset).
                  </p>
                </div>
              </div>

              {/* Verification & Compliance */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: 'var(--accent-emerald-dim)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(16,185,129,0.2)', marginBottom: '20px' }}>
                <ShieldCheck size={16} color="var(--accent-emerald)" />
                <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>
                  Verified Compliant: Goverment policy parameters & rule validations met
                </span>
              </div>

              {/* Senior Approval workflow stage controls */}
              <div style={{ borderTop: '1px solid var(--border-default)', paddingTop: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>APPROVAL WORKFLOW STATE</span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--accent-cyan)' }}>{approvalStatus}</span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {approvalStatus === 'Generated' && (
                    <button
                      onClick={() => setApprovalStatus('Under Review')}
                      style={{
                        padding: '6px 12px', background: 'var(--accent-cyan)', color: '#fff',
                        border: 'none', borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer'
                      }}
                    >
                      Submit for Review
                    </button>
                  )}
                  {approvalStatus === 'Under Review' && (
                    <button
                      onClick={() => setApprovalStatus('Approved')}
                      style={{
                        padding: '6px 12px', background: 'var(--accent-emerald)', color: '#fff',
                        border: 'none', borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer'
                      }}
                    >
                      Approve & Implement
                    </button>
                  )}
                  <button
                    onClick={() => { setStep(0); setQuery(''); setApprovalStatus('Generated'); }}
                    style={{
                      padding: '6px 12px', background: 'var(--bg-primary)', color: 'var(--text-secondary)',
                      border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                      fontSize: '0.75rem', cursor: 'pointer'
                    }}
                  >
                    Clear Workspace
                  </button>
                </div>
              </div>
            </GlassCard>
          ) : (
            <GlassCard style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '340px', borderStyle: 'dashed' }}>
              <Brain size={48} color="var(--text-muted)" style={{ opacity: 0.3, marginBottom: '16px' }} />
              <h3 style={{ fontSize: '1rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>Awaiting Planning Request</h3>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', maxWidth: '300px' }}>
                Enter planning parameters on the left and dispatch to orchestrate Supervisor AI capabilities.
              </p>
            </GlassCard>
          )}
        </div>

      </div>

      {/* AI Multi-Suggestion Problem Solver Workspace */}
      <ProblemSolverSection />
    </div>
  )
}

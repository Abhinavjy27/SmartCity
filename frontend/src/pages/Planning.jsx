import { useState, useRef, useEffect } from 'react'
import {
  Brain, Send, Cpu, AlertCircle, CheckCircle2,
  Play, RefreshCw, BarChart3, Activity, Gauge,
  Clock, ArrowRight, ShieldCheck, Sparkles, TrendingUp, TrendingDown
} from 'lucide-react'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import ProblemSolverSection from '../components/ProblemSolverSection'
import { planningApi } from '../services/api'
import { usePlanner } from '../context/PlannerContext'

const samplePrompts = [
  "What is the traffic situation in Narayanguda?",
  "Which corridor is the bottleneck?",
  "Why is it slow?",
  "How can I improve it?",
  "Test the proposed intervention.",
  "Was the intervention effective?"
]

function formatInterventionBadgeLabel(item) {
  const type = String(item?.type || item?.intervention_type || 'Intervention').replace('_', ' ')
  const target = item?.target || ''
  const params = item?.parameters || {}
  const paramParts = []
  if (params.green_time_adjustment_sec !== undefined) {
    paramParts.push(`+${params.green_time_adjustment_sec}s`)
  } else if (params.adjustment_seconds !== undefined) {
    paramParts.push(`+${params.adjustment_seconds}s`)
  }
  if (params.diversion_fraction !== undefined) {
    paramParts.push(`${Math.round(params.diversion_fraction * 100)}%`)
  }
  const paramStr = paramParts.length > 0 ? ` ${paramParts.join(', ')}` : ''
  const typeCapitalized = type.charAt(0).toUpperCase() + type.slice(1)
  return `${typeCapitalized}${target ? ` — ${target}` : ''}${paramStr}`
}

function resolveRequestedDuration(res, promptText) {
  const txt = String(promptText || res?.query || res?.objective || '').toLowerCase()
  if (txt.includes('300') && txt.includes('600')) {
    return 'BOTH'
  }
  if (res?.final_response?.requested_duration) {
    return Number(res.final_response.requested_duration)
  }
  if (txt.includes('600s') || txt.includes('600 second') || txt.includes('600-second') || txt.includes('600')) {
    return 600
  }
  if (txt.includes('300s') || txt.includes('300 second') || txt.includes('300-second') || txt.includes('300')) {
    return 300
  }
  if (txt.includes('120s') || txt.includes('120 second') || txt.includes('120-second') || txt.includes('120')) {
    return 120
  }
  return null
}

function getScenarioDuration(s) {
  if (!s) return null
  const d = s.duration_seconds ?? s.duration ?? s.metadata?.duration_seconds ?? s.comparison?.intervention_duration_seconds ?? s.comparison?.baseline_duration_seconds
  return d !== null && d !== undefined && !isNaN(Number(d)) ? Number(d) : null
}

export function getSimulationKey(sim) {
  if (!sim) return ''
  const sId = sim.scenario_id || (sim.intervention && (sim.intervention.type || sim.intervention.intervention_type)) || 'sim'
  const dur = getScenarioDuration(sim) || 'unknown_dur'
  const scen = sim.scenario || sim.metadata?.demand_profile || sim.comparison?.intervention_scenario || 'unknown_scen'
  const seed = sim.seed ?? sim.metadata?.random_seed ?? sim.comparison?.intervention_seed ?? 'unknown_seed'
  return `${sId}::dur_${dur}::scen_${scen}::seed_${seed}`
}

function parseMultiSimulationComparison(res, promptText) {
  const finalResp = res?.final_response || {}
  const rawScenarios = finalResp.tested_scenarios || res?.agent_results?.simulations || res?.collected_results?.simulations || []
  if (!Array.isArray(rawScenarios) || rawScenarios.length === 0) return null

  const targetDur = resolveRequestedDuration(res, promptText)
  const isBoth = targetDur === 'BOTH'

  const scenarios = (!isBoth && targetDur)
    ? rawScenarios.filter(s => getScenarioDuration(s) === targetDur)
    : rawScenarios

  // Filter out pure baseline entries so table rows only show actual tested candidate interventions
  const interventionScenarios = scenarios.filter(s => {
    const intApplied = s.intervention || s.intervention_applied
    if (!intApplied) return false
    const sId = String(s.scenario_id || '').toLowerCase()
    if (sId.startsWith('baseline') && !s.intervention && !s.intervention_applied) return false
    return true
  })

  const displayScenarios = interventionScenarios.length >= 2 ? interventionScenarios : scenarios
  if (displayScenarios.length <= 1) return null

  // Extract canonical baseline reference and metrics shared across this experiment set
  let canonicalBaseline = null
  for (const scen of displayScenarios) {
    const b = scen.baseline_metrics || scen.comparison?.baseline_summary
    if (b && (b.average_speed_kmh !== undefined || b.average_delay_sec !== undefined)) {
      canonicalBaseline = b
      break
    }
  }
  if (!canonicalBaseline) {
    const trf = res?.agent_results?.traffic || res?.collected_results?.traffic
    if (trf) {
      canonicalBaseline = trf.metrics || trf
    }
  }

  const items = displayScenarios.map(scen => {
    const intApplied = scen.intervention || scen.intervention_applied || {}
    const type = String(intApplied.type || 'intervention').replace('_', ' ')
    const target = intApplied.target || ''
    const params = intApplied.parameters || {}

    const paramParts = []
    if (params.green_time_adjustment_sec !== undefined) {
      paramParts.push(`+${params.green_time_adjustment_sec}s green`)
    } else if (params.adjustment_seconds !== undefined) {
      paramParts.push(`+${params.adjustment_seconds}s green`)
    }
    if (params.diversion_fraction !== undefined) {
      paramParts.push(`${Math.round(params.diversion_fraction * 100)}% diversion`)
    }
    const paramStr = paramParts.length > 0 ? ` (${paramParts.join(', ')})` : ''
    const scenDur = getScenarioDuration(scen)
    const durTag = isBoth && scenDur ? ` [${scenDur}s]` : ''
    const label = `${type.charAt(0).toUpperCase() + type.slice(1)}${target ? ` — ${target}` : ''}${paramStr}${durTag}`

    const comp = scen.comparison || {}
    let tgtSpdDelta = comp.target_corridor_speed_change_pct
    let tgtSpdVal = null
    if (comp.corridor_comparisons && Array.isArray(comp.corridor_comparisons)) {
      const match = comp.corridor_comparisons.find(c => c.name === target || String(c.id || '').toUpperCase().endsWith(String(target).slice(0, 2).toUpperCase()))
      if (match) {
        if (tgtSpdDelta === undefined || tgtSpdDelta === null) tgtSpdDelta = match.speed_change_pct
        tgtSpdVal = match.intervention_speed_kmh
      }
    }

    // Use NEW signed *_change_pct fields (negative = improved for delay/waiting/congestion)
    const netSpdDelta = comp.speed_change_pct
    const netSpdVal = comp.intervention_summary?.average_speed_kmh ?? scen.metrics?.average_speed_kmh
    const delayChangePct = comp.delay_change_pct ?? null
    const delayVal = comp.intervention_summary?.average_delay_sec ?? scen.metrics?.average_delay_sec
    const waitChangePct = comp.waiting_time_change_pct ?? null
    const waitVal = comp.intervention_summary?.average_waiting_time_sec ?? scen.metrics?.average_waiting_time_sec

    const tradeOffs = scen.corridor_trade_offs || comp.corridor_trade_offs || []
    const tradeOffsText = tradeOffs.length > 0 ? tradeOffs.join('; ') : (
      (delayChangePct !== null && delayChangePct !== undefined && delayChangePct > 1.0)
        ? `Network delay worsened by ${delayChangePct.toFixed(1)}%`
        : 'No material trade-offs'
    )
    const hasTradeOffs = tradeOffs.length > 0 || (delayChangePct !== null && delayChangePct !== undefined && delayChangePct > 1.0)
    const fmtSignedPct = (v) => v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${v}%`

    return {
      intervention: label,
      baselineMetrics: scen.baseline_metrics || comp.baseline_summary || canonicalBaseline,
      baselineReference: scen.baseline_reference || comp.baseline_reference || null,
      interventionMetrics: scen.intervention_metrics || comp.intervention_summary || scen.metrics,
      targetSpeedDelta: tgtSpdDelta,
      targetSpeedText: tgtSpdVal !== null && tgtSpdVal !== undefined
        ? `${Number(tgtSpdVal).toFixed(1)} km/h (${(tgtSpdDelta ?? 0) > 0 ? '+' : ''}${tgtSpdDelta ?? 0}%)`
        : (tgtSpdDelta !== undefined && tgtSpdDelta !== null ? `${tgtSpdDelta > 0 ? '+' : ''}${tgtSpdDelta}%` : '—'),
      netSpeedDelta: netSpdDelta,
      netSpeedText: netSpdVal !== null && netSpdVal !== undefined
        ? `${Number(netSpdVal).toFixed(1)} km/h (${(netSpdDelta ?? 0) > 0 ? '+' : ''}${netSpdDelta ?? 0}%)`
        : (netSpdDelta !== undefined && netSpdDelta !== null ? `${netSpdDelta > 0 ? '+' : ''}${netSpdDelta}%` : '—'),
      delayChangePct,
      delayText: delayVal !== null && delayVal !== undefined
        ? `${Number(delayVal).toFixed(1)}s (${fmtSignedPct(delayChangePct)})`
        : fmtSignedPct(delayChangePct),
      waitingChangePct: waitChangePct,
      waitingText: waitVal !== null && waitVal !== undefined
        ? `${Number(waitVal).toFixed(1)}s (${fmtSignedPct(waitChangePct)})`
        : fmtSignedPct(waitChangePct),
      tradeOffsText,
      hasTradeOffs,
      scenario: comp.baseline_scenario || comp.intervention_scenario || scen.scenario || 'synthetic_peak_westbound',
      durationSeconds: scenDur,
      seed: comp.baseline_seed ?? comp.intervention_seed ?? scen.seed ?? scen.metadata?.random_seed ?? null,
      fairComparison: comp.fair_comparison ?? true,
    }
  })

  items.canonicalBaseline = canonicalBaseline
  const firstComp = displayScenarios[0]?.comparison || {}
  items.scenario = firstComp.baseline_scenario || firstComp.intervention_scenario || displayScenarios[0]?.scenario || 'synthetic_peak_westbound'
  items.durationSeconds = isBoth ? '300s & 600s' : (targetDur || getScenarioDuration(displayScenarios[0]))
  items.seed = firstComp.baseline_seed ?? firstComp.intervention_seed ?? displayScenarios[0]?.seed ?? displayScenarios[0]?.metadata?.random_seed ?? null
  items.fairComparison = displayScenarios.every(s => s.comparison?.fair_comparison !== false)
  return items
}

function parseTrafficEvidence(res) {
  const trf = res?.agent_results?.traffic || res?.collected_results?.traffic
  if (!trf) return null

  const metrics = trf.metrics || {}
  const obs = trf.observations || {}
  const bottlenecks = trf.bottlenecks || []
  const primaryBottleneck = bottlenecks[0] || null

  const netSpeed = metrics.average_speed_kmh ?? trf.average_speed_kmh ?? obs.network_average_speed_kmh
  const lowestCorridor = primaryBottleneck?.corridor || (
    trf.corridors && trf.corridors.length > 0
      ? [...trf.corridors].sort((a, b) => (a.avg_speed ?? 999) - (b.avg_speed ?? 999))[0]?.name
      : null
  )
  const lowestSpeed = primaryBottleneck?.evidence?.speed_kmh ?? (
    trf.corridors && trf.corridors.length > 0
      ? [...trf.corridors].sort((a, b) => (a.avg_speed ?? 999) - (b.avg_speed ?? 999))[0]?.avg_speed
      : null
  )

  const waitingTime = metrics.average_waiting_time_sec ?? trf.average_waiting_time_sec ?? obs.average_waiting_time_sec
  const delay = metrics.average_delay_sec ?? trf.average_delay_sec ?? obs.average_delay_sec
  const congestion = metrics.congestion_index ?? trf.congestion_index ?? obs.congestion_index
  const activeVehicles = metrics.active_vehicles ?? trf.active_vehicles ?? obs.active_vehicles
  const totalVehicles = metrics.total_vehicles ?? trf.total_vehicles ?? obs.total_vehicles
  const throughput = metrics.throughput ?? trf.throughput ?? obs.throughput

  return {
    scenario: trf.metadata?.demand_profile || trf.scenario || 'synthetic_peak_westbound',
    durationSeconds: getScenarioDuration(trf),
    seed: trf.metadata?.random_seed ?? trf.seed ?? null,
    netSpeed: netSpeed !== null && netSpeed !== undefined ? Number(netSpeed).toFixed(1) : null,
    lowestCorridor,
    lowestSpeed: lowestSpeed !== null && lowestSpeed !== undefined ? Number(lowestSpeed).toFixed(1) : null,
    waitingTime: waitingTime !== null && waitingTime !== undefined ? Number(waitingTime).toFixed(1) : null,
    delay: delay !== null && delay !== undefined ? Number(delay).toFixed(1) : null,
    congestion: congestion !== null && congestion !== undefined ? `${(congestion * 100).toFixed(1)}%` : null,
    activeVehicles,
    totalVehicles,
    throughput,
    bottlenecks,
    candidateInterventions: trf.candidate_interventions || [],
    corridors: trf.corridors || []
  }
}

function parseSimulationEvidence(res, promptText) {
  let allSims = []
  if (Array.isArray(res?.final_response?.tested_scenarios) && res.final_response.tested_scenarios.length > 0) {
    allSims = res.final_response.tested_scenarios
  } else if (Array.isArray(res?.agent_results?.simulations) && res.agent_results.simulations.length > 0) {
    allSims = res.agent_results.simulations
  } else if (Array.isArray(res?.agent_results?.simulation)) {
    allSims = res.agent_results.simulation
  } else if (res?.agent_results?.simulation && typeof res.agent_results.simulation === 'object') {
    allSims = [res.agent_results.simulation]
  }

  if (allSims.length === 0) return null

  const targetDur = resolveRequestedDuration(res, promptText)
  let sim = null
  if (targetDur && targetDur !== 'BOTH') {
    const matching = allSims.filter(s => getScenarioDuration(s) === targetDur)
    if (matching.length > 0) {
      sim = matching[matching.length - 1]
    } else {
      // Requested specific horizon but no matching experiment exists: do not substitute another horizon!
      return null
    }
  } else {
    sim = allSims[allSims.length - 1]
  }

  if (!sim) return null

  const comp = sim.comparison || res?.final_response?.comparison || res?.final_response?.metric_changes || {}
  const baseSummary = comp.baseline_summary || null
  const intSummary = comp.intervention_summary || sim.metrics || {}
  const intervention = sim.intervention_applied || sim.intervention || {}

  const isBaselineMissing = comp.status === 'baseline_missing' || !baseSummary || baseSummary.average_speed_kmh === null || baseSummary.average_speed_kmh === undefined
  const actualDur = getScenarioDuration(sim) || comp.baseline_duration_seconds || comp.intervention_duration_seconds || null

  return {
    scenarioId: sim.scenario_id,
    scenario: sim.scenario || comp.baseline_scenario || comp.intervention_scenario || 'synthetic_peak_westbound',
    durationSeconds: actualDur,
    seed: sim.seed ?? sim.metadata?.random_seed ?? comp.baseline_seed ?? comp.intervention_seed ?? null,
    interventionType: intervention.type || 'Intervention',
    interventionTarget: intervention.target || 'Corridor',
    isBaselineMissing,
    fairComparison: comp.fair_comparison ?? true,
    status: comp.status || (isBaselineMissing ? 'baseline_missing' : 'SUCCESS'),
    speedChangePct: comp.speed_change_pct,
    // NEW signed change fields (negative = improved for delay/waiting/congestion)
    delayChangePct: comp.delay_change_pct ?? null,
    waitingTimeChangePct: comp.waiting_time_change_pct ?? null,
    congestionChangePct: comp.congestion_change_pct ?? null,
    // Legacy reduction fields kept for backward compat
    delayReductionPct: comp.delay_reduction_pct,
    waitingTimeReductionPct: comp.waiting_time_reduction_pct,
    congestionReductionPct: comp.congestion_reduction_pct,
    throughputChange: comp.throughput_change,
    corridorComparisons: comp.corridor_comparisons || [],
    corridorTradeOffs: sim.corridor_trade_offs || comp.corridor_trade_offs || [],
    tradeOffSummary: sim.trade_off_summary || comp.trade_off_summary,
    baseline: baseSummary ? {
      speed: baseSummary.average_speed_kmh !== undefined && baseSummary.average_speed_kmh !== null ? Number(baseSummary.average_speed_kmh).toFixed(2) : null,
      delay: baseSummary.average_delay_sec !== undefined && baseSummary.average_delay_sec !== null ? Number(baseSummary.average_delay_sec).toFixed(2) : null,
      waiting: baseSummary.average_waiting_time_sec !== undefined && baseSummary.average_waiting_time_sec !== null ? Number(baseSummary.average_waiting_time_sec).toFixed(2) : null,
      congestion: baseSummary.congestion_index !== undefined && baseSummary.congestion_index !== null ? `${(baseSummary.congestion_index * 100).toFixed(1)}%` : null,
      throughput: baseSummary.throughput ?? null
    } : null,
    intervention: {
      speed: intSummary.average_speed_kmh !== undefined && intSummary.average_speed_kmh !== null ? Number(intSummary.average_speed_kmh).toFixed(2) : null,
      delay: intSummary.average_delay_sec !== undefined && intSummary.average_delay_sec !== null ? Number(intSummary.average_delay_sec).toFixed(2) : null,
      waiting: intSummary.average_waiting_time_sec !== undefined && intSummary.average_waiting_time_sec !== null ? Number(intSummary.average_waiting_time_sec).toFixed(2) : null,
      congestion: intSummary.congestion_index !== undefined && intSummary.congestion_index !== null ? `${(intSummary.congestion_index * 100).toFixed(1)}%` : null,
      throughput: intSummary.throughput ?? null
    }
  }
}

export default function Planning() {
  const { session, updateSession, clearSession } = usePlanner()
  const conversation = session.conversation
  const [query, setQuery] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [errorMessage, setErrorMessage] = useState(null)
  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [conversation, isProcessing, errorMessage])

  const handleSendPrompt = async (promptToSend) => {
    const text = (promptToSend || query).trim()
    if (!text || isProcessing) return

    setErrorMessage(null)
    setIsProcessing(true)

    // Append user query to UI conversation immediately
    const userTurn = {
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString()
    }
    const updatedHistory = [...conversation, userTurn]
    updateSession(prev => ({ ...prev, conversation: updatedHistory }))
    setQuery('')

    try {
      // Build structured conversation history format expected by backend
      const historyForBackend = conversation.map(turn => ({
        role: turn.role,
        content: turn.content,
        simulations: turn.simulations || undefined,
        tested_scenarios: turn.tested_scenarios || undefined,
        tested_interventions: turn.testedInterventions || undefined,
        untested_candidates: turn.untestedCandidates || undefined,
        traffic_evidence: turn.trafficEvidence || undefined,
        simulation_evidence: turn.simulationEvidence || undefined,
        evidence_status: turn.evidenceStatus || undefined
      }))

      // Frontend -> Planner API (POST /agents/planner/execute)
      const res = await planningApi.executePlanner({
        query: text,
        objective: text,
        location: 'Narayanguda, Hyderabad',
        session_id: session.sessionId,
        conversation_history: historyForBackend,
        simulation_history: session.simulationHistory?.length > 0 ? session.simulationHistory : undefined,
        tested_scenarios: session.testedScenarios?.length > 0 ? session.testedScenarios : undefined,
        max_cycles: 2
      })

      // Extract real LLM reasoning and real evidence
      const finalResp = res.final_response || {}
      const feedback = res.planner_feedback || {}
      const insights = feedback.insights || {}

      // Extract raw simulations
      const newSims = []
      if (Array.isArray(res.agent_results?.simulations)) {
        newSims.push(...res.agent_results.simulations)
      } else if (res.agent_results?.simulation) {
        if (Array.isArray(res.agent_results.simulation)) {
          newSims.push(...res.agent_results.simulation)
        } else if (typeof res.agent_results.simulation === 'object') {
          newSims.push(res.agent_results.simulation)
        }
      }
      if (Array.isArray(finalResp.tested_scenarios)) {
        newSims.push(...finalResp.tested_scenarios)
      }

      // Merge simulations into simulationHistory by duration-aware composite identity
      const mergedSims = [...(session.simulationHistory || [])]
      for (const sim of newSims) {
        const key = getSimulationKey(sim)
        if (key) {
          const idx = mergedSims.findIndex(existing => getSimulationKey(existing) === key)
          if (idx >= 0) {
            mergedSims[idx] = sim
          } else {
            mergedSims.push(sim)
          }
        } else {
          mergedSims.push(sim)
        }
      }

      const testedScenarios = Array.isArray(finalResp.tested_scenarios) && finalResp.tested_scenarios.length > 0
        ? finalResp.tested_scenarios
        : (session.testedScenarios || [])

      // Persistent TESTED interventions never regress
      const newTested = finalResp.tested_interventions || []
      const mergedTested = Array.from(new Set([...(session.testedInterventions || []), ...newTested]))
      const newUntested = (finalResp.untested_candidates || []).filter(c => !mergedTested.includes(c))

      // Deterministic evidence status based on historical completed simulations
      const evidenceStatus = mergedSims.length >= 2
        ? 'EVIDENCE: MULTI-SIMULATION EVALUATION'
        : (mergedSims.length === 1
          ? 'EVIDENCE: SINGLE SIMULATION RUN'
          : (finalResp.evidence_status || res.evidence_status || session.evidenceStatus || 'EVIDENCE: OBSERVATIONAL'))

      const summary = finalResp.summary || insights.analysis || 'Analysis completed.'
      const recommendation = finalResp.recommendation || insights.recommendation || ''
      const decision = finalResp.decision || feedback.decision || res.status || 'COMPLETED'

      const trafficEv = parseTrafficEvidence(res)
      const simEv = parseSimulationEvidence(res, text)
      const multiComp = parseMultiSimulationComparison(res, text)

      const assistantTurn = {
        role: 'assistant',
        content: summary,
        recommendation,
        decision,
        evidenceStatus,
        testedInterventions: mergedTested,
        untestedCandidates: newUntested,
        trafficEvidence: trafficEv,
        simulationEvidence: simEv,
        multiInterventionComparison: multiComp,
        dispatchedAgents: res.dispatched_agents || [],
        simulations: mergedSims,
        tested_scenarios: testedScenarios,
        timestamp: new Date().toLocaleTimeString()
      }

      const nextConversation = [...updatedHistory, assistantTurn]
      updateSession({
        sessionId: session.sessionId,
        conversation: nextConversation,
        simulationHistory: mergedSims,
        testedScenarios,
        testedInterventions: mergedTested,
        untestedCandidates: newUntested,
        evidenceStatus,
        baselineMetadata: res.agent_results?.traffic?.metrics || session.baselineMetadata
      })
    } catch (err) {
      console.error('Planner call failed:', err)
      setErrorMessage(err.message || 'Unable to retrieve traffic evidence.')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleClear = () => {
    clearSession()
    setErrorMessage(null)
    setQuery('')
  }

  return (
    <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* Page Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Brain size={28} color="var(--accent-traffic)" />
            Smart City Planner
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Central LLM Decision Authority connected to real SUMO Traffic Agent telemetry & simulation
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="badge badge-ai" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
            Sole Decision Authority
          </span>
          <span className="badge badge-info" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
            Narayanguda Network
          </span>
        </div>
      </div>

      {/* Main Interactive Planner Section */}
      <GlassCard glow="cyan">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
          <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
            <Sparkles size={18} color="var(--accent-traffic)" />
            Ask the Smart City Planner...
          </div>
          {conversation.length > 0 && (
            <button
              onClick={handleClear}
              disabled={isProcessing}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '4px 10px', background: 'transparent',
                border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)', fontSize: '0.75rem', cursor: 'pointer'
              }}
            >
              <RefreshCw size={12} /> Clear Conversation
            </button>
          )}
        </div>

        {/* Natural Language Prompt Input */}
        <div style={{ position: 'relative', marginBottom: '14px' }}>
          <textarea
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSendPrompt()
              }
            }}
            placeholder="Ask anything about Narayanguda traffic (e.g., 'What is the traffic situation in Narayanguda?' or 'Which corridor is the bottleneck?')..."
            style={{
              width: '100%', minHeight: '90px', padding: '14px',
              background: 'var(--bg-input)', border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)', color: 'var(--text-primary)',
              fontFamily: 'var(--font-body)', fontSize: '0.9rem', resize: 'vertical',
              outline: 'none', transition: 'border-color var(--transition-fast)'
            }}
            onFocus={e => e.currentTarget.style.borderColor = 'var(--accent-traffic)'}
            onBlur={e => e.currentTarget.style.borderColor = 'var(--border-default)'}
          />
        </div>

        {/* Quick Sample Prompts */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '8px', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>
            Interactive Prompts
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {samplePrompts.map((promptText, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setQuery(promptText)
                }}
                disabled={isProcessing}
                style={{
                  padding: '6px 12px', background: 'var(--bg-card)',
                  border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                  color: 'var(--text-secondary)', fontSize: '0.75rem', cursor: 'pointer',
                  transition: 'all var(--transition-fast)'
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-traffic)'; e.currentTarget.style.color = 'var(--text-primary)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-default)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
              >
                {promptText}
              </button>
            ))}
          </div>
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Press Enter or click Send
          </span>
          <button
            onClick={() => handleSendPrompt()}
            disabled={isProcessing || !query.trim()}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 24px',
              background: isProcessing || !query.trim() ? 'var(--bg-tertiary)' : 'var(--accent-traffic)',
              color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem', fontWeight: 600,
              cursor: isProcessing || !query.trim() ? 'not-allowed' : 'pointer',
              transition: 'background var(--transition-fast)'
            }}
          >
            {isProcessing ? (
              <>
                <RefreshCw size={16} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
                <span>Planner is analyzing traffic conditions...</span>
              </>
            ) : (
              <>
                <Send size={16} />
                <span>Send</span>
              </>
            )}
          </button>
        </div>
      </GlassCard>

      {/* Honest Error State */}
      {errorMessage && (
        <GlassCard style={{ borderColor: 'var(--accent-warning)', background: 'var(--accent-warning-dim)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
            <AlertCircle size={22} color="var(--accent-warning)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{ fontWeight: 600, color: 'var(--accent-warning)', fontSize: '0.9rem' }}>
                Unable to retrieve traffic evidence.
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {errorMessage}
              </div>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Processing Indicator */}
      {isProcessing && (
        <GlassCard style={{ display: 'flex', alignItems: 'center', gap: '14px', borderStyle: 'dashed' }}>
          <div style={{
            width: 32, height: 32, borderRadius: '50%',
            border: '3px solid var(--accent-traffic-dim)', borderTopColor: 'var(--accent-traffic)',
            animation: 'spin 1s linear infinite'
          }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
              Planner is analyzing traffic conditions...
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Dispatching real Traffic Agent, evaluating TraCI telemetry, and synthesizing LLM reasoning.
            </div>
          </div>
        </GlassCard>
      )}

      {/* Conversation Stream */}
      {conversation.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
          {conversation.map((turn, index) => (
            <div key={index}>
              {turn.role === 'user' ? (
                /* User Prompt Bubble */
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
                  <div style={{
                    maxWidth: '80%', padding: '12px 18px',
                    background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-md) var(--radius-md) 0 var(--radius-md)',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.03)'
                  }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '4px', fontFamily: 'var(--font-mono)' }}>
                      YOU • {turn.timestamp}
                    </div>
                    <div style={{ fontSize: '0.9rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                      {turn.content}
                    </div>
                  </div>
                </div>
              ) : (
                /* Planner Response Card */
                <GlassCard glow="cyan" style={{ marginBottom: '8px' }}>
                  {/* Card Header */}
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    borderBottom: '1px solid var(--border-default)', paddingBottom: '10px', marginBottom: '14px'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Brain size={18} color="var(--accent-traffic)" />
                      <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                        Smart City Planner Response
                      </span>
                      <span className="badge badge-smooth" style={{ fontSize: '0.65rem' }}>
                        {turn.decision || 'COMPLETED'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="badge badge-smooth" style={{
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        fontFamily: 'var(--font-mono)',
                        padding: '3px 8px',
                        borderRadius: '4px',
                        background: turn.evidenceStatus?.includes('MULTI') ? 'rgba(16, 185, 129, 0.15)' : (
                          turn.evidenceStatus?.includes('SINGLE') ? 'rgba(59, 130, 246, 0.15)' : 'rgba(245, 158, 11, 0.15)'
                        ),
                        color: turn.evidenceStatus?.includes('MULTI') ? '#10b981' : (
                          turn.evidenceStatus?.includes('SINGLE') ? '#60a5fa' : '#f59e0b'
                        ),
                        border: `1px solid ${turn.evidenceStatus?.includes('MULTI') ? 'rgba(16, 185, 129, 0.3)' : (
                          turn.evidenceStatus?.includes('SINGLE') ? 'rgba(59, 130, 246, 0.3)' : 'rgba(245, 158, 11, 0.3)'
                        )}`
                      }}>
                        {turn.evidenceStatus || 'EVIDENCE: OBSERVATIONAL'}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {turn.timestamp}
                      </span>
                    </div>
                  </div>

                  {/* Natural-Language Analysis */}
                  <div style={{ marginBottom: '14px' }}>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, fontFamily: 'var(--font-mono)', marginBottom: '4px', textTransform: 'uppercase' }}>
                      Reasoning & Analysis
                    </div>
                    <p style={{ fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.5, margin: 0 }}>
                      {turn.content}
                    </p>
                  </div>

                  {/* Tested vs Untested Interventions Badges */}
                  {((turn.testedInterventions && turn.testedInterventions.length > 0) || (turn.untestedCandidates && turn.untestedCandidates.length > 0)) && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '14px' }}>
                      {turn.testedInterventions?.map((t, idx) => (
                        <div key={`tested-${idx}`} style={{
                          display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem',
                          padding: '3px 8px', background: 'rgba(16, 185, 129, 0.1)',
                          border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '4px', color: '#10b981'
                        }}>
                          <span style={{ fontWeight: 800, fontSize: '0.62rem', background: '#10b981', color: '#000', padding: '1px 4px', borderRadius: '3px' }}>
                            TESTED
                          </span>
                          <span style={{ fontWeight: 500 }}>
                            {formatInterventionBadgeLabel(t)}
                          </span>
                        </div>
                      ))}
                      {turn.untestedCandidates?.map((u, idx) => (
                        <div key={`untested-${idx}`} style={{
                          display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem',
                          padding: '3px 8px', background: 'rgba(100, 116, 139, 0.1)',
                          border: '1px solid rgba(100, 116, 139, 0.25)', borderRadius: '4px', color: '#94a3b8'
                        }}>
                          <span style={{ fontWeight: 800, fontSize: '0.62rem', background: '#64748b', color: '#fff', padding: '1px 4px', borderRadius: '3px' }}>
                            UNTESTED
                          </span>
                          <span style={{ fontWeight: 500 }}>
                            {formatInterventionBadgeLabel(u)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Natural-Language Recommendation */}
                  {turn.recommendation && (
                    <div style={{
                      padding: '12px 14px', background: 'var(--accent-traffic-dim)',
                      borderRadius: 'var(--radius-sm)', border: '1px solid rgba(47,143,114,0.2)',
                      marginBottom: '16px'
                    }}>
                      <div style={{ fontSize: '0.7rem', color: 'var(--accent-traffic)', fontWeight: 700, fontFamily: 'var(--font-mono)', marginBottom: '4px', textTransform: 'uppercase' }}>
                        Proposed Recommendation
                      </div>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: 1.4, margin: 0, fontWeight: 500 }}>
                        {turn.recommendation}
                      </p>
                    </div>
                  )}

                  {/* Multi-Intervention Empirical Comparison Table */}
                  {turn.multiInterventionComparison && turn.multiInterventionComparison.length > 1 && (
                    <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-default)', paddingTop: '14px', marginBottom: '16px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <div style={{
                          fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)',
                          fontFamily: 'var(--font-mono)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '6px'
                        }}>
                          <BarChart3 size={14} color="var(--accent-traffic)" />
                          Multi-Intervention Empirical Comparison (Real SUMO)
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span className="badge badge-smooth" style={{ fontSize: '0.65rem', padding: '2px 6px', fontFamily: 'var(--font-mono)' }}>
                            {turn.multiInterventionComparison.scenario || 'synthetic_peak_westbound'} / {turn.multiInterventionComparison.durationSeconds ? (typeof turn.multiInterventionComparison.durationSeconds === 'number' ? `${turn.multiInterventionComparison.durationSeconds}s` : turn.multiInterventionComparison.durationSeconds) : 'Unknown duration'}
                            {turn.multiInterventionComparison.seed !== undefined && turn.multiInterventionComparison.seed !== null ? ` (Seed ${turn.multiInterventionComparison.seed})` : ''}
                          </span>
                          {turn.multiInterventionComparison.canonicalBaseline && (
                            <span className="badge badge-smooth" style={{ fontSize: '0.65rem', padding: '2px 6px', fontFamily: 'var(--font-mono)', background: 'var(--bg-card)' }}>
                              Baseline: {Number(turn.multiInterventionComparison.canonicalBaseline.average_speed_kmh ?? 0).toFixed(1)} km/h | {Number(turn.multiInterventionComparison.canonicalBaseline.average_delay_sec ?? 0).toFixed(1)}s delay
                            </span>
                          )}
                          <span style={{ fontSize: '0.65rem', color: turn.multiInterventionComparison.fairComparison === false ? 'var(--accent-warning)' : 'var(--text-muted)' }}>
                            {turn.multiInterventionComparison.fairComparison === false ? 'NOT FAIR PAIRED' : 'Fair Paired Comparison'}
                          </span>
                        </div>
                      </div>

                      <div style={{ overflowX: 'auto', marginBottom: '8px' }}>
                        <table style={{
                          width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem',
                          background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)'
                        }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left', color: 'var(--text-muted)' }}>
                              <th style={{ padding: '8px 10px' }}>Tested Intervention</th>
                              <th style={{ padding: '8px 10px' }}>Target Corridor Speed</th>
                              <th style={{ padding: '8px 10px' }}>Network Speed</th>
                              <th style={{ padding: '8px 10px' }}>Network Delay</th>
                              <th style={{ padding: '8px 10px' }}>Waiting Time</th>
                              <th style={{ padding: '8px 10px' }}>Observed Trade-offs</th>
                            </tr>
                          </thead>
                          <tbody>
                            {turn.multiInterventionComparison.map((row, idx) => (
                              <tr key={idx} style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                <td style={{ padding: '8px 10px', fontWeight: 600, color: 'var(--text-primary)' }}>
                                  {row.intervention}
                                </td>
                                <td style={{
                                  padding: '8px 10px', fontWeight: 600,
                                  color: (row.targetSpeedDelta ?? 0) > 0 ? 'var(--accent-emerald)' : ((row.targetSpeedDelta ?? 0) < 0 ? 'var(--accent-warning)' : 'var(--text-secondary)')
                                }}>
                                  {row.targetSpeedText}
                                </td>
                                <td style={{
                                  padding: '8px 10px',
                                  color: (row.netSpeedDelta ?? 0) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)'
                                }}>
                                  {row.netSpeedText}
                                </td>
                                <td style={{
                                  padding: '8px 10px',
                                  color: (row.delayChangePct ?? 0) <= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)'
                                }}>
                                  {row.delayText}
                                </td>
                                <td style={{
                                  padding: '8px 10px',
                                  color: (row.waitingChangePct ?? 0) <= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)'
                                }}>
                                  {row.waitingText}
                                </td>
                                <td style={{
                                  padding: '8px 10px', fontSize: '0.7rem',
                                  color: row.hasTradeOffs ? 'var(--accent-warning)' : 'var(--text-muted)'
                                }}>
                                  {row.tradeOffsText}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Real Traffic Evidence Section */}
                  {turn.trafficEvidence && (
                    <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-default)', paddingTop: '14px' }}>
                      <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'
                      }}>
                        <div style={{
                          fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)',
                          fontFamily: 'var(--font-mono)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '6px'
                        }}>
                          <Activity size={14} color="var(--accent-traffic)" />
                          Traffic Evidence (from Real Traffic Agent)
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span className="badge badge-smooth" style={{ fontSize: '0.65rem', padding: '2px 6px', fontFamily: 'var(--font-mono)' }}>
                            {turn.trafficEvidence.scenario || 'synthetic_peak_westbound'} / {turn.trafficEvidence.durationSeconds ? `${turn.trafficEvidence.durationSeconds}s` : 'Unknown duration'}
                            {turn.trafficEvidence.seed !== undefined && turn.trafficEvidence.seed !== null ? ` • Seed ${turn.trafficEvidence.seed}` : ''}
                          </span>
                          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                            SUMO Narayanguda Telemetry
                          </span>
                        </div>
                      </div>

                      {/* Compact Metric Grid */}
                      <div style={{
                        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                        gap: '10px', marginBottom: '12px'
                      }}>
                        <div style={{ padding: '10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>NETWORK SPEED</div>
                          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                            {turn.trafficEvidence.netSpeed !== null ? `${turn.trafficEvidence.netSpeed} km/h` : '—'}
                          </div>
                        </div>

                        <div style={{ padding: '10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>LOWEST SPEED</div>
                          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-warning)', marginTop: '2px' }}>
                            {turn.trafficEvidence.lowestSpeed !== null ? `${turn.trafficEvidence.lowestSpeed} km/h` : '—'}
                          </div>
                          {turn.trafficEvidence.lowestCorridor && (
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                              on {turn.trafficEvidence.lowestCorridor}
                            </div>
                          )}
                        </div>

                        <div style={{ padding: '10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>WAITING TIME</div>
                          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                            {turn.trafficEvidence.waitingTime !== null ? `${turn.trafficEvidence.waitingTime} sec` : '—'}
                          </div>
                        </div>

                        <div style={{ padding: '10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>DELAY</div>
                          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                            {turn.trafficEvidence.delay !== null ? `${turn.trafficEvidence.delay} sec` : '—'}
                          </div>
                        </div>

                        <div style={{ padding: '10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)' }}>
                          <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>CONGESTION</div>
                          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                            {turn.trafficEvidence.congestion ?? '—'}
                          </div>
                        </div>
                      </div>

                      {/* Corridors breakdown if available */}
                      {turn.trafficEvidence.corridors && turn.trafficEvidence.corridors.length > 0 && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                          <strong style={{ color: 'var(--text-primary)' }}>Corridor Speeds: </strong>
                          {turn.trafficEvidence.corridors.map(c => `${c.name}: ${c.avg_speed !== null ? c.avg_speed + ' km/h' : 'N/A'}`).join(' • ')}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Single-Run Simulation Results Section */}
                  {turn.simulationEvidence && (
                    <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-default)', paddingTop: '14px' }}>
                      <div style={{
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px'
                      }}>
                        <div style={{
                          fontSize: '0.75rem', fontWeight: 700, color: 'var(--accent-traffic)',
                          fontFamily: 'var(--font-mono)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '6px'
                        }}>
                          <Gauge size={14} color="var(--accent-traffic)" />
                          Intervention Simulation Results ({turn.simulationEvidence.interventionType} on {turn.simulationEvidence.interventionTarget})
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span className="badge badge-smooth" style={{ fontSize: '0.65rem', padding: '2px 6px', fontFamily: 'var(--font-mono)' }}>
                            {turn.simulationEvidence.scenario || 'synthetic_peak_westbound'} / {turn.simulationEvidence.durationSeconds ? `${turn.simulationEvidence.durationSeconds}s` : 'Unknown duration'}
                            {turn.simulationEvidence.seed !== undefined && turn.simulationEvidence.seed !== null ? ` • Seed ${turn.simulationEvidence.seed}` : ''}
                            {turn.simulationEvidence.fairComparison !== undefined ? ` • ${turn.simulationEvidence.fairComparison ? 'Fair Paired' : 'Not Fair'}` : ''}
                          </span>
                          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                            SUMO Microsimulation
                          </span>
                        </div>
                      </div>

                      {/* Comparison Content */}
                      {turn.simulationEvidence.isBaselineMissing ? (
                        <div style={{
                          padding: '12px 14px',
                          background: 'rgba(239, 68, 68, 0.08)',
                          border: '1px solid rgba(239, 68, 68, 0.25)',
                          borderRadius: 'var(--radius-sm)',
                          color: '#f87171',
                          fontSize: '0.8rem',
                          marginBottom: '10px'
                        }}>
                          <strong>Comparison unavailable</strong> — baseline evidence was not supplied.
                        </div>
                      ) : (
                        <>
                          {/* Comparison Table */}
                          <div style={{ overflowX: 'auto', marginBottom: '10px' }}>
                            <table style={{
                              width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem',
                              background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)'
                            }}>
                              <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left', color: 'var(--text-muted)' }}>
                                  <th style={{ padding: '8px 10px' }}>Metric</th>
                                  <th style={{ padding: '8px 10px' }}>Baseline</th>
                                  <th style={{ padding: '8px 10px' }}>Intervention</th>
                                  <th style={{ padding: '8px 10px' }}>Change</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                  <td style={{ padding: '8px 10px', fontWeight: 500 }}>Network Speed</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.baseline?.speed ? `${turn.simulationEvidence.baseline.speed} km/h` : '—'}</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.intervention?.speed ? `${turn.simulationEvidence.intervention.speed} km/h` : '—'}</td>
                                  <td style={{ padding: '8px 10px', fontWeight: 600, color: (turn.simulationEvidence.speedChangePct ?? 0) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)' }}>
                                    {turn.simulationEvidence.speedChangePct !== null && turn.simulationEvidence.speedChangePct !== undefined
                                      ? `${turn.simulationEvidence.speedChangePct > 0 ? '+' : ''}${turn.simulationEvidence.speedChangePct}%`
                                      : '—'}
                                  </td>
                                </tr>
                                <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                  <td style={{ padding: '8px 10px', fontWeight: 500 }}>Waiting Time</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.baseline?.waiting ? `${turn.simulationEvidence.baseline.waiting} sec` : '—'}</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.intervention?.waiting ? `${turn.simulationEvidence.intervention.waiting} sec` : '—'}</td>
                                  <td style={{ padding: '8px 10px', fontWeight: 600, color: (turn.simulationEvidence.waitingTimeChangePct ?? 0) <= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)' }}>
                                    {turn.simulationEvidence.waitingTimeChangePct !== null && turn.simulationEvidence.waitingTimeChangePct !== undefined
                                      ? `${turn.simulationEvidence.waitingTimeChangePct > 0 ? '+' : ''}${turn.simulationEvidence.waitingTimeChangePct}%`
                                      : '—'}
                                  </td>
                                </tr>
                                <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                  <td style={{ padding: '8px 10px', fontWeight: 500 }}>Delay</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.baseline?.delay ? `${turn.simulationEvidence.baseline.delay} sec` : '—'}</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.intervention?.delay ? `${turn.simulationEvidence.intervention.delay} sec` : '—'}</td>
                                  <td style={{ padding: '8px 10px', fontWeight: 600, color: (turn.simulationEvidence.delayChangePct ?? 0) <= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)' }}>
                                    {turn.simulationEvidence.delayChangePct !== null && turn.simulationEvidence.delayChangePct !== undefined
                                      ? `${turn.simulationEvidence.delayChangePct > 0 ? '+' : ''}${turn.simulationEvidence.delayChangePct}%`
                                      : '—'}
                                  </td>
                                </tr>
                                <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                  <td style={{ padding: '8px 10px', fontWeight: 500 }}>Congestion Index</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.baseline?.congestion ?? '—'}</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.intervention?.congestion ?? '—'}</td>
                                  <td style={{ padding: '8px 10px', fontWeight: 600, color: (turn.simulationEvidence.congestionChangePct ?? 0) <= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)' }}>
                                    {turn.simulationEvidence.congestionChangePct !== null && turn.simulationEvidence.congestionChangePct !== undefined
                                      ? `${turn.simulationEvidence.congestionChangePct > 0 ? '+' : ''}${turn.simulationEvidence.congestionChangePct}%`
                                      : '—'}
                                  </td>
                                </tr>
                                <tr>
                                  <td style={{ padding: '8px 10px', fontWeight: 500 }}>Throughput (Arrivals)</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.baseline?.throughput ?? '—'} veh</td>
                                  <td style={{ padding: '8px 10px' }}>{turn.simulationEvidence.intervention?.throughput ?? '—'} veh</td>
                                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>
                                    {turn.simulationEvidence.throughputChange !== null && turn.simulationEvidence.throughputChange !== undefined
                                      ? `${turn.simulationEvidence.throughputChange >= 0 ? '+' : ''}${turn.simulationEvidence.throughputChange} veh`
                                      : '—'}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>

                          {/* Corridor-by-Corridor Speed Comparisons */}
                          {turn.simulationEvidence.corridorComparisons && turn.simulationEvidence.corridorComparisons.length > 0 && (
                            <div style={{ marginTop: '12px' }}>
                              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontWeight: 600, fontFamily: 'var(--font-mono)', marginBottom: '6px', textTransform: 'uppercase' }}>
                                Corridor-Level Speed Comparisons
                              </div>
                              <div style={{ overflowX: 'auto', marginBottom: '10px' }}>
                                <table style={{
                                  width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem',
                                  background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)'
                                }}>
                                  <thead>
                                    <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left', color: 'var(--text-muted)' }}>
                                      <th style={{ padding: '6px 10px' }}>Corridor</th>
                                      <th style={{ padding: '6px 10px' }}>Baseline</th>
                                      <th style={{ padding: '6px 10px' }}>Intervention</th>
                                      <th style={{ padding: '6px 10px' }}>Speed Delta</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {turn.simulationEvidence.corridorComparisons.map(c => (
                                      <tr key={c.id} style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                        <td style={{ padding: '6px 10px', fontWeight: 500 }}>{c.name}</td>
                                        <td style={{ padding: '6px 10px' }}>{c.baseline_speed_kmh !== null && c.baseline_speed_kmh !== undefined ? `${Number(c.baseline_speed_kmh).toFixed(1)} km/h` : '—'}</td>
                                        <td style={{ padding: '6px 10px' }}>{c.intervention_speed_kmh !== null && c.intervention_speed_kmh !== undefined ? `${Number(c.intervention_speed_kmh).toFixed(1)} km/h` : '—'}</td>
                                        <td style={{
                                          padding: '6px 10px', fontWeight: 600,
                                          color: (c.speed_change_pct ?? 0) > 0 ? 'var(--accent-emerald)' : ((c.speed_change_pct ?? 0) < 0 ? 'var(--accent-warning)' : 'var(--text-secondary)')
                                        }}>
                                          {c.speed_change_pct !== null && c.speed_change_pct !== undefined
                                            ? `${c.speed_change_pct > 0 ? '+' : ''}${c.speed_change_pct}% (${c.speed_change_kmh > 0 ? '+' : ''}${c.speed_change_kmh} km/h)`
                                            : '—'}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}
                        </>
                      )}

                      {/* Trade-off Summary */}
                      {turn.simulationEvidence.tradeOffSummary && (
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                          <strong style={{ color: 'var(--text-primary)' }}>Trade-off Analysis: </strong>
                          {turn.simulationEvidence.tradeOffSummary}
                        </div>
                      )}
                    </div>
                  )}
                </GlassCard>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      ) : (
        /* Empty State */
        <GlassCard style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 20px', borderStyle: 'dashed' }}>
          <Brain size={48} color="var(--text-muted)" style={{ opacity: 0.35, marginBottom: '14px' }} />
          <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '4px' }}>
            Awaiting Natural-Language Question
          </h3>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', maxWidth: '420px', margin: 0 }}>
            Type a question above or click one of the interactive prompt chips. The LLM Planner will query real SUMO traffic evidence and provide reasoning.
          </p>
        </GlassCard>
      )}

      {/* Urban Problems & Cross-Domain Solutions */}
      <ProblemSolverSection />
    </div>
  )
}

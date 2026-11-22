import { useState, useRef, useEffect } from 'react'
import {
  Brain, Send, Cpu, AlertCircle, CheckCircle2,
  Play, RefreshCw, BarChart3, Activity, Gauge, CloudRain,
  Clock, ArrowRight, ShieldCheck, Sparkles, TrendingUp, TrendingDown,
  ChevronDown, ChevronUp, Database, Wind, Compass, Zap, Flame, ShieldAlert,
  Calendar, Check, AlertTriangle, Layers
} from 'lucide-react'
import GlassCard from '../components/GlassCard'
import StatusBadge from '../components/StatusBadge'
import { planningApi } from '../services/api'
import { usePlanner } from '../context/PlannerContext'

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

function getOperationalStatusLabel(status, evidenceStatus, testedInterventions) {
  const ev = (evidenceStatus || '').toUpperCase()
  if (ev.includes('MULTI-SIM') || (Array.isArray(testedInterventions) && testedInterventions.length >= 2)) {
    return 'Simulation Completed (Multi-Scenario)'
  }
  if (ev.includes('SINGLE SIMULATION') || (Array.isArray(testedInterventions) && testedInterventions.length === 1)) {
    return 'Simulation Completed (Single-Run)'
  }
  if (ev.includes('MODELLED')) {
    return 'Modelled Estimate'
  }
  if (ev.includes('MULTI-SOURCE')) {
    return 'Multi-Source Telemetry & Model'
  }
  if (ev.includes('API-SOURCED') || ev.includes('OBSERVATIONAL')) {
    return 'Live Telemetry Available'
  }
  if (status === 'SIMULATION_REQUIRED') {
    return 'Simulation Pending'
  }
  return 'Current Assessment'
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
    let target = intApplied.target || ''
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
      const match = comp.corridor_comparisons.find(c =>
        c.is_target ||
        (target && (c.name === target || c.name?.toLowerCase().includes(target.toLowerCase()) || String(c.id || '').toUpperCase().endsWith(String(target).slice(0, 2).toUpperCase())))
      )
      if (match) {
        if (!target && match.name) target = match.name
        if (tgtSpdDelta === undefined || tgtSpdDelta === null) tgtSpdDelta = match.speed_change_pct
        tgtSpdVal = match.intervention_speed_kmh
      }
    }

    // Use NEW signed *_change_pct fields (negative = improved for delay/waiting/congestion)
    const netSpdDelta = comp.speed_change_pct
    const netSpdVal = comp.intervention_summary?.average_speed_kmh ?? scen.metrics?.average_speed_kmh
    let delayChangePct = comp.delay_change_pct ?? null
    if (delayChangePct === null && comp.delay_reduction_pct !== undefined && comp.delay_reduction_pct !== null) {
      delayChangePct = -comp.delay_reduction_pct
    }
    const delayVal = comp.intervention_summary?.average_delay_sec ?? scen.metrics?.average_delay_sec
    let waitChangePct = comp.waiting_time_change_pct ?? null
    if (waitChangePct === null && comp.waiting_time_reduction_pct !== undefined && comp.waiting_time_reduction_pct !== null) {
      waitChangePct = -comp.waiting_time_reduction_pct
    }
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
  const freeFlowSpeed = metrics.free_flow_speed_kmh ?? trf.free_flow_speed_kmh ?? obs.free_flow_speed_kmh ?? 50.0
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

  const isObserved = (trf.source_type || trf.source?.type) === 'observed' || (trf.source_provider || trf.source?.provider) === 'tomtom'

  const waitingTime = isObserved ? null : (metrics.average_waiting_time_sec ?? trf.average_waiting_time_sec ?? obs.average_waiting_time_sec)
  const delay = metrics.average_delay_sec ?? trf.average_delay_sec ?? obs.average_delay_sec
  const congestion = metrics.congestion_index ?? trf.congestion_index ?? obs.congestion_index
  const speedDeficitPct = netSpeed !== null && freeFlowSpeed ? Math.max(0, Math.round((1 - (Number(netSpeed) / freeFlowSpeed)) * 100)) : null
  const totalVehicles = metrics.total_vehicles ?? trf.total_vehicles ?? obs.total_vehicles
  const throughput = metrics.throughput ?? trf.throughput ?? obs.throughput

  return {
    location: trf.location,
    sourceProvider: trf.source_provider || trf.source?.provider || 'tomtom',
    sourceType: trf.source_type || trf.source?.type || 'observed',
    scenario: trf.metadata?.demand_profile || trf.scenario || 'live_observed',
    durationSeconds: isObserved ? null : getScenarioDuration(trf),
    seed: isObserved ? null : (trf.metadata?.random_seed ?? trf.seed ?? null),
    netSpeed: netSpeed !== null && netSpeed !== undefined ? Number(netSpeed).toFixed(1) : null,
    freeFlowSpeed: freeFlowSpeed !== null && freeFlowSpeed !== undefined ? Number(freeFlowSpeed).toFixed(1) : null,
    speedDeficitPct,
    lowestCorridor,
    lowestSpeed: lowestSpeed !== null && lowestSpeed !== undefined ? Number(lowestSpeed).toFixed(1) : null,
    waitingTime: waitingTime !== null && waitingTime !== undefined ? Number(waitingTime).toFixed(1) : null,
    delay: delay !== null && delay !== undefined ? Number(delay).toFixed(1) : null,
    congestion: congestion !== null && congestion !== undefined ? `${(congestion * 100).toFixed(1)}%` : null,
    totalVehicles,
    throughput,
    bottlenecks,
    candidateInterventions: trf.candidate_interventions || [],
    corridors: trf.corridors || []
  }
}

function parsePollutionEvidence(res) {
  const pol = res?.agent_results?.pollution || res?.collected_results?.pollution
  if (!pol) return null

  const aqi = pol.city_avg_aqi ?? pol.aqi ?? null
  const pm25 = pol.pm25 !== null && pol.pm25 !== undefined ? Number(pol.pm25).toFixed(1) : null
  const pm10 = pol.pm10 !== null && pol.pm10 !== undefined ? Number(pol.pm10).toFixed(1) : null
  const stations = Array.isArray(pol.stations) ? pol.stations : []
  const interventions = Array.isArray(pol.suggested_interventions) ? pol.suggested_interventions : []
  const category = pol.category || (
    aqi !== null ? (
      aqi <= 50 ? 'Good' : (
        aqi <= 100 ? 'Moderate' : (
          aqi <= 200 ? 'Unhealthy' : 'Very Unhealthy'
        )
      )
    ) : 'Unknown'
  )

  const dataMode = pol.data_mode || 'historical'
  const dataSource = pol.data_source || (dataMode === 'current' ? 'open-meteo-air-quality-current' : 'open-meteo-air-quality-historical')
  const dataTimestamp = pol.data_timestamp || null
  const retrievedAt = pol.retrieved_at || null
  const pollutants = pol.pollutants || null
  const isModelled = pol.is_modelled !== false

  return {
    aqi,
    pm25,
    pm10,
    category,
    primaryPollutant: pol.primary_pollutant || 'PM2.5',
    stations,
    suggestedInterventions: interventions,
    location: pol.location || res?.location || res?.final_response?.location || null,
    dataMode,
    dataSource,
    dataTimestamp,
    retrievedAt,
    pollutants,
    isModelled,
    isCurrent: dataMode === 'current',
  }
}

function parseWeatherEvidence(res) {
  const wtr = res?.agent_results?.weather || res?.collected_results?.weather
  if (!wtr || typeof wtr !== 'object') return null

  const temp = wtr.temperature_c ?? null
  const feelsLike = wtr.feels_like_c ?? null
  const condition = wtr.condition || 'Clear'
  const humidity = wtr.humidity_pct ?? null
  const windSpeed = wtr.wind_speed_kmh ?? null
  const windDir = wtr.wind_direction || ''
  const precip = wtr.precipitation_mm ?? 0
  const pressure = wtr.pressure_hpa ?? null
  const uv = wtr.uv_index ?? null
  const visibility = wtr.visibility_km ?? null
  const location = wtr.city || wtr.location || res?.location || null
  const provider = wtr.provider || wtr.source || 'WeatherAPI / Open-Meteo'
  const timestamp = wtr.timestamp || null
  const forecast = Array.isArray(wtr.forecast_7d) ? wtr.forecast_7d : (Array.isArray(wtr.forecast_summary) ? wtr.forecast_summary : [])

  return {
    location,
    temperature: temp !== null && temp !== undefined ? Number(temp).toFixed(1) : null,
    feelsLike: feelsLike !== null && feelsLike !== undefined ? Number(feelsLike).toFixed(1) : null,
    condition,
    humidity,
    windSpeed: windSpeed !== null && windSpeed !== undefined ? Number(windSpeed).toFixed(1) : null,
    windDir,
    precip,
    pressure,
    uv,
    visibility,
    provider,
    timestamp,
    forecast: forecast.slice(0, 3)
  }
}

function parseEnergyEvidence(res) {
  const eng = res?.agent_results?.energy || res?.collected_results?.energy
  if (!eng || typeof eng !== 'object') return null

  const currentLoadMw = eng.current_load_mw !== null && eng.current_load_mw !== undefined ? Number(eng.current_load_mw) : null
  const capacityMw = eng.capacity_mw !== null && eng.capacity_mw !== undefined ? Number(eng.capacity_mw) : null
  const loadPct = eng.load_pct !== null && eng.load_pct !== undefined ? Number(eng.load_pct) : null
  const availableCapacityMw = (capacityMw !== null && currentLoadMw !== null) ? Math.max(0, Number((capacityMw - currentLoadMw).toFixed(1))) : null
  const solarGenMw = eng.solar_generation_mw !== null && eng.solar_generation_mw !== undefined ? Number(eng.solar_generation_mw) : null
  const totalConsumptionMwh = eng.total_consumption_mwh !== null && eng.total_consumption_mwh !== undefined ? Number(eng.total_consumption_mwh) : null
  const efficiencyScorePct = eng.efficiency_score_pct !== null && eng.efficiency_score_pct !== undefined ? Number(eng.efficiency_score_pct) : null
  const severity = eng.severity || 'NORMAL'
  const substations = Array.isArray(eng.substations) ? eng.substations : []
  const recommendations = Array.isArray(eng.recommendations) ? eng.recommendations : []
  const location = eng.location || res?.location || 'Hyderabad Central'
  const timestamp = eng.timestamp || null
  const rawSource = String(eng.source || '')

  // Honest Data Provenance Classification
  const isSynthetic = rawSource.toLowerCase().includes('synthetic') || Boolean(eng.is_synthetic)
  let provenanceLabel = 'API-Sourced Energy Telemetry'
  let provenanceType = 'API_SOURCED'
  if (isSynthetic) {
    provenanceLabel = 'Synthetic Baseline Model'
    provenanceType = 'SYNTHETIC_BASELINE'
  } else if (rawSource.toLowerCase().includes('live')) {
    provenanceLabel = 'Live Substation Telemetry (Energy Agent API)'
    provenanceType = 'LIVE_TELEMETRY'
  } else if (rawSource) {
    provenanceLabel = rawSource
    provenanceType = 'API_SOURCED'
  } else {
    provenanceLabel = 'Source Unavailable'
    provenanceType = 'UNAVAILABLE'
  }

  return {
    currentLoadMw,
    capacityMw,
    loadPct,
    availableCapacityMw,
    solarGenMw,
    totalConsumptionMwh,
    efficiencyScorePct,
    severity,
    substations,
    recommendations,
    location,
    timestamp,
    source: rawSource || 'Energy Agent API',
    provenanceLabel,
    provenanceType,
    isSynthetic,
    weatherImpactMw: eng.weather_impact_mw ?? null,
    evTrafficImpactMw: eng.ev_traffic_impact_mw ?? null
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
  const [expandedDetails, setExpandedDetails] = useState({})
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  const toggleDetails = (idx) => {
    setExpandedDetails(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }))
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [conversation, isProcessing, errorMessage])

  const handleTextareaChange = (e) => {
    setQuery(e.target.value)
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`
    }
  }

  const handleSendPrompt = async (promptToSend) => {
    const text = (promptToSend || query).trim()
    if (!text || isProcessing) return

    setErrorMessage(null)
    setIsProcessing(true)

    const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
    const conversationId = session.conversationId || session.sessionId

    // Append user query to UI conversation immediately
    const userTurn = {
      role: 'user',
      content: text,
      requestId,
      conversationId,
      timestamp: new Date().toLocaleTimeString()
    }
    const updatedHistory = [...conversation, userTurn]
    updateSession(prev => ({ ...prev, conversation: updatedHistory }))
    setQuery('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    try {
      // Build structured conversation history format expected by backend
      const historyForBackend = conversation.map(turn => ({
        role: turn.role,
        content: turn.content,
        location: turn.location || undefined,
        simulations: turn.simulations || undefined,
        tested_scenarios: turn.tested_scenarios || undefined,
        tested_interventions: turn.testedInterventions || undefined,
        untested_candidates: turn.untestedCandidates || undefined,
        traffic_evidence: turn.trafficEvidence || undefined,
        pollution_evidence: turn.pollutionEvidence || undefined,
        simulation_evidence: turn.simulationEvidence || undefined,
        evidence_status: turn.evidenceStatus || undefined
      }))

      // Frontend -> Planner API (POST /agents/planner/execute)
      const res = await planningApi.executePlanner({
        request_id: requestId,
        conversation_id: conversationId,
        session_id: conversationId,
        query: text,
        objective: text,
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

      // Authoritative evidence status from backend supervisor (preserves honest evidence provenance)
      const evidenceStatus = finalResp.evidence_status || res.evidence_status || (
        mergedSims.length >= 2
          ? 'EVIDENCE: MULTI-SIMULATION EVALUATION'
          : (mergedSims.length === 1
            ? 'EVIDENCE: SINGLE SIMULATION RUN'
            : (session.evidenceStatus || 'EVIDENCE: OBSERVATIONAL'))
      )

      const summary = finalResp.summary || insights.analysis || 'Analysis completed.'
      const recommendation = finalResp.recommendation || insights.recommendation || ''
      const decision = finalResp.decision || feedback.decision || res.status || 'COMPLETED'

      const trafficEv = parseTrafficEvidence(res)
      const pollutionEv = parsePollutionEvidence(res)
      const weatherEv = parseWeatherEvidence(res)
      const energyEv = parseEnergyEvidence(res)
      const simEv = parseSimulationEvidence(res, text)
      const multiComp = parseMultiSimulationComparison(res, text)
      const runtimeInfo = res.runtime || null

      const resolvedLocation = res.location || finalResp.location || (trafficEv ? trafficEv.location : null) || (pollutionEv ? pollutionEv.location : null) || (weatherEv ? weatherEv.location : null) || (energyEv ? energyEv.location : null) || session.lastLocality

      const assistantTurn = {
        role: 'assistant',
        content: summary,
        recommendation,
        decision,
        evidenceStatus,
        location: resolvedLocation,
        requestId: res.request_id || requestId,
        conversationId,
        testedInterventions: mergedTested,
        untestedCandidates: newUntested,
        trafficEvidence: trafficEv,
        pollutionEvidence: pollutionEv,
        weatherEvidence: weatherEv,
        energyEvidence: energyEv,
        simulationEvidence: simEv,
        multiInterventionComparison: multiComp,
        runtime: runtimeInfo,
        dispatchedAgents: res.dispatched_agents || [],
        simulations: mergedSims,
        tested_scenarios: testedScenarios,
        timestamp: new Date().toLocaleTimeString()
      }

      // Also backfill location on the user turn
      userTurn.location = resolvedLocation

      const nextConversation = [...updatedHistory, assistantTurn]
      updateSession({
        conversationId,
        sessionId: conversationId,
        lastLocality: resolvedLocation,
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
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      minHeight: 'calc(100vh - 140px)',
      position: 'relative',
    }}>
      {/* Page Header */}
      <div className="page-header" style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 'var(--space-md)',
        flexShrink: 0
      }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Brain size={28} color="var(--accent-traffic)" />
            Smart City Planner
          </h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Central LLM Decision Authority connected to real SUMO Traffic Agent telemetry & simulation
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          {conversation.length > 0 && (
            <button
              onClick={handleClear}
              disabled={isProcessing}
              title="Reset conversation"
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '5px 12px', background: 'var(--bg-card)',
                border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                color: 'var(--text-secondary)', fontSize: '0.75rem', cursor: 'pointer',
                transition: 'all var(--transition-fast)'
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-warning)'; e.currentTarget.style.color = 'var(--accent-warning)' }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-default)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
            >
              <RefreshCw size={12} /> Clear Chat
            </button>
          )}
          <span className="badge badge-ai" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
            Sole Decision Authority
          </span>
          <span className="badge badge-info" style={{ fontSize: '0.75rem', padding: '4px 10px' }}>
            {session.lastLocality ? `${session.lastLocality.replace(/,\s*Hyderabad/i, '')} Network` : 'Hyderabad Network'}
          </span>
        </div>
      </div>

      {/* Main Conversation Area */}
      <div style={{
        flex: 1,
        width: '100%',
        maxWidth: '1000px',
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-md)',
        paddingBottom: '140px',
      }}>
        {conversation.length === 0 ? (
          /* Clean ChatGPT-inspired Welcome Hero */
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '44vh',
            textAlign: 'center',
            padding: '48px 20px',
            margin: 'auto 0',
          }}>
            <div style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              background: 'rgba(108, 143, 197, 0.12)',
              border: '1px solid var(--accent-traffic)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '18px',
            }}>
              <Brain size={28} color="var(--accent-traffic)" />
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              How can the Smart City Planner help today?
            </h2>
            <p style={{
              fontSize: '0.85rem',
              color: 'var(--text-secondary)',
              maxWidth: '520px',
              lineHeight: 1.55,
              margin: '0 auto',
            }}>
              Ask about traffic congestion, bottlenecks, signal adjustments, air quality, or test proposed urban interventions across Hyderabad localities.
            </p>
          </div>
        ) : (
          /* Conversation Stream */
          conversation.map((turn, index) => (
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
                /* Municipal Command Center Operational Response Card */
                <div style={{
                  marginBottom: '16px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
                  overflow: 'hidden'
                }}>
                  {/* Command Center Card Header */}
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '12px 18px',
                    background: 'var(--bg-input)',
                    borderBottom: '1px solid var(--border-default)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Brain size={16} color="var(--accent-traffic)" />
                      <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)', letterSpacing: '0.01em' }}>
                        Planning Assistant
                      </span>
                      {turn.location && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          • <Compass size={12} color="var(--text-muted)" /> {turn.location}
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        padding: '3px 8px',
                        borderRadius: '4px',
                        background: 'rgba(255,255,255,0.05)',
                        border: '1px solid var(--border-default)',
                        color: 'var(--text-secondary)'
                      }}>
                        {getOperationalStatusLabel(turn.decision, turn.evidenceStatus, turn.testedInterventions)}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {turn.timestamp}
                      </span>
                    </div>
                  </div>

                  <div style={{ padding: '18px 20px' }}>
                    {/* 1. Assessment (Concise operational answer) */}
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{
                        fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                        fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '6px'
                      }}>
                        Assessment
                      </div>
                      <p style={{
                        fontSize: '0.92rem', color: 'var(--text-primary)', lineHeight: 1.55, margin: 0, fontWeight: 400
                      }}>
                        {turn.content}
                      </p>
                    </div>

                    {/* 2. Key Indicators (Compact visual metrics layout) */}
                    {/* Live TomTom Traffic Indicators */}
                    {turn.trafficEvidence && turn.trafficEvidence.sourceType === 'observed' && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'
                        }}>
                          <div style={{
                            fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase'
                          }}>
                            Key Traffic Indicators
                          </div>
                          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            Segment Telemetry (TomTom)
                          </span>
                        </div>
                        <div style={{
                          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                          gap: '8px'
                        }}>
                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>NETWORK SPEED</div>
                            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                              {turn.trafficEvidence.netSpeed !== null ? `${turn.trafficEvidence.netSpeed} km/h` : '—'}
                            </div>
                            {turn.trafficEvidence.freeFlowSpeed && (
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                                Free-flow: {turn.trafficEvidence.freeFlowSpeed} km/h
                              </div>
                            )}
                          </div>

                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>SPEED DEFICIT</div>
                            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: (turn.trafficEvidence.speedDeficitPct ?? 0) > 30 ? 'var(--accent-warning)' : 'var(--text-primary)', marginTop: '2px' }}>
                              {turn.trafficEvidence.speedDeficitPct !== null ? `${turn.trafficEvidence.speedDeficitPct}%` : (turn.trafficEvidence.congestion ?? '—')}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                              Below free-flow
                            </div>
                          </div>

                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>SEGMENT DELAY</div>
                            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                              {turn.trafficEvidence.delay !== null ? `+${turn.trafficEvidence.delay} sec` : '—'}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                              Travel-time delay
                            </div>
                          </div>

                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>PRIMARY CORRIDOR</div>
                            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '3px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {turn.trafficEvidence.lowestCorridor || turn.trafficEvidence.location || 'Main Arterial'}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', marginTop: '1px' }}>
                              {turn.trafficEvidence.lowestSpeed ? `${turn.trafficEvidence.lowestSpeed} km/h recorded` : 'Flow monitored'}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Live Weather Current Indicators */}
                    {turn.weatherEvidence && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px'
                        }}>
                          <div style={{
                            fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase'
                          }}>
                            Current Meteorological Conditions
                          </div>
                          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            WeatherAPI Observation
                          </span>
                        </div>
                        <div style={{
                          display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                          gap: '8px'
                        }}>
                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>TEMPERATURE</div>
                            <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#38bdf8', marginTop: '2px' }}>
                              {turn.weatherEvidence.temperature !== null ? `${turn.weatherEvidence.temperature}°C` : '—'}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                              {turn.weatherEvidence.feelsLike ? `Feels like ${turn.weatherEvidence.feelsLike}°C` : turn.weatherEvidence.condition}
                            </div>
                          </div>

                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>CONDITION</div>
                            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '3px' }}>
                              {turn.weatherEvidence.condition}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                              Precip: {turn.weatherEvidence.precip !== null ? `${turn.weatherEvidence.precip} mm` : '0 mm'}
                            </div>
                          </div>

                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>HUMIDITY & WIND</div>
                            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                              {turn.weatherEvidence.humidity !== null ? `${turn.weatherEvidence.humidity}%` : '—'}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                              {turn.weatherEvidence.windSpeed ? `${turn.weatherEvidence.windSpeed} km/h ${turn.weatherEvidence.windDir}` : 'Calm'}
                            </div>
                          </div>

                          <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>ATMOSPHERIC</div>
                            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                              UV: {turn.weatherEvidence.uv !== null ? turn.weatherEvidence.uv : '—'}
                            </div>
                            <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                              {turn.weatherEvidence.pressure ? `${turn.weatherEvidence.pressure} hPa` : 'Standard pressure'}
                            </div>
                          </div>
                        </div>

                        {/* Separate Forecast Strip */}
                        {turn.weatherEvidence.forecast && turn.weatherEvidence.forecast.length > 0 && (
                          <div style={{
                            marginTop: '10px', padding: '10px 12px', background: 'var(--bg-input)',
                            borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)'
                          }}>
                            <div style={{ fontSize: '0.65rem', fontWeight: 700, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginBottom: '6px' }}>
                              OUTLOOK & FORECAST (Open-Meteo Model)
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', fontSize: '0.75rem' }}>
                              {turn.weatherEvidence.forecast.map((fc, idx) => (
                                <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{fc.day || `Day ${idx + 1}`}:</span>
                                  <span style={{ color: 'var(--text-secondary)' }}>{fc.high ?? '—'}° / {fc.low ?? '—'}°C</span>
                                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>({fc.condition || 'Clear'})</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* POLLUTION — Environmental Intelligence Section */}
                    {turn.pollutionEvidence && (
                      <div style={{ marginBottom: '20px' }}>
                        {/* Air Quality Overview Header with Severity Indicator */}
                        <div style={{
                          display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center',
                          padding: '12px 14px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--border-divider)', marginBottom: '12px', gap: '10px'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <div style={{
                              width: '44px', height: '44px', borderRadius: 'var(--radius-sm)',
                              background: (turn.pollutionEvidence.aqi ?? 0) > 200 ? 'rgba(239, 68, 68, 0.15)' : (
                                (turn.pollutionEvidence.aqi ?? 0) > 100 ? 'rgba(245, 158, 11, 0.15)' : (
                                  (turn.pollutionEvidence.aqi ?? 0) > 50 ? 'rgba(59, 130, 246, 0.15)' : 'rgba(16, 185, 129, 0.15)'
                                )
                              ),
                              border: `1px solid ${(turn.pollutionEvidence.aqi ?? 0) > 200 ? '#ef4444' : (
                                (turn.pollutionEvidence.aqi ?? 0) > 100 ? '#f59e0b' : (
                                  (turn.pollutionEvidence.aqi ?? 0) > 50 ? '#3b82f6' : '#10b981'
                                )
                              )}`,
                              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'
                            }}>
                              <span style={{ fontSize: '0.6rem', fontWeight: 700, color: 'var(--text-muted)', lineHeight: 1 }}>AQI</span>
                              <span style={{
                                fontSize: '1.15rem', fontWeight: 800, lineHeight: 1.1,
                                color: (turn.pollutionEvidence.aqi ?? 0) > 200 ? '#ef4444' : (
                                  (turn.pollutionEvidence.aqi ?? 0) > 100 ? '#f59e0b' : (
                                    (turn.pollutionEvidence.aqi ?? 0) > 50 ? '#3b82f6' : '#10b981'
                                  )
                                )
                              }}>
                                {turn.pollutionEvidence.aqi ?? '—'}
                              </span>
                            </div>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{
                                  fontSize: '0.92rem', fontWeight: 700,
                                  color: (turn.pollutionEvidence.aqi ?? 0) > 200 ? '#ef4444' : (
                                    (turn.pollutionEvidence.aqi ?? 0) > 100 ? '#f59e0b' : (
                                      (turn.pollutionEvidence.aqi ?? 0) > 50 ? '#3b82f6' : '#10b981'
                                    )
                                  )
                                }}>
                                  {turn.pollutionEvidence.category || 'Air Quality Standard'}
                                </span>
                              </div>
                              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                                {turn.pollutionEvidence.location || 'Monitored Locality'} • Primary Driver: {turn.pollutionEvidence.primaryPollutant || 'Particulate Matter'}
                              </div>
                            </div>
                          </div>

                          <div style={{ textAlign: 'right', fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            <div>Model: {turn.pollutionEvidence.dataSource || 'Open-Meteo Air Quality Model'}</div>
                            <div>Timestamp: {turn.pollutionEvidence.dataTimestamp || 'Current Atmospheric Snapshot'}</div>
                          </div>
                        </div>

                        {/* Pollutant Concentrations Grid */}
                        <div style={{ marginBottom: '12px' }}>
                          <div style={{
                            fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '6px'
                          }}>
                            Pollutant Concentrations
                          </div>
                          <div style={{
                            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))',
                            gap: '8px'
                          }}>
                            {/* PM2.5 */}
                            <div style={{
                              padding: '8px 10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
                              border: (turn.pollutionEvidence.pm25 !== null && Number(turn.pollutionEvidence.pm25) > 30) ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid var(--border-divider)'
                            }}>
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                                <span>PM2.5</span>
                                <span style={{ fontSize: '0.58rem' }}>Fine</span>
                              </div>
                              <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                                {turn.pollutionEvidence.pm25 !== null ? `${turn.pollutionEvidence.pm25}` : '—'}
                              </div>
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>µg/m³</div>
                            </div>

                            {/* PM10 */}
                            <div style={{
                              padding: '8px 10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
                              border: (turn.pollutionEvidence.pm10 !== null && Number(turn.pollutionEvidence.pm10) > 50) ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid var(--border-divider)'
                            }}>
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                                <span>PM10</span>
                                <span style={{ fontSize: '0.58rem' }}>Respirable</span>
                              </div>
                              <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                                {turn.pollutionEvidence.pm10 !== null ? `${turn.pollutionEvidence.pm10}` : '—'}
                              </div>
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>µg/m³</div>
                            </div>

                            {/* NO2 */}
                            {turn.pollutionEvidence.pollutants?.nitrogen_dioxide !== undefined && turn.pollutionEvidence.pollutants?.nitrogen_dioxide !== null && (
                              <div style={{ padding: '8px 10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>NO₂</div>
                                <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                                  {turn.pollutionEvidence.pollutants.nitrogen_dioxide}
                                </div>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>µg/m³</div>
                              </div>
                            )}

                            {/* SO2 */}
                            {turn.pollutionEvidence.pollutants?.sulphur_dioxide !== undefined && turn.pollutionEvidence.pollutants?.sulphur_dioxide !== null && (
                              <div style={{ padding: '8px 10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>SO₂</div>
                                <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                                  {turn.pollutionEvidence.pollutants.sulphur_dioxide}
                                </div>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>µg/m³</div>
                              </div>
                            )}

                            {/* CO */}
                            {turn.pollutionEvidence.pollutants?.carbon_monoxide !== undefined && turn.pollutionEvidence.pollutants?.carbon_monoxide !== null && (
                              <div style={{ padding: '8px 10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>CO</div>
                                <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                                  {turn.pollutionEvidence.pollutants.carbon_monoxide}
                                </div>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>µg/m³</div>
                              </div>
                            )}

                            {/* O3 */}
                            {turn.pollutionEvidence.pollutants?.ozone !== undefined && turn.pollutionEvidence.pollutants?.ozone !== null && (
                              <div style={{ padding: '8px 10px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>O₃</div>
                                <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                                  {turn.pollutionEvidence.pollutants.ozone}
                                </div>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>µg/m³</div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Structured Municipal Actions & Health Advisory (Clean, user-centric) */}
                        {turn.pollutionEvidence.suggestedInterventions && turn.pollutionEvidence.suggestedInterventions.length > 0 && (
                          <div style={{
                            padding: '12px 14px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-divider)', borderLeft: '3px solid var(--accent-emerald)', marginBottom: '8px'
                          }}>
                            <div style={{
                              fontSize: '0.68rem', fontWeight: 700, color: 'var(--accent-emerald)',
                              fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px'
                            }}>
                              Recommended Municipal Actions
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {turn.pollutionEvidence.suggestedInterventions.slice(0, 3).map((inv, idx) => {
                                const actionType = typeof inv === 'object' ? (inv.action_type || 'MUNICIPAL_INTERVENTION') : 'MUNICIPAL_ACTION'
                                const desc = typeof inv === 'object' ? (inv.description || '') : String(inv)
                                const horizon = typeof inv === 'object' ? (inv.horizon || (idx < 2 ? 'Immediate' : 'Medium-term')) : 'Proposed'
                                const stakeholders = typeof inv === 'object' && Array.isArray(inv.stakeholders) ? inv.stakeholders.join(', ') : 'GHMC / TSPCB'
                                
                                return (
                                  <div key={idx} style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                                      <span style={{
                                        fontSize: '0.6rem', fontWeight: 700, padding: '1px 5px', borderRadius: '2px',
                                        background: horizon.toLowerCase().includes('immediate') ? 'rgba(239, 68, 68, 0.15)' : (
                                          horizon.toLowerCase().includes('medium') ? 'rgba(245, 158, 11, 0.15)' : 'rgba(59, 130, 246, 0.15)'
                                        ),
                                        color: horizon.toLowerCase().includes('immediate') ? '#ef4444' : (
                                          horizon.toLowerCase().includes('medium') ? '#f59e0b' : '#60a5fa'
                                        )
                                      }}>
                                        {horizon.toUpperCase()}
                                      </span>
                                      <strong style={{ color: 'var(--text-primary)' }}>{actionType.replace(/_/g, ' ')}</strong>
                                      {stakeholders && (
                                        <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>({stakeholders})</span>
                                      )}
                                    </div>
                                    <div style={{ paddingLeft: '8px', lineHeight: 1.4 }}>
                                      {desc}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* ENERGY — Infrastructure & Demand Intelligence Section */}
                    {turn.energyEvidence && (
                      <div style={{ marginBottom: '20px' }}>
                        {/* Energy Overview Header with Load & Grid Status */}
                        <div style={{
                          display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center',
                          padding: '12px 14px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
                          border: '1px solid var(--border-divider)', marginBottom: '12px', gap: '10px'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <div style={{
                              width: '44px', height: '44px', borderRadius: 'var(--radius-sm)',
                              background: turn.energyEvidence.severity === 'CRITICAL' ? 'rgba(239, 68, 68, 0.15)' : (
                                turn.energyEvidence.severity === 'HIGH' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(59, 130, 246, 0.15)'
                              ),
                              border: `1px solid ${turn.energyEvidence.severity === 'CRITICAL' ? '#ef4444' : (
                                turn.energyEvidence.severity === 'HIGH' ? '#f59e0b' : '#3b82f6'
                              )}`,
                              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'
                            }}>
                              <Zap size={16} color={turn.energyEvidence.severity === 'CRITICAL' ? '#ef4444' : (
                                turn.energyEvidence.severity === 'HIGH' ? '#f59e0b' : '#3b82f6'
                              )} />
                              <span style={{
                                fontSize: '0.62rem', fontWeight: 800, lineHeight: 1, marginTop: '2px',
                                color: turn.energyEvidence.severity === 'CRITICAL' ? '#ef4444' : (
                                  turn.energyEvidence.severity === 'HIGH' ? '#f59e0b' : '#3b82f6'
                                )
                              }}>
                                {turn.energyEvidence.loadPct !== null ? `${Math.round(turn.energyEvidence.loadPct)}%` : '—'}
                              </span>
                            </div>
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{
                                  fontSize: '0.92rem', fontWeight: 700,
                                  color: turn.energyEvidence.severity === 'CRITICAL' ? '#ef4444' : (
                                    turn.energyEvidence.severity === 'HIGH' ? '#f59e0b' : 'var(--text-primary)'
                                  )
                                }}>
                                  Grid Operational Status: {turn.energyEvidence.severity || 'NORMAL'}
                                </span>
                              </div>
                              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                                {turn.energyEvidence.location} Substation Grid Region • Efficiency Index: {turn.energyEvidence.efficiencyScorePct !== null ? `${turn.energyEvidence.efficiencyScorePct}%` : 'Standard'}
                              </div>
                            </div>
                          </div>

                          <div style={{ textAlign: 'right', fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            <div style={{
                              fontWeight: 700,
                              color: turn.energyEvidence.isSynthetic ? '#f59e0b' : '#38bdf8'
                            }}>
                              {turn.energyEvidence.isSynthetic ? 'SYNTHETIC BASELINE MODEL' : 'LIVE AGENT TELEMETRY'}
                            </div>
                            <div>{turn.energyEvidence.provenanceLabel}</div>
                          </div>
                        </div>

                        {/* Energy Demand & Load Indicators Grid */}
                        <div style={{ marginBottom: '12px' }}>
                          <div style={{
                            fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '6px'
                          }}>
                            Demand & Transformer Load Indicators
                          </div>
                          <div style={{
                            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                            gap: '8px'
                          }}>
                            {/* Current Demand */}
                            <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>MEASURED DEMAND</div>
                              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                                {turn.energyEvidence.currentLoadMw !== null ? `${turn.energyEvidence.currentLoadMw} MW` : '—'}
                              </div>
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                                Real-time demand
                              </div>
                            </div>

                            {/* Grid Capacity */}
                            <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>RATED CAPACITY</div>
                              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
                                {turn.energyEvidence.capacityMw !== null ? `${turn.energyEvidence.capacityMw} MW` : '—'}
                              </div>
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                                Transformer ceiling
                              </div>
                            </div>

                            {/* Load Percentage */}
                            <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>TRANSFORMER LOAD</div>
                              <div style={{
                                fontSize: '1.05rem', fontWeight: 700, marginTop: '2px',
                                color: (turn.energyEvidence.loadPct ?? 0) > 85 ? 'var(--accent-warning)' : 'var(--text-primary)'
                              }}>
                                {turn.energyEvidence.loadPct !== null ? `${turn.energyEvidence.loadPct}%` : '—'}
                              </div>
                              <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                                {turn.energyEvidence.availableCapacityMw !== null ? `${turn.energyEvidence.availableCapacityMw} MW head room` : 'Capacity headroom'}
                              </div>
                            </div>

                            {/* Solar / Renewables Component */}
                            {turn.energyEvidence.solarGenMw !== null && (
                              <div style={{ padding: '8px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-divider)' }}>
                                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>SOLAR GENERATION</div>
                                <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#10b981', marginTop: '2px' }}>
                                  {turn.energyEvidence.solarGenMw > 0 ? `${turn.energyEvidence.solarGenMw} MW` : '0.0 MW'}
                                </div>
                                <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', marginTop: '1px' }}>
                                  Renewable offset
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Monitored Substation Details if present */}
                        {turn.energyEvidence.substations && turn.energyEvidence.substations.length > 0 && (
                          <div style={{
                            padding: '10px 12px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-divider)', marginBottom: '12px'
                          }}>
                            <div style={{
                              fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                              fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '6px'
                            }}>
                              Monitored Infrastructure Substation
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', fontSize: '0.74rem' }}>
                              {turn.energyEvidence.substations.map((sub, sIdx) => (
                                <div key={sIdx} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <strong style={{ color: 'var(--text-primary)' }}>{sub.name}:</strong>
                                  <span style={{ color: 'var(--text-secondary)' }}>{sub.current_load_mw} MW / {sub.capacity_mw} MW ({sub.load_pct}%)</span>
                                  <span style={{
                                    fontSize: '0.62rem', padding: '1px 5px', borderRadius: '2px', fontWeight: 700,
                                    background: sub.status === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : (
                                      sub.status === 'HIGH' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)'
                                    ),
                                    color: sub.status === 'CRITICAL' ? '#ef4444' : (
                                      sub.status === 'HIGH' ? '#f59e0b' : '#10b981'
                                    )
                                  }}>
                                    {sub.status}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Structured Energy Recommendations (Top 2-3 High Impact Actions) */}
                        {turn.energyEvidence.recommendations && turn.energyEvidence.recommendations.length > 0 && (
                          <div style={{
                            padding: '12px 14px', background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--border-divider)', borderLeft: '3px solid #38bdf8', marginBottom: '8px'
                          }}>
                            <div style={{
                              fontSize: '0.68rem', fontWeight: 700, color: '#38bdf8',
                              fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '8px'
                            }}>
                              Recommended Grid Actions
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                              {turn.energyEvidence.recommendations.slice(0, 3).map((rec, rIdx) => {
                                const priority = rec.priority || (rIdx === 0 ? 'CRITICAL' : (rIdx < 3 ? 'HIGH' : 'MEDIUM'))
                                const horizonLabel = rIdx < 2 ? 'Immediate' : 'Medium-term'
                                return (
                                  <div key={rIdx} style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                                      <span style={{
                                        fontSize: '0.6rem', fontWeight: 700, padding: '1px 5px', borderRadius: '2px',
                                        background: horizonLabel === 'Immediate' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                                        color: horizonLabel === 'Immediate' ? '#ef4444' : '#38bdf8'
                                      }}>
                                        {horizonLabel.toUpperCase()}
                                      </span>
                                      <strong style={{ color: 'var(--text-primary)' }}>{rec.title}</strong>
                                      {rec.impact && (
                                        <span style={{ fontSize: '0.68rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>[Est. Impact: {rec.impact}]</span>
                                      )}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* 3. Analysis: Multi-Intervention Simulation Comparison Table if present */}
                    {turn.multiInterventionComparison && turn.multiInterventionComparison.length > 1 && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <div style={{
                            fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-primary)',
                            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '6px'
                          }}>
                            <BarChart3 size={13} color="var(--accent-traffic)" />
                            SUMO Simulation Analysis (Multi-Intervention Comparison)
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            <span>Horizon: {turn.multiInterventionComparison.durationSeconds ? `${turn.multiInterventionComparison.durationSeconds}s` : 'Scenario'}</span>
                            {turn.multiInterventionComparison.seed !== undefined && <span>• Seed {turn.multiInterventionComparison.seed}</span>}
                          </div>
                        </div>

                        <div style={{ overflowX: 'auto', marginBottom: '6px' }}>
                          <table style={{
                            width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem',
                            background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)'
                          }}>
                            <thead>
                              <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left', color: 'var(--text-muted)' }}>
                                <th style={{ padding: '8px 10px' }}>Intervention</th>
                                <th style={{ padding: '8px 10px' }}>Target Corridor Speed</th>
                                <th style={{ padding: '8px 10px' }}>Network Speed</th>
                                <th style={{ padding: '8px 10px' }}>Network Delay</th>
                                <th style={{ padding: '8px 10px' }}>Trade-offs Observed</th>
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

                    {/* Single-Run Simulation Results if present */}
                    {turn.simulationEvidence && !turn.multiInterventionComparison && (
                      <div style={{ marginBottom: '18px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                          <div style={{
                            fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-primary)',
                            fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '6px'
                          }}>
                            <Gauge size={13} color="var(--accent-traffic)" />
                            SUMO Simulation Analysis ({turn.simulationEvidence.interventionType} on {turn.simulationEvidence.interventionTarget})
                          </div>
                          <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {turn.simulationEvidence.scenario} • {turn.simulationEvidence.durationSeconds}s
                          </span>
                        </div>

                        {turn.simulationEvidence.isBaselineMissing ? (
                          <div style={{ padding: '8px 12px', background: 'rgba(239, 68, 68, 0.08)', borderRadius: 'var(--radius-sm)', color: '#f87171', fontSize: '0.75rem' }}>
                            Comparison unavailable: paired baseline simulation evidence missing.
                          </div>
                        ) : (
                          <div style={{ overflowX: 'auto' }}>
                            <table style={{
                              width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem',
                              background: 'var(--bg-input)', borderRadius: 'var(--radius-sm)'
                            }}>
                              <thead>
                                <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left', color: 'var(--text-muted)' }}>
                                  <th style={{ padding: '6px 10px' }}>Metric</th>
                                  <th style={{ padding: '6px 10px' }}>Baseline</th>
                                  <th style={{ padding: '6px 10px' }}>Simulated Intervention</th>
                                  <th style={{ padding: '6px 10px' }}>Change</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                  <td style={{ padding: '6px 10px' }}>Network Speed</td>
                                  <td style={{ padding: '6px 10px' }}>{turn.simulationEvidence.baseline?.speed ? `${turn.simulationEvidence.baseline.speed} km/h` : '—'}</td>
                                  <td style={{ padding: '6px 10px' }}>{turn.simulationEvidence.intervention?.speed ? `${turn.simulationEvidence.intervention.speed} km/h` : '—'}</td>
                                  <td style={{ padding: '6px 10px', fontWeight: 600, color: (turn.simulationEvidence.speedChangePct ?? 0) >= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)' }}>
                                    {turn.simulationEvidence.speedChangePct !== null ? `${turn.simulationEvidence.speedChangePct > 0 ? '+' : ''}${turn.simulationEvidence.speedChangePct}%` : '—'}
                                  </td>
                                </tr>
                                <tr style={{ borderBottom: '1px solid var(--border-divider)' }}>
                                  <td style={{ padding: '6px 10px' }}>Average Delay</td>
                                  <td style={{ padding: '6px 10px' }}>{turn.simulationEvidence.baseline?.delay ? `${turn.simulationEvidence.baseline.delay}s` : '—'}</td>
                                  <td style={{ padding: '6px 10px' }}>{turn.simulationEvidence.intervention?.delay ? `${turn.simulationEvidence.intervention.delay}s` : '—'}</td>
                                  <td style={{ padding: '6px 10px', fontWeight: 600, color: (turn.simulationEvidence.delayChangePct ?? 0) <= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)' }}>
                                    {turn.simulationEvidence.delayChangePct !== null ? `${turn.simulationEvidence.delayChangePct > 0 ? '+' : ''}${turn.simulationEvidence.delayChangePct}%` : '—'}
                                  </td>
                                </tr>
                                <tr>
                                  <td style={{ padding: '6px 10px' }}>Waiting Time</td>
                                  <td style={{ padding: '6px 10px' }}>{turn.simulationEvidence.baseline?.waiting ? `${turn.simulationEvidence.baseline.waiting}s` : '—'}</td>
                                  <td style={{ padding: '6px 10px' }}>{turn.simulationEvidence.intervention?.waiting ? `${turn.simulationEvidence.intervention.waiting}s` : '—'}</td>
                                  <td style={{ padding: '6px 10px', fontWeight: 600, color: (turn.simulationEvidence.waitingTimeChangePct ?? 0) <= 0 ? 'var(--accent-emerald)' : 'var(--accent-warning)' }}>
                                    {turn.simulationEvidence.waitingTimeChangePct !== null ? `${turn.simulationEvidence.waitingTimeChangePct > 0 ? '+' : ''}${turn.simulationEvidence.waitingTimeChangePct}%` : '—'}
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}

                    {/* 4. Recommended Actions & Status */}
                    {/* Tested vs Untested status labels */}
                    {((turn.testedInterventions && turn.testedInterventions.length > 0) || (turn.untestedCandidates && turn.untestedCandidates.length > 0)) && (
                      <div style={{ marginBottom: '14px' }}>
                        <div style={{
                          fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-muted)',
                          fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: '6px'
                        }}>
                          Intervention Validation Status
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                          {turn.testedInterventions?.map((t, idx) => (
                            <div key={`tested-${idx}`} style={{
                              display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem',
                              padding: '3px 8px', background: 'rgba(16, 185, 129, 0.08)',
                              border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '4px', color: '#10b981'
                            }}>
                              <span style={{ fontWeight: 800, fontSize: '0.6rem', background: '#10b981', color: '#000', padding: '1px 4px', borderRadius: '2px' }}>
                                SIMULATION TESTED
                              </span>
                              <span>{formatInterventionBadgeLabel(t)}</span>
                            </div>
                          ))}
                          {turn.untestedCandidates?.map((u, idx) => (
                            <div key={`untested-${idx}`} style={{
                              display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem',
                              padding: '3px 8px', background: 'var(--bg-input)',
                              border: '1px solid var(--border-default)', borderRadius: '4px', color: 'var(--text-secondary)'
                            }}>
                              <span style={{ fontWeight: 700, fontSize: '0.6rem', background: 'var(--text-muted)', color: '#fff', padding: '1px 4px', borderRadius: '2px' }}>
                                PROPOSED / UNTESTED
                              </span>
                              <span>{formatInterventionBadgeLabel(u)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actionable Municipal Recommendation (Avoid duplicating if already rendered inside Pollution/Energy sections) */}
                    {turn.recommendation && !turn.pollutionEvidence && !turn.energyEvidence && (
                      <div style={{
                        padding: '12px 14px', background: 'var(--bg-input)',
                        borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)',
                        borderLeft: '3px solid var(--accent-traffic)',
                        marginBottom: '16px'
                      }}>
                        <div style={{
                          fontSize: '0.68rem', color: 'var(--accent-traffic)', fontWeight: 700,
                          fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px', textTransform: 'uppercase'
                        }}>
                          Recommended Operational Actions
                        </div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: 1.45, margin: 0, fontWeight: 400 }}>
                          {turn.recommendation}
                        </p>
                      </div>
                    )}

                    {/* Municipal interventions from Pollution Agent if available */}
                    {turn.pollutionEvidence?.suggestedInterventions && turn.pollutionEvidence.suggestedInterventions.length > 0 && !turn.recommendation && (
                      <div style={{
                        padding: '12px 14px', background: 'var(--bg-input)',
                        borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-default)',
                        borderLeft: '3px solid var(--accent-emerald)',
                        marginBottom: '16px'
                      }}>
                        <div style={{
                          fontSize: '0.68rem', color: 'var(--accent-emerald)', fontWeight: 700,
                          fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', marginBottom: '4px', textTransform: 'uppercase'
                        }}>
                          Recommended Municipal Air-Quality Measures
                        </div>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)', lineHeight: 1.45 }}>
                          {turn.pollutionEvidence.suggestedInterventions.map((inv, idx) => (
                            <div key={idx} style={{ marginTop: idx > 0 ? '4px' : '0' }}>
                              • {typeof inv === 'object' ? `${inv.action_type || 'Action'}: ${inv.description || ''}` : inv}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 5. Evidence & Provenance Bar (Clean operational footer) */}
                    <div style={{
                      display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center',
                      gap: '8px', paddingTop: '10px', borderTop: '1px solid var(--border-divider)',
                      fontSize: '0.68rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)'
                    }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
                        <span>
                          <strong>Locality:</strong> {turn.location || 'Hyderabad Metro'}
                        </span>
                        <span>•</span>
                        <span>
                          <strong>Source:</strong> {
                            turn.trafficEvidence ? (turn.trafficEvidence.sourceType === 'observed' ? 'TomTom Live Flow API' : 'Eclipse SUMO Microsimulation') : (
                              turn.weatherEvidence ? 'WeatherAPI.com & Open-Meteo' : (
                                turn.pollutionEvidence ? 'Open-Meteo Air Quality Model' : (
                                  turn.energyEvidence ? (turn.energyEvidence.isSynthetic ? 'Synthetic Baseline Model' : 'Energy Agent Telemetry API') : 'Municipal Operations Domain'
                                )
                              )
                            )
                          }
                        </span>
                        <span>•</span>
                        <span>
                          <strong>Classification:</strong> {
                            turn.energyEvidence && turn.energyEvidence.isSynthetic ? 'SYNTHETIC BASELINE' : (
                              turn.pollutionEvidence ? 'EVIDENCE: MODELLED ESTIMATE' : (turn.evidenceStatus || 'EVIDENCE: OBSERVATIONAL')
                            )
                          }
                        </span>
                      </div>

                      {/* Expandable Technical Execution Diagnostics Toggle */}
                      {turn.runtime && (
                        <button
                          onClick={() => toggleDetails(index)}
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-secondary)',
                            fontSize: '0.68rem',
                            fontFamily: 'var(--font-mono)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            cursor: 'pointer',
                            padding: '2px 4px',
                            borderRadius: '3px'
                          }}
                        >
                          <Database size={12} />
                          <span>Execution Details</span>
                          {expandedDetails[index] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                        </button>
                      )}
                    </div>

                    {/* Collapsible Technical Execution Diagnostics */}
                    {turn.runtime && expandedDetails[index] && (
                      <div style={{
                        marginTop: '10px',
                        padding: '10px 14px',
                        background: 'var(--bg-input)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-default)',
                        fontSize: '0.68rem',
                        fontFamily: 'var(--font-mono)',
                        color: 'var(--text-secondary)'
                      }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
                          <span><strong>LLM Provider:</strong> {turn.runtime.llm_provider || 'Groq'}</span>
                          <span>•</span>
                          <span><strong>Model:</strong> {turn.runtime.llm_model || 'llama-3.3-70b-versatile'}</span>
                          <span>•</span>
                          <span><strong>Planner Calls:</strong> {turn.runtime.llm_calls || 1}</span>
                          <span>•</span>
                          <span><strong>Dispatched Specialists:</strong> {turn.dispatchedAgents?.length > 0 ? turn.dispatchedAgents.map(a => a.replace('_agent', '').toUpperCase()).join(', ') : 'None'}</span>
                          <span>•</span>
                          <span><strong>Simulation Status:</strong> {turn.runtime.simulation_runs?.length > 0 ? `${turn.runtime.simulation_runs.length} Runs Completed` : 'Not Executed'}</span>
                          <span>•</span>
                          <span><strong>Cache:</strong> {turn.runtime.cache_used ? 'Hit' : 'Miss'}</span>
                          <span>•</span>
                          <span><strong>System Latency:</strong> {turn.runtime.total_latency_ms ? `${turn.runtime.total_latency_ms}ms` : '—'}</span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))
        )}

        {/* Processing Indicator inside Conversation Area */}
        {isProcessing && (
          <GlassCard style={{ display: 'flex', alignItems: 'center', gap: '14px', borderStyle: 'dashed', padding: '16px 20px', marginBottom: '8px' }}>
            <div style={{
              width: 24, height: 24, borderRadius: '50%',
              border: '2px solid var(--accent-traffic-dim)', borderTopColor: 'var(--accent-traffic)',
              animation: 'spin 1s linear infinite', flexShrink: 0
            }} />
            <div>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                Planner is analyzing city conditions...
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'var(--font-mono)' }}>
                Dispatching real specialist agents, querying telemetry, and evaluating interventions.
              </div>
            </div>
          </GlassCard>
        )}

        {/* Honest Error State inside Conversation Area */}
        {errorMessage && (
          <GlassCard style={{ borderColor: 'var(--accent-warning)', background: 'var(--accent-warning-dim)', padding: '16px 20px', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <AlertCircle size={20} color="var(--accent-warning)" style={{ flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontWeight: 600, color: 'var(--accent-warning)', fontSize: '0.875rem' }}>
                  Unable to retrieve evidence.
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                  {errorMessage}
                </div>
              </div>
            </div>
          </GlassCard>
        )}

        <div ref={messagesEndRef} style={{ height: '1px' }} />
      </div>

      {/* ChatGPT-style Fixed/Sticky Bottom Message Composer */}
      <div style={{
        position: 'sticky',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        background: 'linear-gradient(to top, var(--bg-workspace) 85%, rgba(24, 25, 27, 0.95) 50%, transparent 100%)',
        paddingTop: '18px',
        paddingBottom: 'max(14px, env(safe-area-inset-bottom, 14px))',
        marginTop: 'auto',
      }}>
        <div style={{
          width: '100%',
          maxWidth: '1000px',
          margin: '0 auto',
          padding: '0 8px',
        }}>
          {/* Rounded Input Capsule */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              gap: '10px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border-default)',
              borderRadius: '24px',
              padding: '8px 12px 8px 18px',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.14)',
              transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
            }}
            onFocusCapture={e => {
              e.currentTarget.style.borderColor = 'var(--accent-traffic)'
              e.currentTarget.style.boxShadow = '0 4px 24px rgba(108, 143, 197, 0.2)'
            }}
            onBlurCapture={e => {
              e.currentTarget.style.borderColor = 'var(--border-default)'
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.14)'
            }}
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={query}
              onChange={handleTextareaChange}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSendPrompt()
                }
              }}
              placeholder="Ask the Smart City Planner (e.g., 'What is the traffic situation in Tarnaka?' or 'How can I optimize traffic in Begumpet?')..."
              style={{
                flex: 1,
                border: 'none',
                outline: 'none',
                background: 'transparent',
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-body)',
                fontSize: '0.9rem',
                lineHeight: 1.45,
                padding: '6px 0',
                resize: 'none',
                minHeight: '24px',
                maxHeight: '160px',
                overflowY: query.length > 150 ? 'auto' : 'hidden',
              }}
            />
            <button
              onClick={() => handleSendPrompt()}
              disabled={isProcessing || !query.trim()}
              aria-label="Send message"
              title={isProcessing ? 'Analyzing...' : 'Send message (Enter)'}
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                border: 'none',
                background: isProcessing || !query.trim() ? 'var(--bg-tertiary)' : 'var(--accent-traffic)',
                color: isProcessing || !query.trim() ? 'var(--text-muted)' : '#ffffff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: isProcessing || !query.trim() ? 'not-allowed' : 'pointer',
                flexShrink: 0,
                transition: 'background var(--transition-fast), opacity var(--transition-fast)',
                opacity: isProcessing || !query.trim() ? 0.6 : 1,
                marginBottom: '2px',
              }}
            >
              {isProcessing ? (
                <RefreshCw size={15} className="spin" style={{ animation: 'spin 1s linear infinite' }} />
              ) : (
                <Send size={15} style={{ marginLeft: '1px' }} />
              )}
            </button>
          </div>

          {/* Micro Footer Disclaimer */}
          <div style={{
            fontSize: '0.68rem',
            color: 'var(--text-muted)',
            textAlign: 'center',
            marginTop: '8px',
            fontFamily: 'var(--font-mono)',
          }}>
            Smart City Planner synthesizes live telemetry & SUMO simulations · Press Enter to send, Shift + Enter for new line
          </div>
        </div>
      </div>
    </div>
  )
}

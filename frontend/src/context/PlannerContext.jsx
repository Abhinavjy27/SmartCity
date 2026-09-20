import { createContext, useContext, useState, useEffect } from 'react'

const PlannerContext = createContext(null)

const STORAGE_KEY = 'smartcity_planner_session'

export function generateSessionId() {
  return 'planner_sess_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9)
}

function loadInitialSession() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw) {
      const data = JSON.parse(raw)
      if (data && typeof data === 'object') {
        return {
          sessionId: data.sessionId || generateSessionId(),
          conversation: Array.isArray(data.conversation) ? data.conversation : [],
          simulationHistory: Array.isArray(data.simulationHistory) ? data.simulationHistory : [],
          testedScenarios: Array.isArray(data.testedScenarios) ? data.testedScenarios : [],
          testedInterventions: Array.isArray(data.testedInterventions) ? data.testedInterventions : [],
          untestedCandidates: Array.isArray(data.untestedCandidates) ? data.untestedCandidates : [],
          evidenceStatus: data.evidenceStatus || 'EVIDENCE: OBSERVATIONAL',
          baselineMetadata: data.baselineMetadata || null
        }
      }
    }
  } catch (err) {
    console.warn('[PlannerContext] Failed to parse stored session:', err)
  }
  return {
    sessionId: generateSessionId(),
    conversation: [],
    simulationHistory: [],
    testedScenarios: [],
    testedInterventions: [],
    untestedCandidates: [],
    evidenceStatus: 'EVIDENCE: OBSERVATIONAL',
    baselineMetadata: null
  }
}

export function PlannerProvider({ children }) {
  const [session, setSession] = useState(loadInitialSession)

  // Sync to sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        sessionId: session.sessionId,
        conversation: session.conversation,
        simulationHistory: session.simulationHistory,
        testedScenarios: session.testedScenarios,
        testedInterventions: session.testedInterventions,
        untestedCandidates: session.untestedCandidates,
        evidenceStatus: session.evidenceStatus,
        baselineMetadata: session.baselineMetadata
      }))
    } catch (err) {
      console.warn('[PlannerContext] Failed to persist session:', err)
    }
  }, [session])

  const clearSession = () => {
    const freshSession = {
      sessionId: generateSessionId(),
      conversation: [],
      simulationHistory: [],
      testedScenarios: [],
      testedInterventions: [],
      untestedCandidates: [],
      evidenceStatus: 'EVIDENCE: OBSERVATIONAL',
      baselineMetadata: null
    }
    setSession(freshSession)
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(freshSession))
    } catch (err) {
      console.warn('[PlannerContext] Failed to persist cleared session:', err)
    }
  }

  const updateSession = (updater) => {
    setSession(prev => (typeof updater === 'function' ? updater(prev) : { ...prev, ...updater }))
  }

  return (
    <PlannerContext.Provider value={{ session, setSession, updateSession, clearSession }}>
      {children}
    </PlannerContext.Provider>
  )
}

export function usePlanner() {
  const ctx = useContext(PlannerContext)
  if (!ctx) {
    throw new Error('usePlanner must be used within a PlannerProvider')
  }
  return ctx
}

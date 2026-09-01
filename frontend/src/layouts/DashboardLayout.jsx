import { useState, useEffect } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Car, Wind, Zap, CloudSun, Brain,
  Bell, User, Menu, X, AlertOctagon, CheckCircle2,
  MapPin, ChevronDown, Shield
} from 'lucide-react'
import CommandMenu from '../components/cult-ui/CommandMenu'

const navItems = [
  { path: '/dashboard', label: 'Command Center', icon: LayoutDashboard },
  { path: '/traffic', label: 'Traffic Intelligence', icon: Car },
  { path: '/pollution', label: 'Air Quality Intelligence', icon: Wind },
  { path: '/energy', label: 'Energy Consumption', icon: Zap },
  { path: '/weather', label: 'Weather Intelligence', icon: CloudSun },
  { path: '/planning', label: 'Planning Assistant', icon: Brain },
]

/* Elegant city skyline SVG for sidebar bottom */
function HyderabadSkyline() {
  return (
    <svg viewBox="0 0 175 50" fill="none" style={{ width: '100%', opacity: 0.15 }}>
      {/* Charminar silhouette */}
      <rect x="70" y="15" width="4" height="35" fill="currentColor" />
      <rect x="82" y="15" width="4" height="35" fill="currentColor" />
      <rect x="68" y="12" width="8" height="6" rx="3" fill="currentColor" />
      <rect x="80" y="12" width="8" height="6" rx="3" fill="currentColor" />
      <rect x="66" y="8" width="3" height="8" fill="currentColor" />
      <rect x="87" y="8" width="3" height="8" fill="currentColor" />
      <rect x="64" y="5" width="2" height="5" fill="currentColor" />
      <rect x="90" y="5" width="2" height="5" fill="currentColor" />
      <rect x="72" y="25" width="12" height="25" fill="currentColor" />
      <path d="M72 25 L78 18 L84 25" fill="currentColor" />
      {/* Buildings left */}
      <rect x="15" y="30" width="8" height="20" fill="currentColor" />
      <rect x="25" y="25" width="6" height="25" fill="currentColor" />
      <rect x="33" y="35" width="10" height="15" fill="currentColor" />
      <rect x="45" y="28" width="7" height="22" fill="currentColor" />
      <rect x="54" y="32" width="8" height="18" fill="currentColor" />
      {/* Buildings right */}
      <rect x="100" y="30" width="10" height="20" fill="currentColor" />
      <rect x="112" y="25" width="7" height="25" fill="currentColor" />
      <rect x="121" y="33" width="9" height="17" fill="currentColor" />
      <rect x="132" y="28" width="6" height="22" fill="currentColor" />
      <rect x="140" y="35" width="12" height="15" fill="currentColor" />
      <rect x="154" y="30" width="8" height="20" fill="currentColor" />
      {/* Minarets */}
      <rect x="65" y="2" width="1" height="4" fill="currentColor" />
      <rect x="90" y="2" width="1" height="4" fill="currentColor" />
      <circle cx="65.5" cy="1.5" r="1.5" fill="currentColor" />
      <circle cx="90.5" cy="1.5" r="1.5" fill="currentColor" />
    </svg>
  )
}

/* SUPADSP Logo Icon — refined geometric grid mark */
function LogoIcon() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" fill="none">
      {/* Top-left quadrant — primary, brightest */}
      <rect x="2" y="2" width="11" height="11" rx="2.5" fill="#D8DCC8" />
      {/* Top-right quadrant — accent olive */}
      <rect x="17" y="2" width="11" height="11" rx="2.5" fill="#596A43" />
      {/* Bottom-left quadrant — accent olive */}
      <rect x="2" y="17" width="11" height="11" rx="2.5" fill="#596A43" />
      {/* Bottom-right quadrant — muted */}
      <rect x="17" y="17" width="11" height="11" rx="2.5" fill="rgba(216,220,200,0.35)" />
    </svg>
  )
}

function CurrentTime() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 60000)
    return () => clearInterval(interval)
  }, [])
  const timeStr = time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }).toUpperCase()
  const dateStr = time.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' }).toUpperCase()
  return (
    <div style={{ fontSize: '0.65rem', color: 'var(--text-sidebar-muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.04em' }}>
      {timeStr} · {dateStr}
    </div>
  )
}

export default function DashboardLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [emergencyAlert, setEmergencyAlert] = useState(null)
  const [showIncidentModal, setShowIncidentModal] = useState(false)
  const [showCommandMenu, setShowCommandMenu] = useState(false)
  const [incidentStatus, setIncidentStatus] = useState('UNACKNOWLEDGED')
  const location = useLocation()

  // Collapsed on tablet
  const [isTablet, setIsTablet] = useState(false)
  useEffect(() => {
    const check = () => setIsTablet(window.innerWidth <= 1024 && window.innerWidth > 768)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  const [isMobile, setIsMobile] = useState(false)
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth <= 768)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  // Trigger mock emergency popup
  useEffect(() => {
    const timer = setTimeout(() => {
      setEmergencyAlert({
        id: 'EV_TR_089',
        severity: 'CRITICAL',
        title: 'Severe Traffic Disruption',
        message: 'Major congestion detected on the Central Corridor.',
        location: 'Central Corridor (Gachibowli to Jubilee Hills)',
        detected: '18:42 IST',
        domain: 'Traffic Intelligence',
        telemetry: 'Average Speed: 8.2 km/h | Queue Length: 350m',
        recommendedAction: 'AI Actuated Signal Phase Override triggered automatically. Deploying manual backup dispatch.',
      })
    }, 8000)
    return () => clearTimeout(timer)
  }, [])

  // ⌘K handler
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setShowCommandMenu(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const collapsed = isTablet
  const sidebarVisible = !isMobile || mobileOpen

  const currentPage = navItems.find(n => n.path === location.pathname)
  const pageTitle = currentPage?.label || 'Dashboard'

  // Reset scroll to top on page navigation for independent scroll state
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [location.pathname])

  // Page-specific serif titles
  const serifTitles = {
    '/dashboard': 'Hyderabad Command Center',
    '/traffic': 'Traffic Intelligence',
    '/pollution': 'Air Quality Intelligence',
    '/energy': 'Energy Consumption',
    '/weather': 'Weather Intelligence',
    '/planning': 'Planning Assistant',
  }
  const serifTitle = serifTitles[location.pathname] || pageTitle

  // Page-specific subtitles
  const subtitles = {
    '/dashboard': 'REAL-TIME OVERVIEW OF CITY OPERATIONS AND KEY METRICS',
    '/traffic': 'Real-time traffic monitoring, analysis, and incident management',
    '/pollution': 'Real-time air quality monitoring, analysis, and predictive insights',
    '/energy': 'Real-time grid monitoring, demand analysis, and energy intelligence',
    '/weather': 'Real-time weather monitoring, forecasts, and severe weather alerts',
    '/planning': 'AI-powered decision support and recommended actions',
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-workspace)' }}>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
            zIndex: 99,
          }}
        />
      )}

      {/* ── Sidebar ─────────────────────────────────────────── */}
      {sidebarVisible && (
        <aside style={{
          width: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
          background: 'var(--bg-sidebar)',
          display: 'flex',
          flexDirection: 'column',
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
          zIndex: 100,
          overflow: 'hidden',
          transition: 'width var(--transition-base)',
        }}>
          {/* Logo Section */}
          <div style={{
            padding: collapsed ? '20px 12px' : '20px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            flexShrink: 0,
          }}>
            <div style={{ flexShrink: 0 }}>
              <LogoIcon />
            </div>
            {!collapsed && (
              <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
                <div style={{
                  fontFamily: "'Sora', sans-serif", fontWeight: 600, fontSize: '0.95rem',
                  color: '#F3F1E8', lineHeight: 1.2, letterSpacing: '0.12em',
                }}>SUPADSP</div>
                <div style={{
                  fontSize: '0.55rem', color: '#A7AE8A',
                  fontFamily: "'Sora', sans-serif", letterSpacing: '0.18em',
                  fontWeight: 500, marginTop: '2px',
                }}>SMART CITY AI</div>
              </div>
            )}
            {isMobile && (
              <button
                onClick={() => setMobileOpen(false)}
                style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-sidebar)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            )}
          </div>

          {/* Navigation */}
          <nav style={{ flex: 1, padding: collapsed ? '16px 8px' : '16px 12px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {navItems.map(item => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  onClick={() => isMobile && setMobileOpen(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    padding: collapsed ? '12px' : '10px 14px',
                    borderRadius: '8px',
                    color: isActive ? 'var(--text-sidebar-active)' : 'var(--text-sidebar)',
                    background: isActive ? 'var(--bg-sidebar-active)' : 'transparent',
                    textDecoration: 'none',
                    fontSize: '0.78rem',
                    fontWeight: isActive ? 600 : 400,
                    transition: 'all var(--transition-fast)',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    cursor: 'pointer',
                    lineHeight: 1.3,
                  }}
                  onMouseEnter={e => {
                    if (!isActive) {
                      e.currentTarget.style.background = 'var(--bg-sidebar-hover)'
                      e.currentTarget.style.color = 'var(--text-sidebar-active)'
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isActive) {
                      e.currentTarget.style.background = 'transparent'
                      e.currentTarget.style.color = 'var(--text-sidebar)'
                    }
                  }}
                >
                  <Icon size={18} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.7 }} />
                  {!collapsed && <span>{item.label}</span>}
                </NavLink>
              )
            })}
          </nav>

          {/* Sidebar Bottom */}
          {!collapsed && (
            <div style={{ padding: '16px', flexShrink: 0 }}>
              <div style={{ color: 'rgba(255,255,255,0.5)', marginBottom: '12px' }}>
                <HyderabadSkyline />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <MapPin size={12} color="#E5483F" />
                <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-sidebar)', letterSpacing: '0.01em' }}>
                  HYDERABAD, INDIA
                </span>
              </div>
              <CurrentTime />
            </div>
          )}
        </aside>
      )}

      {/* ── Main Content Area ─────────────────────────────────── */}
      <div style={{
        flex: 1,
        marginLeft: isMobile ? 0 : (collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)'),
        transition: 'margin-left var(--transition-base)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
      }}>
        {/* Top Header */}
        <header style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          padding: `${isMobile ? '16px' : '28px'} var(--page-padding) 0`,
          flexShrink: 0,
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
              {isMobile && (
                <button
                  onClick={() => setMobileOpen(true)}
                  style={{
                    background: 'none', border: 'none', color: 'var(--text-primary)',
                    cursor: 'pointer', padding: '4px',
                  }}
                >
                  <Menu size={24} />
                </button>
              )}
              <h1 style={{
                fontFamily: 'var(--font-serif)',
                fontSize: isMobile ? '1.6rem' : '2.2rem',
                fontWeight: 600,
                color: 'var(--text-primary)',
                letterSpacing: '-0.01em',
                lineHeight: 1.15,
              }}>
                {serifTitle}
              </h1>
            </div>
            <p style={{
              fontSize: '0.7rem',
              color: 'var(--text-muted)',
              letterSpacing: '0.08em',
              textTransform: location.pathname === '/dashboard' ? 'uppercase' : 'none',
              marginTop: '2px',
            }}>
              {subtitles[location.pathname] || ''}
            </p>
          </div>

          {/* Right header area */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexShrink: 0, paddingTop: '4px' }}>


            {/* Notifications */}
            <button style={{
              position: 'relative', background: 'none', border: 'none',
              color: 'var(--text-secondary)', cursor: 'pointer', padding: '6px',
            }}>
              <Bell size={20} />
              <span style={{
                position: 'absolute', top: 2, right: 2,
                width: 16, height: 16, borderRadius: '50%',
                background: 'var(--accent-warning)',
                color: '#fff', fontSize: '0.6rem', fontWeight: 700,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>3</span>
            </button>

            {/* User avatar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}
              className="hide-mobile"
            >
              <div style={{
                width: 38, height: 38, borderRadius: '50%',
                background: 'linear-gradient(135deg, #8B6F47, #A0845C)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '2px solid var(--border-default)',
                overflow: 'hidden',
              }}>
                <User size={18} color="#fff" />
              </div>
              <div>
                <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.2 }}>Arjun R.</div>
                <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Operations Lead</div>
              </div>
              <ChevronDown size={14} color="var(--text-muted)" />
            </div>
          </div>
        </header>

        {/* Page content */}
        <main style={{
          flex: 1,
          padding: `var(--space-lg) var(--page-padding) var(--space-2xl)`,
          maxWidth: '1600px',
          width: '100%',
        }}>
          <Outlet />
        </main>
      </div>

      {/* ── Global Emergency Popup ── */}
      {emergencyAlert && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '24px',
          width: '340px', zIndex: 1100, padding: '16px',
          display: 'flex', flexDirection: 'column', gap: '12px',
          borderLeft: '4px solid var(--accent-warning)',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-modal)',
        }} className="animate-fade-in-up">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-warning)', fontWeight: 'bold', fontSize: '0.75rem', letterSpacing: '0.05em' }}>
              <AlertOctagon size={14} />
              <span>CRITICAL INCIDENT</span>
            </div>
            <button onClick={() => setEmergencyAlert(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
              <X size={14} />
            </button>
          </div>
          <div>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '2px' }}>{emergencyAlert.title}</h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.3 }}>{emergencyAlert.message}</p>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px', fontFamily: 'var(--font-mono)' }}>
              {emergencyAlert.location}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
            <button
              onClick={() => { setShowIncidentModal(true); setEmergencyAlert(null); }}
              style={{
                flex: 1, padding: '6px 12px', background: 'var(--accent-warning-dim)', color: 'var(--accent-warning)',
                border: '1px solid rgba(229,72,63,0.2)', borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s'
              }}
            >
              View Incident
            </button>
            <button
              onClick={() => setEmergencyAlert(null)}
              style={{
                padding: '6px 12px', background: 'var(--bg-workspace)', color: 'var(--text-secondary)',
                border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem', cursor: 'pointer'
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ── Incident Modal ── */}
      {showIncidentModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1200,
          background: 'var(--bg-overlay)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px'
        }}>
          <div style={{
            width: '100%', maxWidth: '800px', background: 'var(--bg-card)',
            border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-modal)', overflow: 'hidden', display: 'flex', flexDirection: 'column'
          }} className="animate-fade-in-up">
            {/* Modal Header */}
            <div style={{
              padding: '16px 24px', borderBottom: '1px solid var(--border-default)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-workspace)'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-warning)', fontSize: '0.7rem', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>
                  <AlertOctagon size={14} />
                  <span>CRITICAL SPATIAL INCIDENT</span>
                </div>
                <h3 style={{ fontSize: '1.2rem', marginTop: '2px', fontWeight: 600 }}>Event ID: EV_TR_089</h3>
              </div>
              <button
                onClick={() => { setShowIncidentModal(false); setIncidentStatus('UNACKNOWLEDGED'); }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '20px', padding: '24px' }}>
              {/* GIS Context */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  GIS SPATIAL DIGITAL TWIN CONTEXT
                </span>
                <div style={{
                  flex: 1, minHeight: '240px', background: 'var(--bg-workspace)',
                  border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
                  position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <svg width="100%" height="100%" viewBox="0 0 200 200" style={{ position: 'absolute', inset: 0 }}>
                    <line x1="0" y1="50" x2="200" y2="50" stroke="rgba(0,0,0,0.04)" strokeWidth="1" />
                    <line x1="0" y1="100" x2="200" y2="100" stroke="rgba(0,0,0,0.04)" strokeWidth="1" />
                    <line x1="0" y1="150" x2="200" y2="150" stroke="rgba(0,0,0,0.04)" strokeWidth="1" />
                    <line x1="50" y1="0" x2="50" y2="200" stroke="rgba(0,0,0,0.04)" strokeWidth="1" />
                    <line x1="100" y1="0" x2="100" y2="200" stroke="rgba(0,0,0,0.04)" strokeWidth="1" />
                    <line x1="150" y1="0" x2="150" y2="200" stroke="rgba(0,0,0,0.04)" strokeWidth="1" />
                    <path d="M 20 100 L 180 100" stroke="rgba(0,0,0,0.08)" strokeWidth="4" strokeLinecap="round" />
                    <path d="M 100 20 L 100 180" stroke="rgba(0,0,0,0.08)" strokeWidth="4" strokeLinecap="round" />
                    <path d="M 60 100 L 140 100" stroke="var(--accent-warning)" strokeWidth="6" strokeLinecap="round" style={{ opacity: 0.95 }} />
                    <circle cx="60" cy="100" r="5" fill="var(--accent-warning)" />
                    <circle cx="100" cy="100" r="7" fill="var(--accent-warning)" style={{ animation: 'pulse-glow 1.5s infinite' }} />
                    <circle cx="140" cy="100" r="5" fill="var(--accent-warning)" />
                    <text x="50" y="90" fill="var(--text-muted)" fontSize="6" fontFamily="var(--font-mono)">Gachibowli</text>
                    <text x="88" y="115" fill="var(--accent-warning)" fontSize="7" fontFamily="var(--font-mono)" fontWeight="bold">Central Corridor</text>
                    <text x="130" y="90" fill="var(--text-muted)" fontSize="6" fontFamily="var(--font-mono)">Jubilee Hills</text>
                  </svg>
                  <div style={{
                    position: 'absolute', top: '10px', right: '10px',
                    padding: '6px 10px', borderRadius: 'var(--radius-sm)',
                    fontSize: '0.65rem', fontFamily: 'var(--font-mono)', fontWeight: 600,
                    background: 'var(--bg-card)', border: '1px solid var(--border-default)',
                    color: 'var(--accent-traffic)'
                  }}>
                    MapLibre GL · Active View
                  </div>
                </div>
              </div>

              {/* Details */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>INCIDENT LOCATION</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                    <MapPin size={14} color="var(--accent-warning)" />
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>Central Corridor Area</span>
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>METRIC TELEMETRY</span>
                  <div style={{
                    marginTop: '4px', padding: '10px', background: 'var(--bg-workspace)',
                    border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                    fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.5
                  }}>
                    <div>• Average Speed: <strong style={{ color: 'var(--accent-warning)' }}>8.2 km/h</strong></div>
                    <div>• Queue Length: <strong style={{ color: 'var(--accent-warning)' }}>350 meters</strong></div>
                    <div>• Estimated Delay: <strong style={{ color: 'var(--accent-warning)' }}>145 seconds</strong></div>
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>RESPONSIBLE DOMAIN</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                    <span className="badge badge-heavy" style={{ fontSize: '0.7rem' }}>Traffic Intelligence</span>
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>AI RECOMMENDATION</span>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: '2px' }}>
                    AI Actuated Signal Phase Override triggered automatically. Deploying manual backup dispatch.
                  </p>
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>FLOW EVENT STATE</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                    {incidentStatus === 'UNACKNOWLEDGED' && <span className="badge badge-heavy" style={{ fontSize: '0.65rem' }}>Awaiting Acknowledgement</span>}
                    {incidentStatus === 'ACKNOWLEDGED' && <span className="badge badge-moderate" style={{ fontSize: '0.65rem' }}>Acknowledged · Deploying Response</span>}
                    {incidentStatus === 'RESOLVED' && <span className="badge badge-smooth" style={{ fontSize: '0.65rem' }}>Resolved · Closed</span>}
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '16px 24px', borderTop: '1px solid var(--border-default)',
              display: 'flex', justifyContent: 'flex-end', gap: '10px', background: 'var(--bg-workspace)'
            }}>
              {incidentStatus === 'UNACKNOWLEDGED' && (
                <button
                  onClick={() => setIncidentStatus('ACKNOWLEDGED')}
                  style={{
                    padding: '8px 16px', background: 'var(--accent-traffic)', color: '#fff',
                    border: 'none', borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  Acknowledge Incident
                </button>
              )}
              {incidentStatus === 'ACKNOWLEDGED' && (
                <button
                  onClick={() => { setIncidentStatus('RESOLVED'); setTimeout(() => setShowIncidentModal(false), 800); }}
                  style={{
                    padding: '8px 16px', background: 'var(--accent-traffic)', color: '#fff',
                    border: 'none', borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer'
                  }}
                >
                  Mark Resolved
                </button>
              )}
              <button
                onClick={() => { setShowIncidentModal(false); setIncidentStatus('UNACKNOWLEDGED'); }}
                style={{
                  padding: '8px 16px', background: 'var(--bg-card)', color: 'var(--text-secondary)',
                  border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                  fontSize: '0.8rem', cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Command Menu */}
      <CommandMenu isOpen={showCommandMenu} onClose={() => setShowCommandMenu(false)} />

      {/* Mobile-hide helper style */}
      <style>{`
        .hide-mobile { display: flex; }
        @media (max-width: 768px) {
          .hide-mobile { display: none !important; }
        }
      `}</style>
    </div>
  )
}

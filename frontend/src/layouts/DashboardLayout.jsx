import { useState, useEffect } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Car, Wind, Zap, CloudSun, Brain,
  ChevronLeft, ChevronRight, Bell, Search, User, Activity,
  Cpu, Shield, Menu, MapPin, X, AlertOctagon, CheckCircle2
} from 'lucide-react'
import CommandMenu from '../components/cult-ui/CommandMenu'

const navItems = [
  { path: '/dashboard', label: 'Command Center', icon: LayoutDashboard },
  { path: '/traffic', label: 'Traffic Intelligence', icon: Car },
  { path: '/pollution', label: 'Air Quality', icon: Wind },
  { path: '/energy', label: 'Energy Grid', icon: Zap },
  { path: '/weather', label: 'Weather Intel', icon: CloudSun },
  { path: '/planning', label: 'Planning Assistant', icon: Brain },
]

export default function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [emergencyAlert, setEmergencyAlert] = useState(null)
  const [showIncidentModal, setShowIncidentModal] = useState(false)
  const [showCommandMenu, setShowCommandMenu] = useState(false)
  const [incidentStatus, setIncidentStatus] = useState('UNACKNOWLEDGED') // UNACKNOWLEDGED, ACKNOWLEDGED, RESOLVED
  const location = useLocation()

  // Trigger a mock emergency popup after 8 seconds of mount
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

  const currentPage = navItems.find(n => n.path === location.pathname)

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          onClick={() => setMobileOpen(false)}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
            zIndex: 99, display: 'none',
          }}
          className="mobile-overlay"
        />
      )}

      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside style={{
        width: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border-default)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width var(--transition-base)',
        position: 'fixed',
        top: 0,
        left: 0,
        bottom: 0,
        zIndex: 100,
        overflow: 'hidden',
      }}>
        {/* Logo */}
        <div style={{
          height: 'var(--topbar-height)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          gap: '12px',
          borderBottom: '1px solid var(--border-default)',
          flexShrink: 0,
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 'var(--radius-md)',
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-violet))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <Cpu size={20} color="#fff" />
          </div>
          {!collapsed && (
            <div style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>
              <div style={{
                fontFamily: 'var(--font-heading)', fontWeight: 700, fontSize: '0.95rem',
                color: 'var(--text-primary)', lineHeight: 1.2,
              }}>SUPADSP</div>
              <div style={{
                fontSize: '0.65rem', color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
              }}>SMART CITY AI</div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navItems.map(item => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <NavLink
                key={item.path}
                to={item.path}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: collapsed ? '12px' : '10px 16px',
                  borderRadius: 'var(--radius-md)',
                  color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  background: isActive ? 'var(--accent-cyan-dim)' : 'transparent',
                  border: isActive ? '1px solid rgba(0,240,255,0.2)' : '1px solid transparent',
                  textDecoration: 'none',
                  fontSize: '0.875rem',
                  fontWeight: isActive ? 600 : 400,
                  transition: 'all var(--transition-fast)',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  position: 'relative',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'var(--bg-elevated)'
                    e.currentTarget.style.color = 'var(--text-primary)'
                  }
                }}
                onMouseLeave={e => {
                  if (!isActive) {
                    e.currentTarget.style.background = 'transparent'
                    e.currentTarget.style.color = 'var(--text-secondary)'
                  }
                }}
              >
                {isActive && (
                  <div style={{
                    position: 'absolute', left: -8, top: '50%', transform: 'translateY(-50%)',
                    width: 3, height: 20, borderRadius: 2,
                    background: 'var(--accent-cyan)',
                    boxShadow: '0 0 8px var(--accent-cyan)',
                  }} />
                )}
                <Icon size={20} style={{ flexShrink: 0 }} />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            )
          })}
        </nav>

        {/* Collapse toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            margin: '8px', padding: '10px',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-primary)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all var(--transition-fast)',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--border-hover)'; e.currentTarget.style.color = 'var(--accent-cyan)' }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-default)'; e.currentTarget.style.color = 'var(--text-secondary)' }}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        {/* System Status */}
        {!collapsed && (
          <div style={{
            margin: '8px', padding: '12px',
            background: 'var(--bg-primary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-default)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Shield size={14} color="var(--accent-emerald)" />
              <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                SYSTEM STATUS
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-emerald)', boxShadow: '0 0 8px var(--accent-emerald)' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--accent-emerald)', fontWeight: 600 }}>All Systems Operational</span>
            </div>
          </div>
        )}
      </aside>

      {/* ── Main Content Area ─────────────────────────────────────── */}
      <div style={{
        flex: 1,
        marginLeft: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
        transition: 'margin-left var(--transition-base)',
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
      }}>
        {/* Top Bar */}
        <header style={{
          height: 'var(--topbar-height)',
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border-default)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          position: 'sticky',
          top: 0,
          zIndex: 50,
          backdropFilter: 'blur(12px)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              style={{
                background: 'none', border: 'none', color: 'var(--text-secondary)',
                cursor: 'pointer', display: 'none',
              }}
              className="mobile-menu-btn"
            >
              <Menu size={24} />
            </button>
            <div>
              <h2 style={{ fontSize: '1.125rem', fontWeight: 600 }}>{currentPage?.label || 'Dashboard'}</h2>
              <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                HYDERABAD URBAN AI PLATFORM
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              onClick={() => setShowCommandMenu(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '6px 12px', borderRadius: 'var(--radius-full)',
                background: 'var(--bg-primary)', border: '1px solid var(--border-default)',
                fontSize: '0.75rem', color: 'var(--text-muted)', cursor: 'pointer',
              }}
            >
              <Search size={14} />
              <span>Search...</span>
              <kbd style={{
                padding: '2px 6px', borderRadius: '4px', fontSize: '0.65rem',
                background: 'var(--bg-tertiary)', border: '1px solid var(--border-default)',
              }}>⌘K</kbd>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                padding: '4px 8px', borderRadius: 'var(--radius-full)',
                background: 'var(--accent-emerald-dim)',
              }}>
                <Activity size={12} color="var(--accent-emerald)" />
                <span style={{ fontSize: '0.7rem', color: 'var(--accent-emerald)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>LIVE</span>
              </div>
            </div>
            <button style={{
              position: 'relative', background: 'none', border: 'none',
              color: 'var(--text-secondary)', cursor: 'pointer', padding: '8px',
            }}>
              <Bell size={20} />
              <span style={{
                position: 'absolute', top: 4, right: 4,
                width: 8, height: 8, borderRadius: '50%',
                background: 'var(--accent-rose)',
                boxShadow: '0 0 8px var(--accent-rose)',
              }} />
            </button>
            <div style={{
              width: 34, height: 34, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-violet))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', border: '2px solid var(--bg-primary)',
            }}>
              <User size={16} color="#fff" />
            </div>
          </div>
        </header>

        {/* Page content */}
        <main style={{
          flex: 1,
          padding: 'var(--space-xl)',
          maxWidth: '1600px',
          width: '100%',
          margin: '0 auto',
        }}>
          <Outlet />
        </main>
      </div>

      {/* ── Global Emergency Popup system (High Priority Red Accent) ── */}
      {emergencyAlert && (
        <div style={{
          position: 'fixed', bottom: '24px', right: '24px',
          width: '320px', zIndex: 1100, padding: '16px',
          display: 'flex', flexDirection: 'column', gap: '12px',
          borderLeft: '4px solid var(--accent-rose)'
        }} className="glass animate-fade-in-up">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--accent-rose)', fontWeight: 'bold', fontSize: '0.75rem', letterSpacing: '0.05em' }}>
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
                flex: 1, padding: '6px 12px', background: 'var(--accent-rose-dim)', color: 'var(--accent-rose)',
                border: '1px solid rgba(225,29,72,0.3)', borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s'
              }}
            >
              View Incident
            </button>
            <button
              onClick={() => setEmergencyAlert(null)}
              style={{
                padding: '6px 12px', background: 'var(--bg-primary)', color: 'var(--text-secondary)',
                border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem', cursor: 'pointer'
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ── Global GIS/Incident Context View Modal ── */}
      {showIncidentModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1200,
          background: 'rgba(5, 8, 16, 0.85)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px'
        }}>
          <div style={{
            width: '100%', maxWidth: '800px', background: 'var(--bg-secondary)',
            border: '1px solid var(--border-default)', borderRadius: 'var(--radius-lg)',
            boxShadow: 'var(--shadow-elevated)', overflow: 'hidden', display: 'flex', flexDirection: 'column'
          }} className="animate-fade-in-up">
            {/* Modal Header */}
            <div style={{
              padding: '16px 24px', borderBottom: '1px solid var(--border-default)',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-primary)'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-rose)', fontSize: '0.7rem', fontWeight: 'bold', fontFamily: 'var(--font-mono)' }}>
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
              {/* Spatial/GIS Digital Twin Mock Context */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                  GIS SPATIAL DIGITAL TWIN CONTEXT
                </span>
                <div style={{
                  flex: 1, minHeight: '240px', background: 'var(--bg-primary)',
                  border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)',
                  position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <svg width="100%" height="100%" viewBox="0 0 200 200" style={{ position: 'absolute', inset: 0 }}>
                    <line x1="0" y1="50" x2="200" y2="50" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                    <line x1="0" y1="100" x2="200" y2="100" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                    <line x1="0" y1="150" x2="200" y2="150" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                    <line x1="50" y1="0" x2="50" y2="200" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                    <line x1="100" y1="0" x2="100" y2="200" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                    <line x1="150" y1="0" x2="150" y2="200" stroke="rgba(255,255,255,0.03)" strokeWidth="1" />
                    <path d="M 20 100 L 180 100" stroke="rgba(255,255,255,0.1)" strokeWidth="4" strokeLinecap="round" />
                    <path d="M 100 20 L 100 180" stroke="rgba(255,255,255,0.1)" strokeWidth="4" strokeLinecap="round" />
                    <path d="M 60 100 L 140 100" stroke="var(--accent-rose)" strokeWidth="6" strokeLinecap="round" style={{ opacity: 0.95 }} />
                    <circle cx="60" cy="100" r="5" fill="var(--accent-rose)" />
                    <circle cx="100" cy="100" r="7" fill="var(--accent-rose)" style={{ animation: 'pulse-glow 1.5s infinite' }} />
                    <circle cx="140" cy="100" r="5" fill="var(--accent-rose)" />
                    <text x="50" y="90" fill="var(--text-muted)" fontSize="6" fontFamily="var(--font-mono)">Gachibowli</text>
                    <text x="95" y="115" fill="var(--accent-rose)" fontSize="7" fontFamily="var(--font-mono)" fontWeight="bold">Central Corridor</text>
                    <text x="135" y="90" fill="var(--text-muted)" fontSize="6" fontFamily="var(--font-mono)">Jubilee Hills</text>
                  </svg>
                  <div style={{
                    position: 'absolute', top: '10px', right: '10px',
                    padding: '6px 10px', borderRadius: 'var(--radius-sm)',
                    fontSize: '0.65rem', fontFamily: 'var(--font-mono)', fontWeight: 600,
                    background: 'var(--bg-glass)', border: '1px solid var(--border-default)',
                    color: 'var(--accent-cyan)'
                  }}>
                    MapLibre GL · Active View
                  </div>
                </div>
              </div>

              {/* Details & Telemetry */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>INCIDENT LOCATION</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                    <MapPin size={14} color="var(--accent-rose)" />
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                      Central Corridor Area
                    </span>
                  </div>
                </div>
                <div>
                  <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>METRIC TELEMETRY</span>
                  <div style={{
                    marginTop: '4px', padding: '10px', background: 'var(--bg-primary)',
                    border: '1px solid var(--border-default)', borderRadius: 'var(--radius-sm)',
                    fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.5
                  }}>
                    <div>• Average Speed: <strong style={{ color: 'var(--accent-rose)' }}>8.2 km/h</strong></div>
                    <div>• Queue Length: <strong style={{ color: 'var(--accent-rose)' }}>350 meters</strong></div>
                    <div>• Estimated Delay: <strong style={{ color: 'var(--accent-rose)' }}>145 seconds</strong></div>
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

            {/* Modal Footer Controls */}
            <div style={{
              padding: '16px 24px', borderTop: '1px solid var(--border-default)',
              display: 'flex', justifyContent: 'flex-end', gap: '10px', background: 'var(--bg-primary)'
            }}>
              {incidentStatus === 'UNACKNOWLEDGED' && (
                <button
                  onClick={() => setIncidentStatus('ACKNOWLEDGED')}
                  style={{
                    padding: '8px 16px', background: 'var(--accent-cyan)', color: '#fff',
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
                    padding: '8px 16px', background: 'var(--accent-emerald)', color: '#fff',
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
                  padding: '8px 16px', background: 'var(--bg-secondary)', color: 'var(--text-secondary)',
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

      {/* Cult UI Command Menu Modal */}
      <CommandMenu isOpen={showCommandMenu} onClose={() => setShowCommandMenu(false)} />
    </div>
  )
}

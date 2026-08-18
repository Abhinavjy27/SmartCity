import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search, LayoutDashboard, Car, Wind, Zap, CloudSun, Brain,
  X, ArrowRight, Activity, MapPin, Shield
} from 'lucide-react'

export default function CommandMenu({ isOpen, onClose }) {
  const [query, setQuery] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        if (isOpen) onClose()
        else {
          // Open triggered by parent if passed, or handled via global listener
        }
      }
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const navigationItems = [
    { label: 'Command Center Dashboard', path: '/dashboard', icon: LayoutDashboard, category: 'Navigation' },
    { label: 'Traffic Intelligence & Signals', path: '/traffic', icon: Car, category: 'Navigation' },
    { label: 'Air Quality & TSPCB Stations', path: '/pollution', icon: Wind, category: 'Navigation' },
    { label: 'Energy Grid & Load Shaving', path: '/energy', icon: Zap, category: 'Navigation' },
    { label: 'Weather Intel & Forecast', path: '/weather', icon: CloudSun, category: 'Navigation' },
    { label: 'AI Planning Assistant Workspace', path: '/planning', icon: Brain, category: 'Navigation' },
  ]

  const quickActions = [
    { label: 'Run Traffic Signal Optimization (Hitec City)', action: () => navigate('/traffic'), icon: Activity, category: 'Actions' },
    { label: 'Inspect Central Corridor Spatial Incident', action: () => navigate('/dashboard'), icon: MapPin, category: 'Actions' },
    { label: 'View AI Domain Agent Operational Health', action: () => navigate('/planning'), icon: Shield, category: 'Actions' },
  ]

  const allItems = [...navigationItems, ...quickActions]
  const filtered = allItems.filter(item => item.label.toLowerCase().includes(query.toLowerCase()))

  const handleSelect = (item) => {
    if (item.path) {
      navigate(item.path)
    } else if (item.action) {
      item.action()
    }
    onClose()
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 2000,
      background: 'rgba(5, 8, 16, 0.75)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
      paddingTop: '15vh',
    }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: '600px',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-hover)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-elevated)',
          overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}
        className="animate-fade-in-up"
      >
        {/* Search Header */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          padding: '16px 20px', borderBottom: '1px solid var(--border-default)',
          background: 'var(--bg-primary)',
        }}>
          <Search size={18} color="var(--accent-cyan)" />
          <input
            type="text"
            placeholder="Type a command, query, or navigate..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
            style={{
              flex: 1, background: 'none', border: 'none', outline: 'none',
              color: 'var(--text-primary)', fontSize: '0.95rem',
              fontFamily: 'var(--font-body)',
            }}
          />
          <kbd style={{
            padding: '2px 6px', borderRadius: '4px', fontSize: '0.7rem',
            background: 'var(--bg-tertiary)', border: '1px solid var(--border-default)',
            color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
          }}>ESC</kbd>
        </div>

        {/* Results List */}
        <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '8px' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No matching commands or navigation targets found.
            </div>
          ) : (
            filtered.map((item, idx) => {
              const Icon = item.icon
              return (
                <div
                  key={idx}
                  onClick={() => handleSelect(item)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 16px', borderRadius: 'var(--radius-md)',
                    cursor: 'pointer', transition: 'all 0.15s ease',
                    marginBottom: '2px',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--bg-elevated)'
                    e.currentTarget.style.borderColor = 'var(--border-hover)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Icon size={18} color="var(--accent-cyan)" />
                    <span style={{ fontSize: '0.875rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                      {item.label}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{
                      fontSize: '0.65rem', fontFamily: 'var(--font-mono)',
                      color: 'var(--text-muted)', textTransform: 'uppercase',
                    }}>
                      {item.category}
                    </span>
                    <ArrowRight size={14} color="var(--text-muted)" />
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '10px 20px', borderTop: '1px solid var(--border-default)',
          background: 'var(--bg-primary)', display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', fontSize: '0.7rem', color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}>
          <span>Cult UI · Smart Command Palette</span>
          <span>Press ↵ to select</span>
        </div>
      </div>
    </div>
  )
}

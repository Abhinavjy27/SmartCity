import { useState } from 'react'
import {
  Sparkles, Send, Paperclip, ThumbsUp, ThumbsDown, Copy,
  AlertTriangle, ChevronRight, ChevronLeft, ArrowRight,
  Car, Wind, Zap, Droplets, Plus, Check, SlidersHorizontal,
  Bot, User, ExternalLink, RefreshCw
} from 'lucide-react'

/* ── Active Alerts Data ── */
const activeAlerts = [
  {
    id: 'ALT_01',
    title: 'Evening Traffic Gridlock',
    location: 'Gachibowli Flyover & Mindspace Corridor',
    domain: 'Traffic & Mobility',
    domainIcon: Car,
    status: 'Ongoing',
    impact: 'High Impact',
    impactColor: '#E5483F',
    time: '10:18 AM',
    solutions: [
      {
        id: 1,
        title: 'Optimize Signal Phasing',
        desc: 'Implement adaptive signal control on Outer Ring Road junction to reduce delays.',
        impactLabel: 'ETA Impact',
        impactValue: '-22% Delay',
        impactColor: '#2F8F72',
        confidence: '92%',
        color: '#2F8F72',
        details: 'Adjusts split times dynamically at 6 intersections along Outer Ring Road to favor east-west discharge during evening rush.'
      },
      {
        id: 2,
        title: 'Dynamic Route Diversion',
        desc: 'Divert traffic via Financial District bypass & Wipro Junction.',
        impactLabel: 'ETA Impact',
        impactValue: '-18% Volume',
        impactColor: '#2563EB',
        confidence: '89%',
        color: '#2563EB',
        details: 'Variable message signs activated to reroute airport-bound traffic onto Outer Ring Road Service Lane 3.'
      },
      {
        id: 3,
        title: 'Public Transit Reinforcement',
        desc: 'Deploy 20 additional shuttle buses & increase metro frequency.',
        impactLabel: 'ETA Impact',
        impactValue: '+15% Capacity',
        impactColor: '#8B5CF6',
        confidence: '87%',
        color: '#8B5CF6',
        details: 'Hyderabad Metro frequency boosted to 3.5 min headway on Blue Line between Raidurg and Ameerpet.'
      },
      {
        id: 4,
        title: 'Commuter Communication',
        desc: 'Push real-time alerts & alternate route suggestions to commuters.',
        impactLabel: 'ETA Impact',
        impactValue: 'High Awareness',
        impactColor: '#F59E0B',
        confidence: '84%',
        color: '#F59E0B',
        details: 'Push notification sent to 142k active Hyderabad Transit app users recommending staggered departure.'
      }
    ]
  },
  {
    id: 'ALT_02',
    title: 'Severe PM2.5 Spike',
    location: 'Nacharam & Sanathnagar',
    domain: 'Air Quality',
    domainIcon: Wind,
    status: 'Ongoing',
    impact: 'Moderate Impact',
    impactColor: '#F59E0B',
    time: '10:15 AM',
    solutions: [
      {
        id: 1,
        title: 'Industrial Mist Spraying',
        desc: 'Activate anti-smog mist cannons in Nacharam industrial cluster.',
        impactLabel: 'PM2.5 Impact',
        impactValue: '-34 μg/m³',
        impactColor: '#4C9E9B',
        confidence: '94%',
        color: '#4C9E9B',
        details: '8 mobile mist cannons dispatched to major industrial emission zones.'
      },
      {
        id: 2,
        title: 'Heavy Vehicle Restriction',
        desc: 'Divert non-electric freight traffic to Outer Ring Road perimeter.',
        impactLabel: 'PM2.5 Impact',
        impactValue: '-20% Emissions',
        impactColor: '#2563EB',
        confidence: '88%',
        color: '#2563EB',
        details: 'Restricts BS-IV and older commercial trucks from entering Inner Ring Road during peak hours.'
      },
      {
        id: 3,
        title: 'Public Health Advisory',
        desc: 'Broadcast air quality advisory to schools and senior citizen centers.',
        impactLabel: 'Exposure Impact',
        impactValue: '-45% Risk',
        impactColor: '#8B5CF6',
        confidence: '91%',
        color: '#8B5CF6',
        details: 'Automated SMS alerts sent to 18 healthcare facilities and 42 local schools.'
      },
      {
        id: 4,
        title: 'Factory Compliance Check',
        desc: 'Trigger automatic telemetry audit on 14 registered boiler units.',
        impactLabel: 'Audit Status',
        impactValue: 'Immediate',
        impactColor: '#F59E0B',
        confidence: '86%',
        color: '#F59E0B',
        details: 'Automated notification dispatched to TSPCB enforcement team.'
      }
    ]
  },
  {
    id: 'ALT_03',
    title: 'Peak Power Load',
    location: 'HiTech City Substation',
    domain: 'Energy',
    domainIcon: Zap,
    status: 'Monitoring',
    impact: 'Moderate Impact',
    impactColor: '#F59E0B',
    time: '10:12 AM',
    solutions: [
      {
        id: 1,
        title: 'Battery Storage Discharge',
        desc: 'Discharge 45 MWh from Madhapur BESS grid battery bank.',
        impactLabel: 'Grid Impact',
        impactValue: '-12% Peak Load',
        impactColor: '#F59E0B',
        confidence: '95%',
        color: '#F59E0B',
        details: 'BESS dispatch stabilizes local frequency at 50.02 Hz.'
      },
      {
        id: 2,
        title: 'Commercial Demand Response',
        desc: 'Signal 28 IT parks to switch non-critical HVAC to chiller backup.',
        impactLabel: 'Grid Impact',
        impactValue: '-28 MW Peak',
        impactColor: '#2563EB',
        confidence: '90%',
        color: '#2563EB',
        details: 'Automated OpenADR signal sent to enrolled corporate campuses.'
      },
      {
        id: 3,
        title: 'Substation Load Transfer',
        desc: 'Re-route 15 MW to neighboring Gachibowli 220kV feeder.',
        impactLabel: 'Grid Impact',
        impactValue: 'Balanced',
        impactColor: '#8B5CF6',
        confidence: '88%',
        color: '#8B5CF6',
        details: 'Feeder tie-switch automated actuation completed in 45 seconds.'
      },
      {
        id: 4,
        title: 'Renewable Ramp-up',
        desc: 'Call on Ramagundam solar firm capacity to bridge afternoon demand.',
        impactLabel: 'Clean Energy',
        impactValue: '+30 MW',
        impactColor: '#2F8F72',
        confidence: '85%',
        color: '#2F8F72',
        details: 'Ensures grid reserves remain above 18% safety threshold.'
      }
    ]
  },
  {
    id: 'ALT_04',
    title: 'Water Supply Leak',
    location: 'Ameerpet Distribution Line',
    domain: 'Water & Utilities',
    domainIcon: Droplets,
    status: 'Investigating',
    impact: 'Low Impact',
    impactColor: '#6C8FC5',
    time: '10:06 AM',
    solutions: [
      {
        id: 1,
        title: 'Sector Valve Isolation',
        desc: 'Isolate section 4B-12 on Ameerpet main line to stop pressure loss.',
        impactLabel: 'Water Loss',
        impactValue: '-85% Loss',
        impactColor: '#2563EB',
        confidence: '96%',
        color: '#2563EB',
        details: 'Automated SCADA valve shutoff prevents road sub-base erosion.'
      },
      {
        id: 2,
        title: 'Secondary Route Supply',
        desc: 'Supply essential water flow via Somajiguda secondary feeder.',
        impactLabel: 'Supply Continuity',
        impactValue: '98% Maintained',
        impactColor: '#2F8F72',
        confidence: '91%',
        color: '#2F8F72',
        details: 'Ensures hospitals and residences experience zero outage.'
      },
      {
        id: 3,
        title: 'Rapid Repair Dispatch',
        desc: 'Dispatch emergency repair crew with ultrasonic leak locator.',
        impactLabel: 'ETA Repair',
        impactValue: '~90 Mins',
        impactColor: '#F59E0B',
        confidence: '89%',
        color: '#F59E0B',
        details: 'Crew unit HMWSSB-E4 en route from Panjagutta depot.'
      },
      {
        id: 4,
        title: 'Traffic Caution Alert',
        desc: 'Coordinate with Traffic Police for single-lane road maintenance.',
        impactLabel: 'Traffic Delay',
        impactValue: 'Minimal',
        impactColor: '#8B5CF6',
        confidence: '85%',
        color: '#8B5CF6',
        details: 'Traffic cone buffer installed 50m upstream of work zone.'
      }
    ]
  }
]

export default function Planning() {
  const [selectedAlertIndex, setSelectedAlertIndex] = useState(0)
  const [solutionSetIndex, setSolutionSetIndex] = useState(1)
  const [inputQuery, setInputQuery] = useState('')
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'user',
      time: '10:18 AM',
      text: 'What actions can we take to reduce the traffic congestion at Gachibowli Flyover this evening?'
    },
    {
      id: 2,
      sender: 'ai',
      time: '10:18 AM',
      text: 'Based on real-time data, historical patterns, and similar event analysis, here are the most effective actions to reduce congestion in this corridor.',
      insights: [
        'Peak congestion is driven by office exit traffic between 5 PM - 8 PM.',
        'Outer Ring Road exchange is the main bottleneck with ~3.4 km queue.',
        'Diversion and signal optimization can significantly reduce travel time.'
      ],
      suggestions: [
        'What if we extend green time by 20%?',
        'Show impact of dynamic diversion',
        'Compare with last Monday'
      ]
    }
  ])
  const [isThinking, setIsThinking] = useState(false)
  const [copiedId, setCopiedId] = useState(null)
  const [selectedSolution, setSelectedSolution] = useState(null)
  const [showScenarioModal, setShowScenarioModal] = useState(false)

  const activeAlert = activeAlerts[selectedAlertIndex]

  const handleSendMessage = (text) => {
    const q = text || inputQuery
    if (!q.trim()) return

    const userMsg = {
      id: Date.now(),
      sender: 'user',
      time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }),
      text: q
    }

    setMessages(prev => [...prev, userMsg])
    setInputQuery('')
    setIsThinking(true)

    setTimeout(() => {
      let aiResponseText = `Based on current multi-domain telemetry for ${activeAlert.location}, the AI simulation projects high confidence in adaptive interventions.`
      let insights = [
        `Corridor flow efficiency can improve by ~22% with synchronized signal timing.`,
        `Alternative routes via Wipro Junction can absorb up to 1,200 vehicles/hour.`,
        `Real-time commuter rerouting reduces bottle-neck queue duration by ~35 minutes.`
      ]
      let suggestions = [
        'Simulate 30-min signal phase change',
        'Check public transit backup capacity',
        'Export operational action plan'
      ]

      if (q.toLowerCase().includes('green time') || q.toLowerCase().includes('signal')) {
        aiResponseText = `Simulating +20% green time on Gachibowli Outer Ring Road approaches:`
        insights = [
          'Throughput increases from 2,100 vph to 2,540 vph (+21%).',
          'Average junction queue clears 14 minutes faster before 7:30 PM.',
          'Cross-corridor delay on Financial District road increases marginally by 8 seconds.'
        ]
      } else if (q.toLowerCase().includes('diversion') || q.toLowerCase().includes('route')) {
        aiResponseText = `Dynamic diversion analysis via Financial District Bypass & Wipro Junction:`
        insights = [
          'Expected traffic reduction on main flyover: 18% (-620 vph).',
          'Travel time for diverted vehicles increases by only 3.2 minutes.',
          'Overall network congestion index drops from 88% (Severe) to 64% (Moderate).'
        ]
      } else if (q.toLowerCase().includes('monday') || q.toLowerCase().includes('compare')) {
        aiResponseText = `Comparison against Last Monday (Jun 5, 2025):`
        insights = [
          'Peak volume is currently +4.2% higher due to return-to-office schedules.',
          'Weather conditions are clear (29°C), reducing rain-induced slowdowns.',
          'Previous automated signal adjustment on Jun 5 yielded a 19% delay reduction.'
        ]
      }

      const aiMsg = {
        id: Date.now() + 1,
        sender: 'ai',
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }),
        text: aiResponseText,
        insights,
        suggestions
      }

      setMessages(prev => [...prev, aiMsg])
      setIsThinking(false)
    }, 900)
  }

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const handleNewConversation = () => {
    setMessages([
      {
        id: Date.now(),
        sender: 'ai',
        time: new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true }),
        text: `Planning AI initialized for ${activeAlert.location}. How can I assist with scenario analysis, decision recommendations, or impact evaluation?`,
        insights: [
          `Active Incident: ${activeAlert.title} (${activeAlert.impact}).`,
          `Domain telemetry monitored live across 52 city sensors.`,
          `Ready to run what-if simulations and dispatch action directives.`
        ],
        suggestions: [
          'What are the best immediate mitigation actions?',
          'Run cross-domain impact check',
          'Generate operational summary report'
        ]
      }
    ])
  }

  return (
    <div className="stagger-children" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-lg)' }}>
      {/* ── Filter Pills Row ───────────────────────────────── */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        flexWrap: 'wrap',
        fontSize: '0.75rem',
      }}>
        {/* Active Domain Pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-full)',
          padding: '6px 14px',
          boxShadow: 'var(--shadow-card)',
        }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Active Domain:</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: 'var(--text-primary)' }}>
            <Car size={14} color="#E5483F" />
            <span>{activeAlert.domain}</span>
          </div>
        </div>

        {/* Active Alert Pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-full)',
          padding: '6px 14px',
          boxShadow: 'var(--shadow-card)',
        }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Active Alert:</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: 'var(--text-primary)' }}>
            <AlertTriangle size={14} color="#E5483F" />
            <span>{activeAlert.title}</span>
          </div>
        </div>

        {/* Location Pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-full)',
          padding: '6px 14px',
          boxShadow: 'var(--shadow-card)',
        }}>
          <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>Location:</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: 'var(--text-primary)' }}>
            <span style={{ color: '#E5483F' }}>📍</span>
            <span>{activeAlert.location}</span>
          </div>
        </div>
      </div>

      {/* ── Main Planning AI Card ───────────────────────────── */}
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border-card)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px',
        boxShadow: 'var(--shadow-card)',
      }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: '20px',
          borderBottom: '1px solid var(--border-divider)',
          paddingBottom: '16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: 38,
              height: 38,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 8px rgba(37,99,235,0.25)',
            }}>
              <Sparkles size={18} color="#FFFFFF" />
            </div>
            <div>
              <h3 style={{
                fontSize: '1.05rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-heading)',
              }}>
                Planning AI
              </h3>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Ask for insights, recommendations, or scenario analysis.
              </p>
            </div>
          </div>

          <button
            onClick={handleNewConversation}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid #2563EB',
              background: 'transparent',
              color: '#2563EB',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(37,99,235,0.06)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            <Plus size={14} />
            <span>New Conversation</span>
          </button>
        </div>

        {/* Conversation Message List */}
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
          maxHeight: '440px',
          overflowY: 'auto',
          paddingRight: '6px',
          marginBottom: '20px',
        }}>
          {messages.map((msg) => {
            if (msg.sender === 'user') {
              return (
                <div key={msg.id} style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <div style={{ maxWidth: '75%' }}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'flex-end',
                      gap: '8px',
                      marginBottom: '4px',
                      fontSize: '0.65rem',
                      color: 'var(--text-muted)',
                      fontFamily: 'var(--font-mono)',
                    }}>
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>You</span>
                      <span>{msg.time}</span>
                    </div>
                    <div style={{
                      background: 'var(--bg-workspace)',
                      border: '1px solid var(--border-default)',
                      borderRadius: '12px 12px 2px 12px',
                      padding: '12px 16px',
                      fontSize: '0.82rem',
                      color: 'var(--text-primary)',
                      lineHeight: 1.45,
                    }}>
                      {msg.text}
                    </div>
                  </div>
                  <div style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: 'var(--text-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: '16px',
                  }}>
                    <User size={16} color="#FFFFFF" />
                  </div>
                </div>
              )
            }

            return (
              <div key={msg.id} style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
                <div style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #3B82F6, #1D4ED8)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                  marginTop: '4px',
                }}>
                  <Sparkles size={16} color="#FFFFFF" />
                </div>
                <div style={{ flex: 1, maxWidth: '85%' }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '6px',
                    fontSize: '0.65rem',
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    <span style={{ fontWeight: 700, color: '#2563EB' }}>Planning AI</span>
                    <span>{msg.time}</span>
                  </div>

                  <div style={{
                    background: 'var(--bg-workspace)',
                    border: '1px solid var(--border-default)',
                    borderRadius: '2px 12px 12px 12px',
                    padding: '16px',
                    fontSize: '0.82rem',
                    color: 'var(--text-primary)',
                    lineHeight: 1.5,
                  }}>
                    <p style={{ marginBottom: msg.insights ? '12px' : '0' }}>{msg.text}</p>

                    {msg.insights && (
                      <div style={{ marginBottom: '14px' }}>
                        <div style={{
                          fontWeight: 700,
                          fontSize: '0.8rem',
                          color: 'var(--text-primary)',
                          marginBottom: '6px',
                        }}>
                          Key Insights
                        </div>
                        <ul style={{
                          margin: 0,
                          paddingLeft: '18px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                          fontSize: '0.78rem',
                          color: 'var(--text-secondary)',
                        }}>
                          {msg.insights.map((insight, idx) => (
                            <li key={idx} style={{ lineHeight: 1.4 }}>
                              {insight}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Suggestion Chips & Action Buttons */}
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '12px',
                      flexWrap: 'wrap',
                      marginTop: '12px',
                      paddingTop: '10px',
                      borderTop: '1px solid var(--border-divider)',
                    }}>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        {msg.suggestions?.map((sug, i) => (
                          <button
                            key={i}
                            onClick={() => handleSendMessage(sug)}
                            style={{
                              padding: '5px 12px',
                              borderRadius: 'var(--radius-full)',
                              background: 'var(--bg-card)',
                              border: '1px solid var(--border-default)',
                              fontSize: '0.7rem',
                              color: 'var(--text-secondary)',
                              cursor: 'pointer',
                              transition: 'all var(--transition-fast)',
                            }}
                            onMouseEnter={e => {
                              e.currentTarget.style.borderColor = '#2563EB'
                              e.currentTarget.style.color = '#2563EB'
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.borderColor = 'var(--border-default)'
                              e.currentTarget.style.color = 'var(--text-secondary)'
                            }}
                          >
                            {sug}
                          </button>
                        ))}
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
                        <button
                          style={{
                            background: 'none', border: 'none', color: 'var(--text-muted)',
                            cursor: 'pointer', padding: '4px', display: 'flex',
                          }}
                          title="Helpful response"
                        >
                          <ThumbsUp size={14} />
                        </button>
                        <button
                          style={{
                            background: 'none', border: 'none', color: 'var(--text-muted)',
                            cursor: 'pointer', padding: '4px', display: 'flex',
                          }}
                          title="Unhelpful response"
                        >
                          <ThumbsDown size={14} />
                        </button>
                        <button
                          onClick={() => handleCopy(`${msg.text}\n${msg.insights?.join('\n') || ''}`, msg.id)}
                          style={{
                            background: 'none', border: 'none', color: copiedId === msg.id ? '#2F8F72' : 'var(--text-muted)',
                            cursor: 'pointer', padding: '4px', display: 'flex',
                          }}
                          title="Copy response"
                        >
                          {copiedId === msg.id ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}

          {isThinking && (
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                background: 'linear-gradient(135deg, #3B82F6, #1D4ED8)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <Sparkles size={16} color="#FFFFFF" />
              </div>
              <div style={{
                padding: '12px 18px',
                background: 'var(--bg-workspace)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontFamily: 'var(--font-mono)',
              }}>
                <RefreshCw size={13} className="animate-spin" />
                Planning AI is synthesizing multi-domain telemetry & running neural simulations...
              </div>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-md)',
          padding: '8px 12px',
          boxShadow: 'var(--shadow-card)',
        }}>
          <button
            style={{
              background: 'none', border: 'none', color: 'var(--text-muted)',
              cursor: 'pointer', padding: '4px', display: 'flex',
            }}
          >
            <Paperclip size={16} />
          </button>
          <input
            type="text"
            value={inputQuery}
            onChange={e => setInputQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask a question or request analysis..."
            style={{
              flex: 1,
              border: 'none',
              outline: 'none',
              background: 'transparent',
              fontSize: '0.8rem',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-body)',
            }}
          />
          <button
            onClick={() => handleSendMessage()}
            style={{
              width: 32,
              height: 32,
              borderRadius: 'var(--radius-sm)',
              background: '#2563EB',
              border: 'none',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => e.currentTarget.style.background = '#1D4ED8'}
            onMouseLeave={e => e.currentTarget.style.background = '#2563EB'}
          >
            <Send size={15} />
          </button>
        </div>

        <div style={{
          textAlign: 'center',
          fontSize: '0.62rem',
          color: 'var(--text-muted)',
          marginTop: '10px',
        }}>
          AI responses may contain inaccuracies. Verify critical decisions before implementation.
        </div>
      </div>

      {/* ── Bottom Section: Active Alerts + AI Recommended Solutions ── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '360px 1fr',
        gap: 'var(--space-lg)',
        alignItems: 'start',
      }}>
        {/* Left Column: Active Alerts List */}
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          boxShadow: 'var(--shadow-card)',
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-heading)',
              }}>
                Active Alerts
              </h3>
              <span style={{
                width: 18,
                height: 18,
                borderRadius: '50%',
                background: 'rgba(229,72,63,0.15)',
                color: '#E5483F',
                fontSize: '0.65rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {activeAlerts.length}
              </span>
            </div>
            <span style={{
              fontSize: '0.65rem',
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              cursor: 'pointer',
              fontWeight: 600,
            }}>
              VIEW ALL
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {activeAlerts.map((alert, idx) => {
              const isSelected = idx === selectedAlertIndex
              const DomainIcon = alert.domainIcon
              return (
                <div
                  key={alert.id}
                  onClick={() => setSelectedAlertIndex(idx)}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    padding: '14px',
                    borderRadius: 'var(--radius-md)',
                    background: isSelected ? 'rgba(229,72,63,0.03)' : 'var(--bg-workspace)',
                    border: `1px solid ${isSelected ? 'rgba(229,72,63,0.3)' : 'var(--border-divider)'}`,
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                >
                  <div style={{
                    width: 32,
                    height: 32,
                    borderRadius: 'var(--radius-sm)',
                    background: isSelected ? 'rgba(229,72,63,0.12)' : 'var(--bg-card)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    <DomainIcon size={16} color={alert.impactColor} />
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '2px' }}>
                      <span style={{
                        fontSize: '0.78rem',
                        fontWeight: 700,
                        color: 'var(--text-primary)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                        {alert.title}
                      </span>
                    </div>

                    <div style={{
                      fontSize: '0.68rem',
                      color: 'var(--text-muted)',
                      marginBottom: '8px',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}>
                      {alert.location}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: '0.6rem',
                        fontWeight: 600,
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-default)',
                        color: 'var(--text-secondary)',
                      }}>
                        {alert.domain}
                      </span>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-full)',
                        fontSize: '0.6rem',
                        fontWeight: 600,
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-default)',
                        color: 'var(--text-muted)',
                      }}>
                        {alert.status}
                      </span>
                    </div>
                  </div>

                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{
                      fontSize: '0.62rem',
                      fontWeight: 700,
                      color: alert.impactColor,
                      fontFamily: 'var(--font-mono)',
                    }}>
                      {alert.impact}
                    </div>
                    <div style={{
                      fontSize: '0.58rem',
                      color: 'var(--text-muted)',
                      fontFamily: 'var(--font-mono)',
                      marginTop: '2px',
                    }}>
                      {alert.time}
                    </div>
                    <ChevronRight size={14} color="var(--text-muted)" style={{ marginTop: '8px', marginLeft: 'auto' }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right Column: AI Recommended Solutions */}
        <div style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          {/* Section Header */}
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={16} color="#E5483F" />
              <h3 style={{
                fontSize: '0.85rem',
                fontWeight: 700,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-heading)',
              }}>
                AI Recommended Solutions for {activeAlert.title}
              </h3>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                fontSize: '0.65rem',
                color: 'var(--text-muted)',
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
              }}>
                SOLUTION SET {solutionSetIndex} OF 3
              </span>
              <button
                onClick={() => setSolutionSetIndex(prev => prev > 1 ? prev - 1 : 3)}
                style={{
                  background: 'none', border: 'none', color: 'var(--text-muted)',
                  cursor: 'pointer', padding: '2px', display: 'flex',
                }}
              >
                <ChevronLeft size={14} />
              </button>
              <button
                onClick={() => setSolutionSetIndex(prev => prev < 3 ? prev + 1 : 1)}
                style={{
                  background: 'none', border: 'none', color: 'var(--text-muted)',
                  cursor: 'pointer', padding: '2px', display: 'flex',
                }}
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>

          {/* 4 Solution Cards in a Row */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '12px',
          }}>
            {activeAlert.solutions.map((sol) => (
              <div
                key={sol.id}
                style={{
                  background: 'var(--bg-workspace)',
                  border: '1px solid var(--border-divider)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '14px',
                  transition: 'all var(--transition-fast)',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = 'var(--border-hover)'
                  e.currentTarget.style.transform = 'translateY(-2px)'
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'var(--border-divider)'
                  e.currentTarget.style.transform = 'translateY(0)'
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                    <div style={{
                      width: 20,
                      height: 20,
                      borderRadius: '50%',
                      background: sol.color,
                      color: '#FFFFFF',
                      fontSize: '0.65rem',
                      fontWeight: 700,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                      {sol.id}
                    </div>
                    <span style={{
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      lineHeight: 1.2,
                    }}>
                      {sol.title}
                    </span>
                  </div>

                  <p style={{
                    fontSize: '0.7rem',
                    color: 'var(--text-muted)',
                    lineHeight: 1.35,
                  }}>
                    {sol.desc}
                  </p>
                </div>

                <div>
                  <div style={{ marginBottom: '10px' }}>
                    <div style={{
                      fontSize: '0.58rem',
                      color: 'var(--text-muted)',
                      fontFamily: 'var(--font-mono)',
                      textTransform: 'uppercase',
                    }}>
                      {sol.impactLabel}
                    </div>
                    <div style={{
                      fontSize: '1rem',
                      fontWeight: 700,
                      color: sol.impactColor,
                      fontFamily: 'var(--font-heading)',
                    }}>
                      {sol.impactValue}
                    </div>
                    <div style={{
                      fontSize: '0.62rem',
                      color: 'var(--text-muted)',
                      marginTop: '2px',
                    }}>
                      Confidence <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{sol.confidence}</span>
                    </div>
                  </div>

                  <button
                    onClick={() => setSelectedSolution(sol)}
                    style={{
                      width: '100%',
                      padding: '6px 0',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-default)',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      transition: 'all var(--transition-fast)',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = '#2563EB'
                      e.currentTarget.style.color = '#2563EB'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = 'var(--border-default)'
                      e.currentTarget.style.color = 'var(--text-secondary)'
                    }}
                  >
                    View Details
                  </button>
                </div>
              </div>
            ))}
          </div>

          {/* Bottom Scenario Analysis Banner Button */}
          <button
            onClick={() => setShowScenarioModal(true)}
            style={{
              width: '100%',
              padding: '12px 20px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-workspace)',
              border: '1px solid var(--border-default)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '0.78rem',
              fontWeight: 600,
              color: '#2563EB',
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(37,99,235,0.06)'
              e.currentTarget.style.borderColor = '#2563EB'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'var(--bg-workspace)'
              e.currentTarget.style.borderColor = 'var(--border-default)'
            }}
          >
            <SlidersHorizontal size={15} />
            <span>Run What-If Scenario Analysis</span>
            <ArrowRight size={14} style={{ marginLeft: 'auto' }} />
          </button>
        </div>
      </div>

      {/* ── Solution Details Modal ──────────────────────────── */}
      {selectedSolution && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'var(--bg-overlay)',
          backdropFilter: 'blur(4px)',
          zIndex: 1200,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
        }}>
          <div style={{
            width: '100%',
            maxWidth: '560px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px',
            boxShadow: 'var(--shadow-modal)',
          }} className="animate-fade-in-up">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: 24, height: 24, borderRadius: '50%',
                  background: selectedSolution.color, color: '#FFFFFF',
                  fontSize: '0.75rem', fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  {selectedSolution.id}
                </div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedSolution.title}
                </h3>
              </div>
              <button
                onClick={() => setSelectedSolution(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: 1.45 }}>
              {selectedSolution.desc}
            </p>

            <div style={{
              padding: '14px',
              background: 'var(--bg-workspace)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-divider)',
              marginBottom: '20px',
            }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Operational Implementation Details
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                {selectedSolution.details}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '20px' }}>
              <div style={{ padding: '10px', background: 'var(--bg-workspace)', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>Projected Impact</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: selectedSolution.impactColor }}>
                  {selectedSolution.impactValue}
                </div>
              </div>
              <div style={{ padding: '10px', background: 'var(--bg-workspace)', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>Simulation Confidence</span>
                <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {selectedSolution.confidence}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setSelectedSolution(null)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-default)',
                  background: 'transparent',
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  color: 'var(--text-secondary)',
                }}
              >
                Close
              </button>
              <button
                onClick={() => {
                  alert(`Directive for "${selectedSolution.title}" transmitted to Field Dispatch Unit.`)
                  setSelectedSolution(null)
                }}
                style={{
                  padding: '8px 18px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  background: '#2563EB',
                  color: '#FFFFFF',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Execute Recommendation
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── What-If Scenario Modal ──────────────────────────── */}
      {showScenarioModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'var(--bg-overlay)',
          backdropFilter: 'blur(4px)',
          zIndex: 1200,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
        }}>
          <div style={{
            width: '100%',
            maxWidth: '680px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px',
            boxShadow: 'var(--shadow-modal)',
          }} className="animate-fade-in-up">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <SlidersHorizontal size={20} color="#2563EB" />
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                  What-If Scenario Simulation
                </h3>
              </div>
              <button
                onClick={() => setShowScenarioModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '20px' }}>
              Select hypothetical parameters to model urban stress response for {activeAlert.location}.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '24px' }}>
              {[
                { label: 'Traffic Surge Scenario', opts: ['Baseline (+0%)', '+15% Evening Peak', '+30% Severe Rain Event'] },
                { label: 'Signal Control Strategy', opts: ['Fixed Time (Legacy)', 'Adaptive AI Split (Active)', 'Emergency Green Wave'] },
                { label: 'Public Transit Frequency', opts: ['Standard Headway', 'High Frequency (+25%)', 'Dedicated Bus Lane Priority'] },
              ].map((param, i) => (
                <div key={i} style={{ padding: '12px', background: 'var(--bg-workspace)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                    {param.label}
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {param.opts.map((opt, oi) => (
                      <button
                        key={oi}
                        style={{
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.7rem',
                          fontWeight: oi === 1 ? 600 : 400,
                          background: oi === 1 ? '#2563EB' : 'var(--bg-card)',
                          color: oi === 1 ? '#FFFFFF' : 'var(--text-secondary)',
                          border: oi === 1 ? 'none' : '1px solid var(--border-default)',
                          cursor: 'pointer',
                        }}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowScenarioModal(false)}
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-default)',
                  background: 'transparent',
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  color: 'var(--text-secondary)',
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowScenarioModal(false)
                  handleSendMessage('Run What-If Scenario with +15% evening peak and Adaptive AI Split.')
                }}
                style={{
                  padding: '8px 20px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  background: '#2563EB',
                  color: '#FFFFFF',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Run Multi-Agent Simulation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

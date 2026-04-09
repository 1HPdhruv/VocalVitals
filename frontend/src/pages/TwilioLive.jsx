import { useState, useEffect, useRef, useCallback } from 'react'
import PropTypes from 'prop-types'
import { PhoneIcon, AlertTriangleIcon, ActivityIcon, MicIcon } from '../components/Icons'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = API_URL.replace('http://', 'ws://').replace('https://', 'wss://')

// ============================================================
// COMPONENTS
// ============================================================

function StatusBadge({ status }) {
  const styles = {
    ringing: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    active: 'bg-green-500/20 text-green-400 border-green-500/30 animate-pulse',
    ended: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded border ${styles[status] || styles.ended}`}>
      {status?.toUpperCase() || 'UNKNOWN'}
    </span>
  )
}

StatusBadge.propTypes = { status: PropTypes.string }

function InsightGauge({ label, value, max = 100, color = 'var(--color-primary)' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const getColor = () => {
    if (pct > 70) return 'var(--color-error)'
    if (pct > 40) return 'var(--color-trend-rising)'
    return color
  }
  
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-[var(--color-text-muted)]">{label}</span>
        <span className="font-mono" style={{ color: getColor() }}>{value.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 bg-[var(--color-surface-overlay)] rounded-full overflow-hidden">
        <div 
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: getColor() }}
        />
      </div>
    </div>
  )
}

InsightGauge.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
  max: PropTypes.number,
  color: PropTypes.string,
}

function ActiveCallCard({ call }) {
  return (
    <div className="card p-4 border-green-500/30 bg-green-500/5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
          <span className="font-medium">Live Call</span>
          <StatusBadge status={call.status} />
        </div>
        <span className="text-sm font-mono text-[var(--color-text-muted)]">
          {call.duration_sec?.toFixed(0) || 0}s
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <div className="text-xs text-[var(--color-text-muted)]">From</div>
          <div className="font-mono text-sm">{call.from_number || 'Unknown'}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-muted)]">Call SID</div>
          <div className="font-mono text-xs truncate">{call.call_sid?.slice(-12) || '...'}</div>
        </div>
      </div>
      
      <div className="space-y-2 mb-3">
        <InsightGauge label="Stress Level" value={call.stress_level || 0} />
        <InsightGauge label="Anomaly Score" value={call.anomaly_score || 0} />
        <InsightGauge label="Speech Clarity" value={call.speech_clarity || 100} color="var(--color-primary)" />
      </div>
      
      {call.insights && call.insights.length > 0 && (
        <div className="mt-3 space-y-1">
          {call.insights.map((insight, i) => (
            <div key={i} className="text-xs text-[var(--color-trend-rising)] flex items-center gap-1">
              <AlertTriangleIcon className="w-3 h-3" />
              {insight}
            </div>
          ))}
        </div>
      )}
      
      <div className="mt-3 text-xs text-[var(--color-text-muted)]">
        Chunks processed: {call.chunks_processed || 0}
      </div>
    </div>
  )
}

ActiveCallCard.propTypes = {
  call: PropTypes.shape({
    call_sid: PropTypes.string,
    from_number: PropTypes.string,
    status: PropTypes.string,
    duration_sec: PropTypes.number,
    stress_level: PropTypes.number,
    anomaly_score: PropTypes.number,
    speech_clarity: PropTypes.number,
    voice_energy: PropTypes.number,
    chunks_processed: PropTypes.number,
    insights: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
}

function CompletedCallCard({ call }) {
  const startTime = call.started_at ? new Date(call.started_at).toLocaleTimeString() : ''
  
  return (
    <div className="card p-4 hover:border-[var(--color-primary)]/20 transition-all">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm">{call.from_number || 'Unknown'}</span>
            <StatusBadge status={call.status} />
          </div>
          <div className="text-xs text-[var(--color-text-muted)]">
            {startTime} · {call.duration_sec?.toFixed(0) || 0}s · {call.chunks_processed || 0} chunks
          </div>
        </div>
        <div className="text-right">
          <div className="text-lg font-mono" style={{
            color: call.stress_level > 60 ? 'var(--color-error)' : 
                   call.stress_level > 30 ? 'var(--color-trend-rising)' : 
                   'var(--color-primary)'
          }}>
            {(call.stress_level || 0).toFixed(0)}%
          </div>
          <div className="text-xs text-[var(--color-text-muted)]">Stress</div>
        </div>
      </div>
      
      {call.insights && call.insights.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {call.insights.map((insight, i) => (
            <span key={i} className="text-xs bg-[var(--color-trend-rising)]/10 text-[var(--color-trend-rising)] px-2 py-0.5 rounded">
              {insight}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

CompletedCallCard.propTypes = {
  call: PropTypes.shape({
    call_sid: PropTypes.string,
    from_number: PropTypes.string,
    status: PropTypes.string,
    started_at: PropTypes.string,
    duration_sec: PropTypes.number,
    stress_level: PropTypes.number,
    chunks_processed: PropTypes.number,
    insights: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
}

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function TwilioLiveDashboard() {
  const [connected, setConnected] = useState(false)
  const [activeCalls, setActiveCalls] = useState([])
  const [history, setHistory] = useState([])
  const [error, setError] = useState(null)
  
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    
    setError(null)
    
    try {
      const ws = new WebSocket(`${WS_URL}/twilio/ws/dashboard`)
      wsRef.current = ws
      
      ws.onopen = () => {
        setConnected(true)
        setError(null)
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          switch (data.type) {
            case 'init':
              setActiveCalls(data.active_calls || [])
              setHistory(data.history || [])
              break
              
            case 'call_started':
              setActiveCalls(prev => {
                const exists = prev.some(c => c.call_sid === data.call.call_sid)
                if (exists) return prev
                return [data.call, ...prev]
              })
              break
              
            case 'call_active':
              setActiveCalls(prev => prev.map(c => 
                c.call_sid === data.call_sid ? { ...c, status: 'active' } : c
              ))
              break
              
            case 'analysis_update':
              if (data.call) {
                setActiveCalls(prev => prev.map(c => 
                  c.call_sid === data.call_sid ? data.call : c
                ))
              }
              break
              
            case 'call_ended':
              setActiveCalls(prev => prev.filter(c => c.call_sid !== data.call.call_sid))
              setHistory(prev => [data.call, ...prev].slice(0, 50))
              break
          }
        } catch (err) {
          // Ignore parse errors
        }
      }
      
      ws.onclose = () => {
        setConnected(false)
        reconnectTimeoutRef.current = setTimeout(connect, 3000)
      }
      
      ws.onerror = () => {
        setConnected(false)
        setError('Connection error')
      }
      
    } catch (err) {
      setError(err.message)
      reconnectTimeoutRef.current = setTimeout(connect, 5000)
    }
  }, [])

  const simulateCall = async () => {
    try {
      await fetch(`${API_URL}/twilio/test/simulate-call`, { method: 'POST' })
    } catch (err) {
      setError('Failed to simulate call')
    }
  }

  useEffect(() => {
    connect()
    
    // Fetch initial data via REST as fallback
    fetch(`${API_URL}/twilio/calls/active`)
      .then(res => res.json())
      .then(data => {
        if (data.calls) setActiveCalls(data.calls)
      })
      .catch(() => {})
    
    fetch(`${API_URL}/twilio/calls/history`)
      .then(res => res.json())
      .then(data => {
        if (data.calls) setHistory(data.calls)
      })
      .catch(() => {})
    
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [connect])

  return (
    <div className="page-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-4xl mx-auto space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium text-[var(--color-text-primary)] flex items-center gap-2">
              <PhoneIcon className="w-6 h-6" />
              Live Call Dashboard
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              Real-time Twilio voice analysis
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button 
              onClick={simulateCall}
              className="btn-secondary text-xs px-3 py-1.5"
            >
              Simulate Call
            </button>
            <div className={`flex items-center gap-1.5 text-xs ${connected ? 'text-green-400' : 'text-[var(--color-text-muted)]'}`}>
              <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-gray-500'}`} />
              {connected ? 'Live' : 'Offline'}
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="card p-3 border-[var(--color-error)]/30 bg-[var(--color-error)]/5">
            <p className="text-sm text-[var(--color-error)]">{error}</p>
          </div>
        )}

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="card p-4 text-center">
            <div className="text-3xl font-mono text-green-400">{activeCalls.length}</div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">Active Calls</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-3xl font-mono text-[var(--color-text-primary)]">{history.length}</div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">Completed</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-3xl font-mono text-[var(--color-trend-rising)]">
              {history.filter(c => (c.stress_level || 0) > 50).length}
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">High Stress</div>
          </div>
        </div>

        {/* Setup Instructions */}
        <div className="card p-4 border-[var(--color-primary)]/20 bg-[var(--color-primary)]/5">
          <p className="text-sm font-medium text-[var(--color-primary)] flex items-center gap-2 mb-2">
            <MicIcon className="w-4 h-4" />
            Twilio Setup
          </p>
          <div className="text-xs text-[var(--color-text-secondary)] space-y-1">
            <p>1. Run ngrok: <code className="bg-black/20 px-1 rounded">ngrok http 8000</code></p>
            <p>2. Set Twilio webhook to: <code className="bg-black/20 px-1 rounded">https://[ngrok-url]/twilio/incoming</code></p>
            <p>3. Call your number: <code className="bg-black/20 px-1 rounded">+17625722165</code></p>
          </div>
        </div>

        {/* Active Calls */}
        {activeCalls.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-[var(--color-text-primary)] flex items-center gap-2">
              <ActivityIcon className="w-4 h-4 text-green-400" />
              Active Calls ({activeCalls.length})
            </h2>
            {activeCalls.map(call => (
              <ActiveCallCard key={call.call_sid} call={call} />
            ))}
          </div>
        )}

        {/* Call History */}
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-[var(--color-text-primary)]">
            Recent Calls ({history.length})
          </h2>
          
          {history.length === 0 ? (
            <div className="card p-10 text-center">
              <PhoneIcon className="w-10 h-10 mx-auto mb-3 text-[var(--color-text-muted)] opacity-40" />
              <p className="text-[var(--color-text-muted)] text-sm">No calls yet</p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                Call your Twilio number or click Simulate Call to test
              </p>
            </div>
          ) : (
            history.map(call => (
              <CompletedCallCard key={call.call_sid} call={call} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

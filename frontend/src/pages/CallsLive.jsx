import { useState, useEffect, useRef, useCallback } from 'react'
import PropTypes from 'prop-types'
import { PhoneIcon, AlertTriangleIcon, ActivityIcon, MicIcon } from '../components/Icons'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = API_URL.replace('http://', 'ws://').replace('https://', 'wss://')

function SeverityBadge({ severity }) {
  const classes = {
    high: 'trend-badge trend-rising',
    medium: 'trend-badge trend-rising',
    low: 'trend-badge trend-stable',
  }
  return (
    <span className={classes[severity] || 'trend-badge trend-stable'}>
      {(severity || 'unknown').toUpperCase()}
    </span>
  )
}

SeverityBadge.propTypes = {
  severity: PropTypes.string,
}

function RiskGauge({ label, value, color }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between text-xs">
        <span className="text-[var(--color-text-muted)]">{label}</span>
        <span className="font-mono" style={{ color }}>{value.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-[var(--color-surface-overlay)] rounded-full overflow-hidden">
        <div 
          className="h-full transition-all duration-300 ease-out rounded-full"
          style={{ 
            width: `${Math.min(100, Math.max(0, value))}%`,
            backgroundColor: color 
          }}
        />
      </div>
    </div>
  )
}

RiskGauge.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
  color: PropTypes.string.isRequired,
}

function ActiveCallCard({ call }) {
  return (
    <div className="card p-4 border-[var(--color-primary)] bg-[var(--color-primary)]/5 animate-pulse-subtle">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-[var(--color-primary)] animate-pulse" />
          <span className="font-medium text-[var(--color-text-primary)]">Live Call</span>
          <span className="font-mono text-sm text-[var(--color-text-secondary)]">
            {call.caller_number || 'Unknown'}
          </span>
        </div>
        <span className="text-xs font-mono text-[var(--color-text-muted)]">
          {call.total_duration ? `${call.total_duration.toFixed(1)}s` : 'Connecting...'}
        </span>
      </div>
      
      {call.cough_score !== undefined && (
        <div className="space-y-2">
          <RiskGauge 
            label="Cough Detection" 
            value={call.cough_score} 
            color={call.cough_score > 60 ? 'var(--color-error)' : call.cough_score > 30 ? 'var(--color-trend-rising)' : 'var(--color-primary)'}
          />
          <RiskGauge 
            label="Respiratory Risk" 
            value={call.respiratory_risk || 0} 
            color={call.respiratory_risk > 50 ? 'var(--color-error)' : 'var(--color-trend-rising)'}
          />
          <RiskGauge 
            label="Speech Quality" 
            value={call.speech_score || 50} 
            color="var(--color-primary)"
          />
        </div>
      )}
      
      {call.chunk_index !== undefined && (
        <div className="mt-3 text-xs text-[var(--color-text-muted)] font-mono">
          Chunk #{call.chunk_index + 1} analyzed
        </div>
      )}
    </div>
  )
}

ActiveCallCard.propTypes = {
  call: PropTypes.shape({
    call_sid: PropTypes.string,
    caller_number: PropTypes.string,
    total_duration: PropTypes.number,
    cough_score: PropTypes.number,
    respiratory_risk: PropTypes.number,
    speech_score: PropTypes.number,
    chunk_index: PropTypes.number,
  }).isRequired,
}

function CompletedCallCard({ call }) {
  const time = call.timestamp
    ? new Date(call.timestamp).toLocaleString()
    : 'Unknown time'

  return (
    <div className="card p-4 hover:border-[var(--color-primary)]/20 transition-all">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono text-sm text-[var(--color-text-secondary)]">
              {call.caller_number || call.callerNumber || '****'}
            </span>
            <SeverityBadge severity={call.severity} />
            {call.chunks_analyzed && (
              <span className="text-xs text-[var(--color-text-muted)] font-mono">
                {call.chunks_analyzed} chunks
              </span>
            )}
          </div>
          
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <div className="text-lg font-mono" style={{ 
                color: call.final_cough_score > 60 ? 'var(--color-error)' : 
                       call.final_cough_score > 30 ? 'var(--color-trend-rising)' : 
                       'var(--color-primary)' 
              }}>
                {(call.final_cough_score || call.coughScore || 0).toFixed(1)}%
              </div>
              <div className="text-xs text-[var(--color-text-muted)]">Cough</div>
            </div>
            <div>
              <div className="text-lg font-mono text-[var(--color-trend-rising)]">
                {(call.final_respiratory_risk || call.respiratoryRisk || 0).toFixed(1)}%
              </div>
              <div className="text-xs text-[var(--color-text-muted)]">Respiratory</div>
            </div>
            <div>
              <div className="text-lg font-mono text-[var(--color-text-secondary)]">
                {(call.total_duration || call.duration || 0).toFixed(1)}s
              </div>
              <div className="text-xs text-[var(--color-text-muted)]">Duration</div>
            </div>
          </div>
        </div>
        <div className="text-xs text-[var(--color-text-muted)] text-right flex-shrink-0 font-mono">
          {time}
        </div>
      </div>
    </div>
  )
}

CompletedCallCard.propTypes = {
  call: PropTypes.shape({
    timestamp: PropTypes.string,
    caller_number: PropTypes.string,
    callerNumber: PropTypes.string,
    severity: PropTypes.string,
    chunks_analyzed: PropTypes.number,
    final_cough_score: PropTypes.number,
    coughScore: PropTypes.number,
    final_respiratory_risk: PropTypes.number,
    respiratoryRisk: PropTypes.number,
    total_duration: PropTypes.number,
    duration: PropTypes.number,
  }).isRequired,
}

export default function Calls() {
  const [activeCalls, setActiveCalls] = useState({})
  const [completedCalls, setCompletedCalls] = useState([])
  const [connectionStatus, setConnectionStatus] = useState('disconnected')
  const [stats, setStats] = useState({ high: 0, medium: 0, low: 0 })
  
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    
    setConnectionStatus('connecting')
    
    try {
      const ws = new WebSocket(`${WS_URL}/twilio/ws/live`)
      wsRef.current = ws
      
      ws.onopen = () => {
        setConnectionStatus('connected')
      }
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          switch (data.type) {
            case 'init':
              // Initial state from server
              setCompletedCalls(data.recent_results || [])
              if (data.active_calls) {
                const activeMap = {}
                data.active_calls.forEach(sid => {
                  activeMap[sid] = { call_sid: sid }
                })
                setActiveCalls(activeMap)
              }
              break
              
            case 'call_started':
              setActiveCalls(prev => ({
                ...prev,
                [data.call_sid]: {
                  call_sid: data.call_sid,
                  caller_number: data.caller_number,
                  started_at: data.timestamp,
                }
              }))
              break
              
            case 'analysis':
              // Real-time analysis update
              setActiveCalls(prev => ({
                ...prev,
                [data.call_sid]: {
                  ...prev[data.call_sid],
                  ...data,
                }
              }))
              break
              
            case 'call_ended':
              // Move from active to completed
              setActiveCalls(prev => {
                const newActive = { ...prev }
                delete newActive[data.call_sid]
                return newActive
              })
              setCompletedCalls(prev => [data, ...prev].slice(0, 50))
              
              // Update stats
              setStats(prev => ({
                high: prev.high + (data.severity === 'high' ? 1 : 0),
                medium: prev.medium + (data.severity === 'medium' ? 1 : 0),
                low: prev.low + (data.severity === 'low' ? 1 : 0),
              }))
              break
              
            case 'call_disconnected':
              setActiveCalls(prev => {
                const newActive = { ...prev }
                delete newActive[data.call_sid]
                return newActive
              })
              break
          }
        } catch (err) {
          // Ignore parse errors
        }
      }
      
      ws.onclose = () => {
        setConnectionStatus('disconnected')
        // Reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(connectWebSocket, 3000)
      }
      
      ws.onerror = () => {
        setConnectionStatus('error')
      }
      
    } catch (err) {
      setConnectionStatus('error')
      reconnectTimeoutRef.current = setTimeout(connectWebSocket, 5000)
    }
  }, [])

  useEffect(() => {
    connectWebSocket()
    
    // Also fetch initial data from REST API
    fetch(`${API_URL}/twilio/recent-results`)
      .then(res => res.json())
      .then(data => {
        if (data.results) {
          setCompletedCalls(prev => {
            const existing = new Set(prev.map(c => c.call_sid))
            const newCalls = data.results.filter(c => !existing.has(c.call_sid))
            return [...newCalls, ...prev].slice(0, 50)
          })
        }
      })
      .catch(() => {})
    
    fetch(`${API_URL}/twilio/stats`)
      .then(res => res.json())
      .then(data => {
        setStats({
          high: data.high_risk || 0,
          medium: data.medium_risk || 0,
          low: data.low_risk || 0,
        })
      })
      .catch(() => {})
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connectWebSocket])

  const activeCallList = Object.values(activeCalls)
  const isConnected = connectionStatus === 'connected'

  return (
    <div className="page-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-4xl mx-auto space-y-5">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-medium text-[var(--color-text-primary)] flex items-center gap-2">
              <PhoneIcon />
              Live Call Screening
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              Real-time Twilio voice analysis
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-xs ${
              isConnected ? 'text-[var(--color-primary)]' : 
              connectionStatus === 'connecting' ? 'text-[var(--color-trend-rising)]' :
              'text-[var(--color-text-muted)]'
            }`}>
              <span className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-[var(--color-primary)] animate-pulse' :
                connectionStatus === 'connecting' ? 'bg-[var(--color-trend-rising)]' :
                'bg-[var(--color-text-muted)]'
              }`} />
              {isConnected ? 'Live' : connectionStatus === 'connecting' ? 'Connecting...' : 'Offline'}
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          <div className="card p-4 text-center">
            <div className="text-2xl font-medium font-mono text-[var(--color-primary)]">
              {activeCallList.length}
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">Active Calls</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-medium font-mono text-[var(--color-error)]">
              {stats.high}
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">High Risk</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-medium font-mono text-[var(--color-trend-rising)]">
              {stats.medium}
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">Medium Risk</div>
          </div>
          <div className="card p-4 text-center">
            <div className="text-2xl font-medium font-mono text-[var(--color-primary)]">
              {stats.low}
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">Low Risk</div>
          </div>
        </div>

        {/* Connection Status / Setup Info */}
        {!isConnected && (
          <div className="card p-4 border-[var(--color-trend-rising)]/20 bg-[var(--color-trend-rising)]/5">
            <p className="text-sm text-[var(--color-trend-rising)] font-medium mb-1 flex items-center gap-2">
              <AlertTriangleIcon className="icon-sm" />
              {connectionStatus === 'connecting' ? 'Connecting to backend...' : 'Backend Offline'}
            </p>
            <p className="text-xs text-[var(--color-text-secondary)]">
              Make sure the backend is running: <code className="text-[var(--color-primary)] font-mono bg-[var(--color-surface-overlay)] px-1 rounded">uvicorn main:app --reload</code>
            </p>
          </div>
        )}

        {/* Twilio Setup Info */}
        <div className="card p-4 border-[var(--color-primary)]/20 bg-[var(--color-primary)]/5">
          <p className="text-sm text-[var(--color-primary)] font-medium mb-1 flex items-center gap-2">
            <MicIcon className="icon-sm" />
            Twilio Webhook Configuration
          </p>
          <p className="text-xs text-[var(--color-text-secondary)]">
            Point your Twilio number&apos;s Voice webhook to:{' '}
            <code className="text-[var(--color-primary)] font-mono bg-[var(--color-surface-overlay)] px-1 rounded">
              https://[ngrok-url]/twilio/incoming
            </code>
          </p>
        </div>

        {/* Active Calls */}
        {activeCallList.length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-medium text-[var(--color-text-primary)] flex items-center gap-2">
              <ActivityIcon className="icon-sm text-[var(--color-primary)]" />
              Active Calls ({activeCallList.length})
            </h2>
            {activeCallList.map(call => (
              <ActiveCallCard key={call.call_sid} call={call} />
            ))}
          </div>
        )}

        {/* Completed Calls */}
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-[var(--color-text-primary)]">
            Recent Calls ({completedCalls.length})
          </h2>
          
          {completedCalls.length === 0 ? (
            <div className="card p-10 text-center">
              <PhoneIcon className="w-10 h-10 mx-auto mb-3 text-[var(--color-text-muted)] opacity-40" />
              <p className="text-[var(--color-text-muted)] text-sm">No calls received yet.</p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                Call your Twilio number to start voice screening. Results appear here in real-time.
              </p>
            </div>
          ) : (
            completedCalls.map((call, idx) => (
              <CompletedCallCard key={call.call_sid || idx} call={call} />
            ))
          )}
        </div>
      </div>
    </div>
  )
}

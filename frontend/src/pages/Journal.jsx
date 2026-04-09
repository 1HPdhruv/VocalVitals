import { useState, useEffect, useCallback } from 'react'
import PropTypes from 'prop-types'
import { useAuth } from '../contexts/AuthContext'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'
import { useAudioRecorder } from '../hooks/useAudioRecorder'
import WaveformVisualizer from '../components/WaveformVisualizer'
import { showToast } from '../components/Toast'
import { ChartIcon, CalendarIcon, MicrophoneIcon, StopCircleIcon } from '../components/Icons'

// Metric definitions with muted colors
const METRICS = [
  { key: 'pitch_mean', label: 'Pitch Mean', unit: 'Hz', color: '#00C9A7' },
  { key: 'shimmer',    label: 'Shimmer',    unit: '%',  color: '#38BDF8' },
  { key: 'jitter',     label: 'Jitter',     unit: '%',  color: '#F59E0B' },
  { key: 'hnr',        label: 'HNR',        unit: 'dB', color: '#A78BFA' },
]

// Calculate trend from last 7 entries
function calculateTrend(entries, key) {
  if (!entries || entries.length < 2) return { slope: 0, direction: 'stable' }
  
  const recent = entries.slice(-7)
  const values = recent
    .map(e => e.acousticFeatures?.[key] ?? e[key])
    .filter(v => v != null && !isNaN(v))
  
  if (values.length < 2) return { slope: 0, direction: 'stable' }
  
  const n = values.length
  const xMean = (n - 1) / 2
  const yMean = values.reduce((a, b) => a + b, 0) / n
  
  let num = 0, den = 0
  values.forEach((y, i) => {
    num += (i - xMean) * (y - yMean)
    den += (i - xMean) ** 2
  })
  
  const slope = den === 0 ? 0 : num / den
  const threshold = 0.1
  
  let direction = 'stable'
  if (slope > threshold) direction = 'rising'
  else if (slope < -threshold) direction = 'falling'
  
  return { slope, direction }
}

// Trend badge component
function TrendBadge({ direction }) {
  const config = {
    rising:  { label: 'Rising',  className: 'trend-badge trend-rising',  symbol: '↑' },
    falling: { label: 'Falling', className: 'trend-badge trend-falling', symbol: '↓' },
    stable:  { label: 'Stable',  className: 'trend-badge trend-stable',  symbol: '–' },
  }
  
  const { label, className, symbol } = config[direction] || config.stable
  
  return (
    <span className={className}>
      {symbol} {label}
    </span>
  )
}

TrendBadge.propTypes = {
  direction: PropTypes.oneOf(['rising', 'falling', 'stable']).isRequired,
}

// Chart tooltip
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  
  return (
    <div className="chart-tooltip">
      <p className="text-[var(--color-text-muted)] mb-1 text-xs">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="font-mono text-sm" style={{ color: p.color }}>
          {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
        </p>
      ))}
    </div>
  )
}

ChartTooltip.propTypes = {
  active: PropTypes.bool,
  payload: PropTypes.array,
  label: PropTypes.string,
}

// Skeleton loader for charts
function ChartSkeleton() {
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="skeleton h-4 w-24" />
        <div className="skeleton h-5 w-16" />
      </div>
      <div className="skeleton h-32 w-full" />
    </div>
  )
}

// Empty state when no data
function EmptyState({ message }) {
  return (
    <div className="empty-state">
      <ChartIcon className="empty-state-icon" />
      <p className="text-sm">{message}</p>
    </div>
  )
}

EmptyState.propTypes = {
  message: PropTypes.string.isRequired,
}

// Weekly summary stats
function computeWeeklyStats(entries, key) {
  const values = entries
    .slice(-7)
    .map(e => e.acousticFeatures?.[key] ?? e[key])
    .filter(v => v != null && !isNaN(v))
  
  if (values.length === 0) return null
  
  return {
    min: Math.min(...values),
    max: Math.max(...values),
    mean: values.reduce((a, b) => a + b, 0) / values.length,
    trend: calculateTrend(entries, key).direction,
  }
}

export default function Journal() {
  const { user } = useAuth()
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [checkinPhase, setCheckinPhase] = useState('idle')
  const [weeklySummary, setWeeklySummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(false)

  const {
    isRecording, duration, analyserNode,
    startRecording, stopRecording, error: recError,
  } = useAudioRecorder({ userId: user?.uid })

  // Load entries from backend
  const loadEntries = useCallback(async () => {
    if (!user) {
      setLoading(false)
      return
    }
    
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`/journal?userId=${user.uid}&limit=60`)
      
      if (!response.ok) {
        throw new Error('Failed to load journal data')
      }
      
      const apiData = await response.json()
      
      const processed = apiData.map(entry => ({
        ...entry,
        acousticFeatures: {
          pitch_mean: entry.pitch_mean,
          pitch_std: entry.pitch_std,
          jitter: entry.jitter,
          shimmer: entry.shimmer,
          hnr: entry.hnr,
          energy_mean: entry.energy_mean,
          zcr_mean: entry.zcr_mean,
          duration: entry.duration,
        },
        dateLabel: new Date(entry.timestamp || Date.now()).toLocaleDateString('en-US', { 
          month: 'short', 
          day: 'numeric' 
        }),
      }))
      
      setEntries(processed)
    } catch (err) {
      setError(err.message)
      
      // Fallback to localStorage
      try {
        const saved = JSON.parse(localStorage.getItem('vocal_vitals_journal') || '[]')
        const filtered = saved
          .filter(entry => entry.userId === user.uid || !entry.userId)
          .map(entry => ({
            ...entry,
            acousticFeatures: entry.features || entry.acousticFeatures || {},
            dateLabel: new Date(entry.timestamp || Date.now()).toLocaleDateString('en-US', { 
              month: 'short', 
              day: 'numeric' 
            }),
          }))
          .reverse()
        
        setEntries(filtered)
      } catch {
        setEntries([])
      }
    } finally {
      setLoading(false)
    }
  }, [user])

  useEffect(() => { 
    loadEntries() 
  }, [loadEntries])

  // Handle stop recording and analyze
  const handleStopCheckin = useCallback(async () => {
    const blob = await stopRecording()
    
    if (!blob || !blob.size) {
      setCheckinPhase('idle')
      return
    }

    setCheckinPhase('uploading')
    
    try {
      const requestTs = Date.now()
      const formData = new FormData()
      formData.append('file', new File([blob], 'journal.webm', { type: blob.type || 'audio/webm' }))
      formData.append('userId', user.uid)
      formData.append('requestTs', String(requestTs))

      setCheckinPhase('processing')
      
      const resp = await fetch(`/analyze?ts=${requestTs}`, {
        method: 'POST',
        body: formData,
        cache: 'no-store',
      })
      
      if (!resp.ok) {
        throw new Error(await resp.text())
      }
      
      const data = await resp.json()

      // Save to localStorage as backup
      try {
        const existing = JSON.parse(localStorage.getItem('vocal_vitals_journal') || '[]')
        const newEntry = {
          id: `${Date.now()}`,
          timestamp: new Date().toISOString(),
          userId: user.uid,
          acousticFeatures: data.features || {},
          transcript: data.transcript || '',
          analysis: data,
        }
        localStorage.setItem('vocal_vitals_journal', JSON.stringify([newEntry, ...existing].slice(0, 60)))
      } catch {
        // Ignore localStorage errors
      }

      setCheckinPhase('idle')
      showToast('Check-in saved successfully', 'success')
      await loadEntries()
      
    } catch (err) {
      setCheckinPhase('idle')
      showToast('Analysis failed: ' + err.message, 'error')
    }
  }, [stopRecording, user, loadEntries])

  // Generate weekly summary
  const generateWeeklySummary = async () => {
    if (entries.length < 3) {
      showToast('Need at least 3 check-ins for summary', 'error')
      return
    }
    
    setSummaryLoading(true)
    
    try {
      const stats = {}
      METRICS.forEach(({ key }) => {
        stats[key] = computeWeeklyStats(entries, key)
      })
      
      setWeeklySummary(stats)
      
      // Also try to get AI summary from backend
      const last7 = entries.slice(-7).map(e => ({
        date: e.dateLabel,
        ...e.acousticFeatures,
        transcript: e.transcript,
      }))
      
      const resp = await fetch('/journal/weekly-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: user.uid, entries: last7 }),
      })
      
      if (resp.ok) {
        const data = await resp.json()
        if (data.summary) {
          setWeeklySummary(prev => ({ ...prev, aiSummary: data.summary }))
        }
      }
    } catch {
      // Stats are already computed, ignore AI errors
    } finally {
      setSummaryLoading(false)
    }
  }

  // Prepare chart data
  const chartData = entries.map(e => ({
    date: e.dateLabel,
    pitch_mean: e.acousticFeatures?.pitch_mean,
    shimmer: e.acousticFeatures?.shimmer,
    jitter: e.acousticFeatures?.jitter,
    hnr: e.acousticFeatures?.hnr,
  }))

  return (
    <div className="page-bg min-h-screen pt-16 pb-12 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between py-6">
          <div>
            <h1 className="text-xl font-medium text-[var(--color-text-primary)]">Voice Journal</h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              Track your voice health over time
            </p>
          </div>
          <button
            onClick={generateWeeklySummary}
            disabled={entries.length < 3 || summaryLoading}
            className="btn btn-secondary"
          >
            {summaryLoading ? (
              <span className="loading-dots">
                <span className="loading-dot" />
                <span className="loading-dot" />
                <span className="loading-dot" />
              </span>
            ) : (
              <>
                <CalendarIcon />
                <span>Weekly Summary</span>
              </>
            )}
          </button>
        </div>

        {/* Main layout: 1fr 2fr grid */}
        <div className="journal-layout">
          {/* Left panel - Check-in */}
          <div className="space-y-4">
            {/* Check-in card */}
            <div className="card p-5">
              <h2 className="text-sm font-medium text-[var(--color-text-primary)] mb-4">
                Daily Check-in
              </h2>
              
              <WaveformVisualizer 
                analyserNode={analyserNode} 
                isRecording={isRecording} 
                height={80} 
              />

              {/* Duration display */}
              {(isRecording || duration > 0) && (
                <div className="flex items-center gap-2 mt-3">
                  {isRecording && (
                    <span className="recording-indicator recording-indicator-pulse" />
                  )}
                  <span className="font-mono text-sm text-[var(--color-text-secondary)]">
                    {Math.floor(duration / 60).toString().padStart(2, '0')}:
                    {(duration % 60).toString().padStart(2, '0')}
                  </span>
                  {duration >= 30 && (
                    <span className="badge badge-success">Good length</span>
                  )}
                </div>
              )}

              {/* Action buttons */}
              <div className="mt-4">
                {checkinPhase === 'idle' && !isRecording && (
                  <button
                    onClick={startRecording}
                    className="btn btn-primary w-full py-3"
                  >
                    <MicrophoneIcon />
                    <span>Start 30-sec Check-in</span>
                  </button>
                )}
                
                {isRecording && (
                  <button
                    onClick={handleStopCheckin}
                    className="btn btn-danger w-full py-3"
                  >
                    <StopCircleIcon />
                    <span>Stop and Save</span>
                  </button>
                )}
                
                {(checkinPhase === 'uploading' || checkinPhase === 'processing') && (
                  <div className="flex items-center justify-center gap-2 py-3 text-[var(--color-text-muted)]">
                    <span className="loading-dots">
                      <span className="loading-dot" />
                      <span className="loading-dot" />
                      <span className="loading-dot" />
                    </span>
                    <span className="text-sm">
                      {checkinPhase === 'uploading' ? 'Uploading...' : 'Analyzing...'}
                    </span>
                  </div>
                )}
              </div>
              
              {recError && (
                <p className="text-sm text-[var(--color-error)] mt-2">{recError}</p>
              )}
            </div>

            {/* Weekly Summary Card */}
            {weeklySummary && (
              <div className="card p-4">
                <h3 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wide mb-3">
                  7-Day Summary
                </h3>
                
                <div className="space-y-3">
                  {METRICS.map(({ key, label, unit }) => {
                    const stats = weeklySummary[key]
                    if (!stats) return null
                    
                    return (
                      <div key={key} className="flex items-center justify-between text-sm">
                        <span className="text-[var(--color-text-secondary)]">{label}</span>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[var(--color-text-primary)]">
                            {stats.mean.toFixed(1)} {unit}
                          </span>
                          <TrendBadge direction={stats.trend} />
                        </div>
                      </div>
                    )
                  })}
                </div>
                
                {weeklySummary.aiSummary?.summary && (
                  <p className="mt-4 pt-3 border-t border-[var(--color-border)] text-sm text-[var(--color-text-secondary)]">
                    {weeklySummary.aiSummary.summary}
                  </p>
                )}
              </div>
            )}

            {/* Trends summary */}
            {entries.length > 1 && !weeklySummary && (
              <div className="card p-4">
                <h3 className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wide mb-3">
                  7-Day Trends
                </h3>
                <div className="space-y-2">
                  {METRICS.map(({ key, label }) => {
                    const { direction } = calculateTrend(entries, key)
                    return (
                      <div key={key} className="flex items-center justify-between text-sm">
                        <span className="text-[var(--color-text-secondary)]">{label}</span>
                        <TrendBadge direction={direction} />
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Right panel - Charts */}
          <div>
            {loading ? (
              <div className="chart-grid">
                <ChartSkeleton />
                <ChartSkeleton />
                <ChartSkeleton />
                <ChartSkeleton />
              </div>
            ) : error && entries.length === 0 ? (
              <div className="card">
                <EmptyState message={`Error loading data: ${error}`} />
              </div>
            ) : entries.length < 2 ? (
              <div className="card">
                <EmptyState message="Complete more check-ins to see trends" />
              </div>
            ) : (
              <div className="chart-grid">
                {METRICS.map(({ key, label, unit, color }) => {
                  const { direction } = calculateTrend(entries, key)
                  const baseline = entries[0]?.acousticFeatures?.[key]
                  
                  return (
                    <div key={key} className="card p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-medium text-[var(--color-text-primary)]">
                          {label} <span className="text-[var(--color-text-muted)]">({unit})</span>
                        </h3>
                        <TrendBadge direction={direction} />
                      </div>
                      
                      <ResponsiveContainer width="100%" height={120}>
                        <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                          <CartesianGrid 
                            strokeDasharray="3 3" 
                            stroke="rgba(255,255,255,0.06)" 
                            vertical={false}
                          />
                          <XAxis 
                            dataKey="date" 
                            tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
                            tickLine={false}
                            axisLine={{ stroke: 'rgba(255,255,255,0.06)' }}
                          />
                          <YAxis 
                            tick={{ fill: 'var(--color-text-muted)', fontSize: 10 }}
                            tickLine={false}
                            axisLine={false}
                          />
                          <Tooltip content={<ChartTooltip />} />
                          {baseline && (
                            <ReferenceLine
                              y={baseline}
                              stroke="rgba(255,255,255,0.15)"
                              strokeDasharray="4 4"
                            />
                          )}
                          <Line
                            type="monotone"
                            dataKey={key}
                            stroke={color}
                            strokeWidth={1.5}
                            dot={{ fill: color, r: 3, strokeWidth: 0 }}
                            activeDot={{ r: 4, fill: color, strokeWidth: 0 }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect, useCallback } from 'react'
import PropTypes from 'prop-types'
import { useAuth } from '../contexts/AuthContext'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { showToast } from '../components/Toast'
import { 
  ActivityIcon, 
  AlertCircleIcon, 
  ChartIcon, 
  CalendarIcon,
  CheckIcon,
  FileTextIcon 
} from '../components/Icons'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Disease icon components
function BrainIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/>
      <path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/>
      <path d="M12 5v14"/>
    </svg>
  )
}

function HeartIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
    </svg>
  )
}

function LungsIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6.081 20C4.978 20 4 19.054 4 18V12a8 8 0 0 1 8-8"/>
      <path d="M17.919 20C19.022 20 20 19.054 20 18V12a8 8 0 0 0-8-8"/>
      <path d="M12 4v8"/>
      <path d="M4 12c0 1.5.5 3 2 4s3 1.5 4 1.5"/>
      <path d="M20 12c0 1.5-.5 3-2 4s-3 1.5-4 1.5"/>
    </svg>
  )
}

BrainIcon.propTypes = { size: PropTypes.number }
HeartIcon.propTypes = { size: PropTypes.number }
LungsIcon.propTypes = { size: PropTypes.number }

// Get icon component based on disease type
function DiseaseIcon({ icon, size = 16 }) {
  switch (icon) {
    case 'brain': return <BrainIcon size={size} />
    case 'heart': return <HeartIcon size={size} />
    case 'lungs': return <LungsIcon size={size} />
    default: return <ActivityIcon size={size} />
  }
}

DiseaseIcon.propTypes = {
  icon: PropTypes.string,
  size: PropTypes.number,
}

// Risk level color helper
function getRiskColor(score) {
  if (score < 20) return 'var(--color-text-muted)'
  if (score < 50) return 'var(--color-trend-rising)'
  return 'var(--color-error)'
}

function getRiskLevel(score) {
  if (score < 20) return 'low'
  if (score < 50) return 'moderate'
  return 'elevated'
}

// Sparkline chart for disease trends
function Sparkline({ data, color }) {
  if (!data || data.length < 2) return null
  
  return (
    <div className="h-8 w-24">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line 
            type="monotone" 
            dataKey="score" 
            stroke={color} 
            strokeWidth={1.5}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

Sparkline.propTypes = {
  data: PropTypes.array,
  color: PropTypes.string,
}

// Disease risk card component
function DiseaseCard({ disease, trends }) {
  const { name, icon, score, ci_low, ci_high, top_features, explanation } = disease
  const color = getRiskColor(score)
  const level = getRiskLevel(score)
  
  // Handle top_features as either array of strings or objects
  const featuresList = top_features?.map(f => 
    typeof f === 'string' ? f : f.explanation || f.name || String(f)
  ) || []
  
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span style={{ color }}>
            <DiseaseIcon icon={icon} size={18} />
          </span>
          <span className="font-medium text-[var(--color-text-primary)]">{name}</span>
        </div>
        <Sparkline data={trends} color={color} />
      </div>
      
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-2xl font-mono font-medium" style={{ color }}>
          {score.toFixed(0)}%
        </span>
        <span className="text-xs text-[var(--color-text-muted)]">
          CI: {ci_low.toFixed(0)}–{ci_high.toFixed(0)}%
        </span>
      </div>
      
      <div className={`inline-block px-2 py-0.5 text-xs rounded mb-3 ${
        level === 'low' ? 'bg-[var(--color-surface-overlay)] text-[var(--color-text-muted)]' :
        level === 'moderate' ? 'bg-[var(--color-trend-rising)]/10 text-[var(--color-trend-rising)]' :
        'bg-[var(--color-error)]/10 text-[var(--color-error)]'
      }`}>
        {level === 'low' ? 'Low Risk' : level === 'moderate' ? 'Moderate' : 'Elevated'}
      </div>
      
      {featuresList.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-[var(--color-text-muted)] mb-1">Key indicators:</div>
          <div className="flex flex-wrap gap-1">
            {featuresList.map((feat, i) => (
              <span key={i} className="text-xs px-1.5 py-0.5 bg-[var(--color-surface-overlay)] rounded">
                {feat}
              </span>
            ))}
          </div>
        </div>
      )}
      
      {explanation && (
        <p className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
          {explanation}
        </p>
      )}
    </div>
  )
}

DiseaseCard.propTypes = {
  disease: PropTypes.shape({
    name: PropTypes.string.isRequired,
    icon: PropTypes.string,
    score: PropTypes.number.isRequired,
    ci_low: PropTypes.number.isRequired,
    ci_high: PropTypes.number.isRequired,
    top_features: PropTypes.array,
    explanation: PropTypes.string,
  }).isRequired,
  trends: PropTypes.array,
}

// Weekly stats table row
function StatRow({ stat }) {
  const { label, baseline, current, change_pct, trend } = stat
  
  const trendColor = trend === 'rising' ? 'var(--color-trend-rising)' : 
                     trend === 'falling' ? 'var(--color-trend-falling)' : 
                     'var(--color-text-muted)'
  const trendSymbol = trend === 'rising' ? '↑' : trend === 'falling' ? '↓' : '–'
  
  return (
    <tr className="border-b border-[var(--color-border)]">
      <td className="py-2 text-sm text-[var(--color-text-secondary)]">{label}</td>
      <td className="py-2 text-sm font-mono text-[var(--color-text-muted)]">{baseline}</td>
      <td className="py-2 text-sm font-mono text-[var(--color-text-primary)]">{current}</td>
      <td className="py-2 text-sm font-mono" style={{ color: trendColor }}>
        {change_pct > 0 ? '+' : ''}{change_pct}%
      </td>
      <td className="py-2 text-sm" style={{ color: trendColor }}>
        <span className="inline-flex items-center gap-1">
          {trendSymbol} {trend}
        </span>
      </td>
    </tr>
  )
}

StatRow.propTypes = {
  stat: PropTypes.shape({
    label: PropTypes.string.isRequired,
    baseline: PropTypes.number.isRequired,
    current: PropTypes.number.isRequired,
    change_pct: PropTypes.number.isRequired,
    trend: PropTypes.string.isRequired,
  }).isRequired,
}

// Loading skeleton
function InsightsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="card p-4">
            <div className="skeleton h-5 w-24 mb-3" />
            <div className="skeleton h-8 w-16 mb-2" />
            <div className="skeleton h-4 w-full" />
          </div>
        ))}
      </div>
      <div className="card p-4">
        <div className="skeleton h-5 w-32 mb-4" />
        <div className="skeleton h-32 w-full" />
      </div>
    </div>
  )
}

// Insufficient data state
function InsufficientData({ count }) {
  return (
    <div className="card p-8 text-center">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-[var(--color-surface-overlay)] flex items-center justify-center">
        <CalendarIcon size={24} />
      </div>
      <h3 className="text-lg font-medium mb-2">More Check-ins Needed</h3>
      <p className="text-[var(--color-text-secondary)] mb-4">
        You have {count} check-in{count !== 1 ? 's' : ''}. Complete at least 7 daily check-ins 
        for reliable disease risk assessment.
      </p>
      <div className="flex items-center justify-center gap-2 text-sm text-[var(--color-text-muted)]">
        <div className="w-full max-w-xs bg-[var(--color-surface-overlay)] rounded-full h-2">
          <div 
            className="bg-[var(--color-primary)] h-2 rounded-full transition-all"
            style={{ width: `${Math.min(100, (count / 7) * 100)}%` }}
          />
        </div>
        <span>{count}/7</span>
      </div>
    </div>
  )
}

InsufficientData.propTypes = {
  count: PropTypes.number.isRequired,
}

export default function Insights() {
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [insights, setInsights] = useState(null)
  const [history, setHistory] = useState(null)
  const [weeklyStats, setWeeklyStats] = useState(null)
  const [report, setReport] = useState(null)
  const [generatingReport, setGeneratingReport] = useState(false)
  
  const userId = user?.uid || 'anonymous'
  
  const loadInsights = useCallback(async () => {
    setLoading(true)
    try {
      // Use demo=true to always get sample data for demonstration
      const [insightsRes, historyRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/insights?userId=${userId}&demo=true`),
        fetch(`${API_BASE}/insights/history?userId=${userId}&days=30`),
        fetch(`${API_BASE}/insights/weekly-stats?userId=${userId}`),
      ])
      
      if (insightsRes.ok) {
        const data = await insightsRes.json()
        setInsights(data)
      }
      
      if (historyRes.ok) {
        const data = await historyRes.json()
        setHistory(data.trends || {})
      }
      
      if (statsRes.ok) {
        const data = await statsRes.json()
        setWeeklyStats(data.stats || {})
      }
    } catch (err) {
      showToast('Failed to load insights', 'error')
    } finally {
      setLoading(false)
    }
  }, [userId])
  
  useEffect(() => {
    loadInsights()
  }, [loadInsights])
  
  const generateWeeklyReport = async () => {
    setGeneratingReport(true)
    try {
      const res = await fetch(`${API_BASE}/insights/weekly-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId }),
      })
      
      if (res.ok) {
        const data = await res.json()
        setReport(data)
        showToast('Weekly report generated', 'success')
      } else {
        const err = await res.json()
        showToast(err.message || 'Failed to generate report', 'error')
      }
    } catch {
      showToast('Failed to generate report', 'error')
    } finally {
      setGeneratingReport(false)
    }
  }
  
  if (loading) {
    return (
      <div className="page-bg min-h-screen p-6">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl font-medium mb-6">Health Insights</h1>
          <InsightsSkeleton />
        </div>
      </div>
    )
  }
  
  if (!insights || insights.status === 'no_data') {
    return (
      <div className="page-bg min-h-screen p-6">
        <div className="max-w-6xl mx-auto">
          <h1 className="text-2xl font-medium mb-6">Health Insights</h1>
          <InsufficientData count={0} />
        </div>
      </div>
    )
  }
  
  const showBlur = insights.checkins_used < 7
  
  return (
    <div className="page-bg min-h-screen p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-medium">Health Insights</h1>
            <p className="text-sm text-[var(--color-text-muted)]">
              Based on {insights.checkins_used} check-in{insights.checkins_used !== 1 ? 's' : ''} 
              {!insights.is_reliable && ' (7+ recommended for reliable results)'}
            </p>
          </div>
          <button
            onClick={generateWeeklyReport}
            disabled={generatingReport || insights.checkins_used < 3}
            className="btn btn-secondary flex items-center gap-2"
          >
            <FileTextIcon size={16} />
            {generatingReport ? 'Generating...' : 'Weekly Report'}
          </button>
        </div>
        
        {/* Reliability warning */}
        {!insights.is_reliable && (
          <div className="card p-4 mb-6 border-[var(--color-trend-rising)] bg-[var(--color-trend-rising)]/5">
            <div className="flex items-start gap-3">
              <AlertCircleIcon size={18} className="text-[var(--color-trend-rising)] flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-[var(--color-trend-rising)]">Limited Data</p>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  Complete 7+ daily check-ins for reliable disease risk assessment. Current scores have wider confidence intervals.
                </p>
              </div>
            </div>
          </div>
        )}
        
        {/* Flagged concerns */}
        {insights.flagged && insights.flagged.length > 0 && (
          <div className="card p-4 mb-6 border-[var(--color-error)] bg-[var(--color-error)]/5">
            <div className="flex items-start gap-3">
              <AlertCircleIcon size={18} className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-[var(--color-error)]">
                  {insights.flagged.length} Area{insights.flagged.length !== 1 ? 's' : ''} Require Attention
                </p>
                <p className="text-sm text-[var(--color-text-secondary)]">
                  {insights.flagged.map(f => f.name).join(', ')} — consider discussing these patterns with your healthcare provider.
                </p>
              </div>
            </div>
          </div>
        )}
        
        {/* Disease risk grid */}
        <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8 ${showBlur ? 'relative' : ''}`}>
          {showBlur && (
            <div className="absolute inset-0 backdrop-blur-sm bg-[var(--color-surface)]/50 z-10 flex items-center justify-center rounded-lg">
              <div className="text-center p-4">
                <CalendarIcon size={24} className="mx-auto mb-2 text-[var(--color-text-muted)]" />
                <p className="text-sm text-[var(--color-text-secondary)]">
                  Complete {7 - insights.checkins_used} more check-ins for full results
                </p>
              </div>
            </div>
          )}
          {Object.entries(insights.diseases || {}).map(([key, disease]) => (
            <DiseaseCard 
              key={key} 
              disease={{ ...disease, key }} 
              trends={history?.[key] || []}
            />
          ))}
        </div>
        
        {/* Weekly stats table */}
        {weeklyStats && Object.keys(weeklyStats).length > 0 && (
          <div className="card p-4 mb-8">
            <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
              <ChartIcon size={18} />
              Weekly Biomarker Summary
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs text-[var(--color-text-muted)] uppercase tracking-wider">
                    <th className="pb-2">Metric</th>
                    <th className="pb-2">Baseline</th>
                    <th className="pb-2">Current</th>
                    <th className="pb-2">Change</th>
                    <th className="pb-2">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(weeklyStats).map(([key, stat]) => (
                    <StatRow key={key} stat={stat} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        
        {/* Weekly report */}
        {report && (
          <div className="card p-4 mb-8">
            <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
              <FileTextIcon size={18} />
              Weekly Report
            </h2>
            <p className="text-[var(--color-text-secondary)] leading-relaxed mb-4">
              {report.narrative}
            </p>
            {report.concerns && report.concerns.length > 0 && (
              <div className="border-t border-[var(--color-border)] pt-4 mt-4">
                <h3 className="text-sm font-medium mb-2">Areas of Concern</h3>
                <ul className="space-y-2">
                  {report.concerns.map((concern, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <AlertCircleIcon size={14} className="text-[var(--color-trend-rising)] flex-shrink-0 mt-0.5" />
                      <span>
                        <strong>{concern.disease}</strong> ({concern.score}%): {concern.explanation}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        
        {/* Disclaimer */}
        <div className="text-center text-xs text-[var(--color-text-muted)] py-4 border-t border-[var(--color-border)]">
          <p>VocalVitals is a screening aid, not a diagnostic tool. Consult a healthcare provider for medical advice.</p>
        </div>
      </div>
    </div>
  )
}

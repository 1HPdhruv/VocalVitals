import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { db } from '../firebase'
import { doc, getDoc } from 'firebase/firestore'
import { useAuth } from '../contexts/AuthContext'
import { FileTextIcon, AlertTriangleIcon } from '../components/Icons'
import { showToast } from '../components/Toast'

export default function Report() {
  const { id } = useParams()
  const { user } = useAuth()
  const [report, setReport]     = useState(null)
  const [loading, setLoading]   = useState(true)
  const [downloading, setDownloading] = useState(false)

  useEffect(() => {
    const load = async () => {
      try {
        if (!db) {
          const saved = JSON.parse(localStorage.getItem('vocal_vitals_analyses') || '[]')
          const match = saved.find(item => item.id === id) || saved[0]
          if (match) {
            setReport({
              id: match.id,
              ...match.analysis,
              acousticFeatures: match.features || match.analysis?.features || {},
              transcript: match.transcript || match.analysis?.transcript || '',
              key_insights: match.key_insights || match.analysis?.key_insights || [],
              anomalies: match.anomalies || match.analysis?.anomalies || [],
              suggestions: match.suggestions || match.analysis?.suggestions || [],
              conditions: match.analysis?.conditions || [],
            })
          }
          return
        }
        const snap = await getDoc(doc(db, 'analyses', id))
        if (snap.exists()) setReport({ id: snap.id, ...snap.data() })
      } catch { /* Report load may fail */ }
      finally { setLoading(false) }
    }
    load()
  }, [id])

  const downloadPDF = async () => {
    setDownloading(true)
    try {
      const resp = await fetch('/report/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audioUrl: report?.audioUrl || '',
          userId:   user?.uid || 'anon',
          userName: user?.displayName || 'Patient',
          interviewRounds: report?.interviewRounds || [],
          originalFeatures: report?.acousticFeatures,
          originalTranscript: report?.transcript,
        }),
      })
      const data = await resp.json()
      if (data.pdf_base64) {
        const link = document.createElement('a')
        link.href = `data:application/pdf;base64,${data.pdf_base64}`
        link.download = `vocal-vitals-report-${id}.pdf`
        link.click()
        showToast('Report downloaded', 'success')
      }
    } catch {
      showToast('Failed to generate PDF', 'error')
    }
    finally { setDownloading(false) }
  }

  if (loading) return (
    <div className="page-bg min-h-screen pt-20 flex items-center justify-center">
      <div className="skeleton h-8 w-32" />
    </div>
  )

  if (!report) return (
    <div className="page-bg min-h-screen pt-20 flex items-center justify-center">
      <div className="card p-8 text-center max-w-md">
        <p className="text-[var(--color-text-muted)]">Report not found or you don&apos;t have access.</p>
      </div>
    </div>
  )

  const fr = report.finalReport || {}
  const feats = report.acousticFeatures || {}

  const severityClass = {
    high: 'trend-badge trend-rising',
    medium: 'trend-badge trend-rising',
    low: 'trend-badge trend-stable',
  }

  return (
    <div className="page-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-3xl mx-auto space-y-5">
        {/* Header */}
        <div className="card p-6 border-[var(--color-primary)]/20">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs text-[var(--color-text-muted)] font-mono uppercase tracking-widest mb-1">Pre-Consultation Report</p>
              <h1 className="text-2xl font-medium text-[var(--color-text-primary)]">
                {fr.chief_complaint || report.conditions?.[0]?.name || 'Voice Health Analysis'}
              </h1>
              <p className="text-sm text-[var(--color-text-muted)] mt-1">
                {report.timestamp?.toDate?.()?.toLocaleString() || ''}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              {report.severity && (
                <span className={severityClass[report.severity] || 'trend-badge trend-stable'}>
                  {report.severity.toUpperCase()} RISK
                </span>
              )}
              {fr.urgency && (
                <span className={`text-xs text-center ${
                  fr.urgency === 'urgent' ? 'trend-badge trend-rising' : 
                  fr.urgency === 'soon' ? 'trend-badge trend-rising' : 
                  'trend-badge trend-stable'
                }`}>
                  {fr.urgency.toUpperCase()}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Conditions */}
        {report.conditions?.length > 0 && (
          <div className="card p-5">
            <h2 className="font-medium text-[var(--color-text-primary)] mb-3">Detected Conditions</h2>
            <div className="space-y-2">
              {report.conditions.map((c, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-[var(--color-text-secondary)]">{c.name}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 bg-[var(--color-surface-overlay)] rounded-full">
                      <div className="h-full bg-[var(--color-primary)] rounded-full" style={{ width: `${c.confidence}%` }} />
                    </div>
                    <span className="text-xs font-mono text-[var(--color-primary)] w-10 text-right">{c.confidence}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Symptom Timeline */}
        {fr.timeline?.length > 0 && (
          <div className="card p-5">
            <h2 className="font-medium text-[var(--color-text-primary)] mb-3">Symptom Timeline</h2>
            <ul className="space-y-1.5">
              {fr.timeline.map((t, i) => (
                <li key={i} className="text-sm text-[var(--color-text-secondary)] flex gap-2">
                  <span className="text-[var(--color-primary)]">•</span>{t}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Acoustic Indicators */}
        {fr.acoustic_indicators?.length > 0 && (
          <div className="card p-5">
            <h2 className="font-medium text-[var(--color-text-primary)] mb-3">Acoustic Indicators</h2>
            <ul className="space-y-1.5">
              {fr.acoustic_indicators.map((a, i) => (
                <li key={i} className="text-sm text-[var(--color-text-secondary)] flex gap-2">
                  <AlertTriangleIcon className="icon-sm text-[var(--color-trend-rising)] flex-shrink-0 mt-0.5" />{a}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Feature Values */}
        {Object.keys(feats).length > 0 && (
          <div className="card p-5">
            <h2 className="font-medium text-[var(--color-text-primary)] mb-3">Raw Acoustic Data</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {['pitch_mean', 'pitch_std', 'jitter', 'shimmer', 'hnr', 'breathiness', 'speech_rate', 'pause_freq'].map(k => (
                feats[k] != null ? (
                  <div key={k} className="bg-[var(--color-surface-overlay)] rounded p-3">
                    <div className="text-xs text-[var(--color-text-muted)]">{k}</div>
                    <div className="font-mono font-medium text-[var(--color-primary)]">{typeof feats[k] === 'number' ? feats[k].toFixed(3) : feats[k]}</div>
                  </div>
                ) : null
              ))}
            </div>
          </div>
        )}

        {/* Specialist */}
        {fr.specialist && (
          <div className="card p-5">
            <h2 className="font-medium text-[var(--color-text-primary)] mb-2">Recommended Specialist</h2>
            <p className="text-[var(--color-primary)] font-medium">{fr.specialist}</p>
            {fr.full_note && (
              <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
                <h3 className="text-sm font-medium text-[var(--color-text-muted)] mb-2">Full Clinical Note</h3>
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{fr.full_note}</p>
              </div>
            )}
          </div>
        )}

        {/* Transcript */}
        {report.transcript && (
          <div className="card p-5">
            <h2 className="font-medium text-[var(--color-text-primary)] mb-2">Patient Transcript</h2>
            <p className="text-sm text-[var(--color-text-muted)] italic">&ldquo;{report.transcript}&rdquo;</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={downloadPDF}
            disabled={downloading}
            className="btn btn-primary px-6 py-3 flex items-center gap-2"
          >
            {downloading ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                Generating...
              </>
            ) : (
              <>
                <FileTextIcon />
                Download PDF
              </>
            )}
          </button>
          <button onClick={() => window.print()} className="btn btn-secondary px-4 py-3">
            Print
          </button>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-[var(--color-text-muted)] text-center border-t border-[var(--color-border)] pt-4 flex items-center justify-center gap-1">
          <AlertTriangleIcon className="icon-sm" />
          This report is generated by an AI screening tool and does NOT constitute a medical diagnosis.
          Always consult a qualified healthcare professional.
        </p>
      </div>
    </div>
  )
}

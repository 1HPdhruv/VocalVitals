import { useState, useRef } from 'react'
import PropTypes from 'prop-types'
import { storage } from '../firebase'
import { ref, uploadBytes, getDownloadURL } from 'firebase/storage'
import { useAuth } from '../contexts/AuthContext'
import { GitCompareIcon, CheckIcon, MicrophoneIcon, TrendingUpIcon, TrendingDownIcon, MinusIcon } from '../components/Icons'

function CompareTable({ comparison }) {
  if (!comparison?.key_changes?.length) return null

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            <th className="text-left py-2 text-[var(--color-text-muted)] font-medium">Metric</th>
            <th className="text-right py-2 text-[var(--color-primary)] font-mono">Recording A</th>
            <th className="text-right py-2 text-[var(--color-primary)] font-mono">Recording B</th>
            <th className="text-right py-2 text-[var(--color-text-muted)]">Delta</th>
            <th className="text-right py-2 text-[var(--color-text-muted)]">Status</th>
          </tr>
        </thead>
        <tbody>
          {comparison.key_changes.map((row, i) => {
            const delta = row.delta || (row.value_b - row.value_a)
            const status = Math.abs(delta) < 0.5 ? 'stable'
              : delta < 0 ? 'improved' : 'worsened'
            const statusColors = {
              stable: 'trend-badge trend-stable',
              improved: 'trend-badge trend-falling',
              worsened: 'trend-badge trend-rising',
            }
            const deltaColors = {
              stable: 'text-[var(--color-trend-stable)]',
              improved: 'text-[var(--color-trend-falling)]',
              worsened: 'text-[var(--color-trend-rising)]',
            }

            return (
              <tr key={i} className="border-b border-[var(--color-border)]/50 hover:bg-[var(--color-surface-overlay)]">
                <td className="py-2.5 text-[var(--color-text-secondary)]">{row.metric}</td>
                <td className="py-2.5 text-right font-mono text-[var(--color-text-primary)]">
                  {typeof row.value_a === 'number' ? row.value_a.toFixed(2) : row.value_a}
                </td>
                <td className="py-2.5 text-right font-mono text-[var(--color-text-primary)]">
                  {typeof row.value_b === 'number' ? row.value_b.toFixed(2) : row.value_b}
                </td>
                <td className={`py-2.5 text-right font-mono font-medium ${deltaColors[status]}`}>
                  {delta > 0 ? '+' : ''}{typeof delta === 'number' ? delta.toFixed(2) : delta}
                </td>
                <td className="py-2.5 text-right">
                  <span className={statusColors[status]}>
                    {status === 'stable' ? '– Stable' : status === 'improved' ? '↓ Better' : '↑ Worse'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

CompareTable.propTypes = {
  comparison: PropTypes.shape({
    key_changes: PropTypes.array,
  }),
}

function FileUploadZone({ label, onChange, file }) {
  const inputRef = useRef(null)
  return (
    <div
      onClick={() => inputRef.current?.click()}
      className={`border-2 border-dashed rounded p-6 text-center cursor-pointer transition-all
        ${file
          ? 'border-[var(--color-primary)]/50 bg-[var(--color-primary)]/5'
          : 'border-[var(--color-border)] hover:border-[var(--color-primary)]/40'
        }`}
    >
      <input ref={inputRef} type="file" accept="audio/*" className="hidden" onChange={e => onChange(e.target.files[0])} />
      {file ? (
        <CheckIcon className="w-8 h-8 mx-auto mb-2 text-[var(--color-primary)]" />
      ) : (
        <MicrophoneIcon className="w-8 h-8 mx-auto mb-2 text-[var(--color-text-muted)]" />
      )}
      <p className="text-sm text-[var(--color-text-primary)] font-medium">{label}</p>
      {file ? (
        <p className="text-xs text-[var(--color-text-muted)] mt-1">{file.name}</p>
      ) : (
        <p className="text-xs text-[var(--color-text-muted)] mt-1">Click to upload audio file</p>
      )}
    </div>
  )
}

FileUploadZone.propTypes = {
  label: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
  file: PropTypes.object,
}

export default function Compare() {
  const { user } = useAuth()
  const [fileA, setFileA] = useState(null)
  const [fileB, setFileB] = useState(null)
  const [phase, setPhase]   = useState('idle')
  const [result, setResult] = useState(null)

  const handleCompare = async () => {
    if (!fileA || !fileB) return
    setPhase('uploading')
    setResult(null)

    try {
      const uid = user?.uid || 'compare'

      if (!storage) return;
      const refA = ref(storage, `compare/${uid}/${Date.now()}-A.${fileA.name.split('.').pop()}`)
      const refB = ref(storage, `compare/${uid}/${Date.now()}-B.${fileB.name.split('.').pop()}`)

      await Promise.all([uploadBytes(refA, fileA), uploadBytes(refB, fileB)])
      const [urlA, urlB] = await Promise.all([getDownloadURL(refA), getDownloadURL(refB)])

      setPhase('analyzing')
      const resp = await fetch('/compare', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audioUrlA: urlA, audioUrlB: urlB, userId: uid }),
      })
      const data = await resp.json()
      setResult(data)
      setPhase('done')
    } catch {
      setPhase('idle')
    }
  }

  const trendIcon = result?.comparison?.overall_trend === 'improving' 
    ? <TrendingDownIcon className="icon-sm" />
    : result?.comparison?.overall_trend === 'worsening'
    ? <TrendingUpIcon className="icon-sm" />
    : <MinusIcon className="icon-sm" />

  const trendClass = result?.comparison?.overall_trend === 'improving'
    ? 'trend-badge trend-falling'
    : result?.comparison?.overall_trend === 'worsening'
    ? 'trend-badge trend-rising'
    : 'trend-badge trend-stable'

  return (
    <div className="page-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-medium text-[var(--color-text-primary)] flex items-center gap-2">
            <GitCompareIcon />
            Second Opinion Comparison
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">Compare two voice recordings to track acoustic changes over time</p>
        </div>

        {/* Upload Zone */}
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-[var(--color-primary)] uppercase tracking-widest mb-2">Recording A (Earlier)</p>
            <FileUploadZone label="Upload Recording A" onChange={setFileA} file={fileA} />
          </div>
          <div>
            <p className="text-xs text-[var(--color-primary)] uppercase tracking-widest mb-2">Recording B (Recent)</p>
            <FileUploadZone label="Upload Recording B" onChange={setFileB} file={fileB} />
          </div>
        </div>

        <button
          onClick={handleCompare}
          disabled={!fileA || !fileB || phase === 'uploading' || phase === 'analyzing'}
          className="w-full btn btn-primary py-4 text-lg disabled:opacity-40"
        >
          {phase === 'uploading' ? 'Uploading Both Files...'
           : phase === 'analyzing' ? 'Comparing with AI...'
           : 'Compare Recordings'}
        </button>

        {/* Results */}
        {phase === 'done' && result && (
          <div className="space-y-5">
            {/* Overall trend */}
            {result.comparison?.overall_trend && (
              <div className="card p-5">
                <div className="flex items-center gap-3 mb-3">
                  <h2 className="text-lg font-medium text-[var(--color-text-primary)]">Overall Trend</h2>
                  <span className={trendClass}>
                    {trendIcon}
                    {result.comparison.overall_trend.toUpperCase()}
                  </span>
                </div>
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{result.comparison.comparison_summary}</p>
                {result.comparison.clinical_note && (
                  <div className="mt-3 p-3 bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/20 rounded">
                    <p className="text-xs text-[var(--color-primary)] mb-1">Clinical Note</p>
                    <p className="text-sm text-[var(--color-text-secondary)]">{result.comparison.clinical_note}</p>
                  </div>
                )}
              </div>
            )}

            {/* Delta table */}
            <div className="card p-5">
              <h3 className="font-medium text-[var(--color-text-primary)] mb-4">Metric Comparison</h3>
              <CompareTable comparison={result.comparison} />
            </div>

            {/* Feature bars */}
            <div className="grid md:grid-cols-2 gap-4">
              {['A', 'B'].map(rec => {
                const feats = rec === 'A' ? result.features_a : result.features_b
                return (
                  <div key={rec} className="card p-4">
                    <h4 className="text-sm font-medium mb-3 text-[var(--color-primary)]">Recording {rec}</h4>
                    <div className="space-y-2 text-xs font-mono">
                      {['pitch_mean', 'jitter', 'shimmer', 'hnr', 'breathiness'].map(k => (
                        <div key={k} className="flex justify-between text-[var(--color-text-muted)]">
                          <span>{k}</span>
                          <span className="text-[var(--color-text-primary)]">{feats?.[k]?.toFixed?.(3) ?? 'N/A'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {phase === 'idle' && (
          <div className="card p-8 text-center">
            <GitCompareIcon className="w-10 h-10 mx-auto mb-3 text-[var(--color-text-muted)] opacity-40" />
            <p className="text-[var(--color-text-muted)] text-sm">Upload two recordings to see side-by-side acoustic comparison with AI interpretation.</p>
          </div>
        )}
      </div>
    </div>
  )
}

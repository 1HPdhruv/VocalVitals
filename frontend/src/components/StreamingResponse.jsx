import React, { useEffect, useRef, useState } from 'react'

/**
 * SSE stream consumer for Claude analysis.
 * Renders incremental conditions as Claude mentions them.
 */
export default function StreamingResponse({ streamUrl, onComplete, requestBody }) {
  const [status, setStatus]           = useState('idle') // idle | streaming | done | error
  const [statusMsg, setStatusMsg]     = useState('')
  const [conditions, setConditions]   = useState([])
  const [explanation, setExplanation] = useState('')
  const [followUps, setFollowUps]     = useState([])
  const [severity, setSeverity]       = useState(null)
  const [consistencyScore, setConsistencyScore] = useState(null)
  const [features, setFeatures]       = useState(null)
  const [transcript, setTranscript]   = useState('')
  const [rawChunks, setRawChunks]     = useState('')
  const abortRef = useRef(null)

  useEffect(() => {
    if (!streamUrl || !requestBody) return

    setStatus('streaming')
    setConditions([])
    setExplanation('')
    setFollowUps([])
    setSeverity(null)
    setRawChunks('')

    const controller = new AbortController()
    abortRef.current = controller

    ;(async () => {
      try {
        const response = await fetch(streamUrl, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(requestBody),
          signal:  controller.signal,
        })

        const reader  = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer    = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const raw = line.slice(6)
            try {
              const msg = JSON.parse(raw)

              if (msg.status) setStatusMsg(msg.status)
              if (msg.features) setFeatures(msg.features)
              if (msg.transcript) setTranscript(msg.transcript)

              if (msg.chunk) {
                setRawChunks(prev => {
                  const updated = prev + msg.chunk
                  // Try to parse partial JSON for real-time condition display
                  try {
                    const parsed = JSON.parse(updated.trim())
                    if (parsed.conditions) setConditions(parsed.conditions)
                    if (parsed.explanation) setExplanation(parsed.explanation)
                    if (parsed.follow_up_questions) setFollowUps(parsed.follow_up_questions)
                    if (parsed.severity) setSeverity(parsed.severity)
                    if (parsed.consistency_score != null) setConsistencyScore(parsed.consistency_score)
                  } catch { /* Still accumulating */ }
                  return updated
                })
              }

              if (msg.done && msg.result) {
                const r = msg.result
                setConditions(r.conditions || [])
                setExplanation(r.explanation || '')
                setFollowUps(r.follow_up_questions || [])
                setSeverity(r.severity)
                setConsistencyScore(r.consistency_score)
                setStatus('done')
                onComplete?.({
                  ...r,
                  acousticFeatures: features,
                  transcript,
                })
              }

              if (msg.error) {
                setStatus('error')
                setStatusMsg(msg.error)
              }
            } catch { /* Parse error, skip */ }
          }
        }
        setStatus('done')
      } catch (err) {
        if (err.name !== 'AbortError') {
          setStatus('error')
          setStatusMsg(err.message)
        }
      }
    })()

    return () => controller.abort()
  }, [streamUrl, JSON.stringify(requestBody)])

  if (status === 'idle') return null

  return (
    <div className="space-y-4">
      {/* Status line */}
      {(status === 'streaming' || statusMsg) && (
        <div className="flex items-center gap-3 p-3 glass-card">
          {status === 'streaming' && (
            <span className="flex gap-1">
              <span className="streaming-dot" />
              <span className="streaming-dot" />
              <span className="streaming-dot" />
            </span>
          )}
          <span className="text-sm text-gray-400 font-mono">{statusMsg || 'Analyzing…'}</span>
        </div>
      )}

      {/* Real-time conditions as they arrive */}
      {conditions.length > 0 && (
        <div>
          <h3 className="text-xs uppercase tracking-widest text-gray-500 mb-2">Detected Conditions</h3>
          <div className="space-y-2">
            {conditions.map((c, i) => (
              <div key={i} className="glass-card p-3 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-white">{c.name}</span>
                  {c.triggered_features?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {c.triggered_features.map((f, fi) => (
                        <span key={fi} className="text-xs px-1.5 py-0.5 rounded bg-cyan-400/10 text-cyan-DEFAULT font-mono">
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-lg font-bold font-mono text-cyan-DEFAULT">{c.confidence}%</div>
                  <div className="w-16 h-1.5 bg-dark-600 rounded-full mt-1">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-DEFAULT transition-all"
                      style={{ width: `${c.confidence}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Severity badge */}
      {severity && (
        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-semibold severity-${severity}`}>
          <span className={`w-2 h-2 rounded-full ${severity === 'low' ? 'bg-green-vital' : severity === 'medium' ? 'bg-amber-warn' : 'bg-red-alert'}`} />
          {severity.toUpperCase()} RISK
        </div>
      )}

      {/* Explanation */}
      {explanation && (
        <div className="glass-card p-4">
          <h3 className="text-xs uppercase tracking-widest text-gray-500 mb-2">AI Assessment</h3>
          <p className="text-sm text-gray-300 leading-relaxed">{explanation}</p>
        </div>
      )}

      {/* Follow-up questions */}
      {followUps.length > 0 && (
        <div className="glass-card p-4">
          <h3 className="text-xs uppercase tracking-widest text-gray-500 mb-2">Follow-up Questions</h3>
          <ol className="space-y-2">
            {followUps.map((q, i) => (
              <li key={i} className="text-sm text-gray-300 flex gap-2">
                <span className="text-cyan-DEFAULT font-mono font-bold">{i + 1}.</span>
                <span>{q}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {status === 'error' && (
        <div className="glass-card p-4 border-red-alert/30 bg-red-alert/5">
          <p className="text-red-alert text-sm">⚠ {statusMsg}</p>
        </div>
      )}
    </div>
  )
}

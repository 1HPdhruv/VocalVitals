import { useState, useCallback, useEffect } from 'react'
import PropTypes from 'prop-types'
import { useAuth } from '../contexts/AuthContext'
import WaveformVisualizer from '../components/WaveformVisualizer'
import SocraticChat from '../components/SocraticChat'
import ClinicCard from '../components/ClinicCard'
import ConsistencyScore from '../components/ConsistencyScore'
import { useAudioRecorder } from '../hooks/useAudioRecorder'
import { MicrophoneIcon, StopIcon, FileTextIcon, RefreshIcon, ActivityIcon, AlertTriangleIcon } from '../components/Icons'
import { showToast } from '../components/Toast'

const DEMO_FEATURES = {
  pitch_mean: 187.3, pitch_std: 24.1, jitter: 0.89, shimmer: 3.2,
  hnr: 11.4, speech_rate: 3.1, pause_freq: 4, breathiness: 0.42,
  duration: 15.0,
  mfcc: [-6.2, 112.3, -18.4, 8.1, -5.3, 2.7, -1.1, 0.9, -0.4, 1.2, 0.3, -0.8, 0.2],
}
const DEMO_TRANSCRIPT = "I have been feeling quite tired lately and my throat has been sore for about a week now. My voice feels strained when I speak for long periods."

const KEY_FEATURES = [
  { key: 'pitch_mean', label: 'Pitch Mean', unit: 'Hz', normal: [100, 300] },
  { key: 'jitter',     label: 'Jitter',     unit: '%',  normal: [0, 1.04] },
  { key: 'shimmer',    label: 'Shimmer',    unit: '%',  normal: [0, 3.81] },
  { key: 'hnr',        label: 'HNR',        unit: 'dB', normal: [20, 45] },
  { key: 'speech_rate',label: 'Speech Rate',unit: 'w/s',normal: [2, 5] },
  { key: 'breathiness',label: 'Breathiness',unit: '',   normal: [0, 0.4] },
]

function FeatureGrid({ features }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {KEY_FEATURES.map(({ key, label, unit, normal }) => {
        const val = features?.[key]
        if (val == null) return null
        const isNormal = val >= normal[0] && val <= normal[1]
        return (
          <div key={key} className="card p-3">
            <div className="text-xs text-[var(--color-text-muted)] mb-1">{label}</div>
            <div className={`text-lg font-medium font-mono ${isNormal ? 'text-[var(--color-primary)]' : 'text-[var(--color-trend-rising)]'}`}>
              {typeof val === 'number' ? val.toFixed(2) : val}
              <span className="text-xs text-[var(--color-text-muted)] ml-1">{unit}</span>
            </div>
            <div className={`text-xs mt-1 ${isNormal ? 'text-[var(--color-primary)]' : 'text-[var(--color-trend-rising)]'}`}>
              {isNormal ? 'Normal' : 'Elevated'}
            </div>
          </div>
        )
      })}
    </div>
  )
}

FeatureGrid.propTypes = {
  features: PropTypes.object,
}

export default function Screen() {
  const { user } = useAuth()
  const [demoMode, setDemoMode] = useState(false)
  const [phase, setPhase]       = useState('idle') // idle | recording | uploading | analyzing | interview | report
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState(null)
  const [analysisData, setAnalysisData] = useState(null)
  const [clinic, setClinic]     = useState(null)
  const [features, setFeatures] = useState(null)
  const [transcript, setTranscript] = useState('')

  // Socratic interview state
  const [questions, setQuestions]         = useState([])
  const [currentRound, setCurrentRound]   = useState(0)
  const [interviewHistory, setInterviewHistory] = useState([])
  const [interviewLoading, setInterviewLoading] = useState(false)
  const [updatedConditions, setUpdatedConditions] = useState([])

  // Streaming state
  const [streamStatus, setStreamStatus]   = useState('')
  const [streamConditions, setStreamConditions] = useState([])
  const [streamSeverity, setStreamSeverity] = useState(null)
  const [streamExplanation, setStreamExplanation] = useState('')
  const [consistencyScore, setConsistencyScore] = useState(null)
  const [isStreaming, setIsStreaming]       = useState(false)

  const [uploadError, setUploadError]     = useState(null)
  const [geolocation, setGeolocation]     = useState(null)

  const persistAnalysis = useCallback((analysis) => {
    try {
      const existing = JSON.parse(localStorage.getItem('vocal_vitals_analyses') || '[]')
      const next = [
        {
          id: `${Date.now()}`,
          timestamp: new Date().toISOString(),
          userId: user?.uid || 'demo',
          audioBlobSize: analysis?.audioBlobSize || null,
          ...analysis,
        },
        ...existing,
      ]
      localStorage.setItem('vocal_vitals_analyses', JSON.stringify(next.slice(0, 50)))
    } catch {
      // Storage may be full or unavailable
    }
  }, [user?.uid])

  const {
    isRecording, audioBlob, localUrl, duration, error: recError,
    uploading, analyserNode, startRecording, stopRecording,
  } = useAudioRecorder({ userId: user?.uid, demoMode })

  const clearAnalysisState = useCallback(() => {
    setResult(null)
    setAnalysisData(null)
    setClinic(null)
    setFeatures(null)
    setTranscript('')
    setQuestions([])
    setCurrentRound(0)
    setInterviewHistory([])
    setUpdatedConditions([])
    setStreamStatus('')
    setStreamConditions([])
    setStreamSeverity(null)
    setStreamExplanation('')
    setConsistencyScore(null)
    setUploadError(null)
  }, [])

  const handleStartRecording = useCallback(async () => {
    clearAnalysisState()
    setPhase('recording')
    setIsStreaming(false)
    setStreamStatus('Recording started')
    await startRecording()
  }, [clearAnalysisState, startRecording])

  // Get geolocation on mount
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        pos => setGeolocation({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => setGeolocation(null)
      )
    }
  }, [])

  const runAnalysis = useCallback(async ({ file, demo = false, audioBlobSize = null } = {}) => {
    clearAnalysisState()
    setAnalysisData(null)
    setLoading(true)
    setPhase('analyzing')
    setIsStreaming(true)
    setStreamStatus('Starting analysis...')

    try {
      const requestTs = Date.now()
      const formData = new FormData()
      if (file) {
        formData.append('file', file)
      }
      formData.append('userId', user?.uid || 'demo')
      formData.append('demoMode', String(demo))
      formData.append('requestTs', String(requestTs))
      if (geolocation?.lat != null) formData.append('lat', String(geolocation.lat))
      if (geolocation?.lon != null) formData.append('lon', String(geolocation.lon))

      if (demo) {
        formData.append('demoTranscript', DEMO_TRANSCRIPT)
      }

      const requestStarted = performance.now()
      const response = await fetch(`/analyze?ts=${requestTs}`, {
        method: 'POST',
        body: formData,
        cache: 'no-store',
      })

      if (!response.ok) {
        let backendError = ''
        try {
          const errorJson = await response.json()
          backendError = errorJson?.error
            ? `${errorJson.error}${errorJson.stage ? ` (stage: ${errorJson.stage})` : ''}`
            : ''
        } catch (_) {
          backendError = await response.text()
        }
        throw new Error(backendError || `Request failed with ${response.status}`)
      }

      const r = await response.json()
      if (r?.error) {
        throw new Error(`${r.error}${r.stage ? ` (stage: ${r.stage})` : ''}`)
      }
      await new Promise(res => setTimeout(res, 1200))
      // Analysis complete

      const scores = r?.risk_scores || null
      if (!scores || Object.keys(scores).length === 0) {
        throw new Error('Backend returned invalid analysis payload (missing risk_scores)')
      }

      const normalizeScoreToPercent = (raw) => {
        const n = Number(raw)
        if (!Number.isFinite(n)) return 0
        const scaled = n <= 1 ? n * 100 : n
        return Math.round(Math.max(0, Math.min(100, scaled)))
      }

      const normalizedScores = scores
      const mappedData = {
        fatigue: normalizeScoreToPercent(normalizedScores.fatigue_score ?? 0),
        stress: normalizeScoreToPercent(normalizedScores.stress_score ?? 0),
        respiratory: normalizeScoreToPercent(normalizedScores.respiratory_risk ?? 0),
        depression: normalizeScoreToPercent(normalizedScores.depression_risk ?? 0),
        nervousness: normalizeScoreToPercent(normalizedScores.nervousness_score ?? 0),
        consistency: normalizeScoreToPercent(normalizedScores.consistency_score ?? 0),
        cough: normalizeScoreToPercent(normalizedScores.cough_score ?? 0),
        coughNatural: normalizeScoreToPercent(normalizedScores.cough_naturalness_score ?? 0),
      }

      setAnalysisData(mappedData)

      setResult(r)

      const derivedConditions = r.conditions || Object.entries(mappedData || {}).map(([key, value]) => ({
        name: key.replace(/_/g, ' '),
        confidence: Math.max(0, Math.min(100, Number(value || 0))),
        triggered_features: [],
      }))

      setStreamConditions(derivedConditions)
      setStreamSeverity(derivedConditions[0] ? (derivedConditions[0].confidence >= 75 ? 'high' : derivedConditions[0].confidence >= 45 ? 'medium' : 'low') : null)
      setStreamExplanation(r.explanation || r.key_insights?.[0] || '')
      setConsistencyScore(mappedData.consistency)
      setQuestions(r.follow_up_questions || [])
      setStreamStatus('Analysis complete')
      setIsStreaming(false)
      setPhase((r.follow_up_questions || []).length > 0 ? 'interview' : 'report')
      setFeatures(r.features ?? null)
      setTranscript(r.transcript ?? '')

      persistAnalysis({
        summary: r.key_insights?.[0] || r.explanation || '',
        risk_scores: r.risk_scores,
        key_insights: r.key_insights,
        anomalies: r.anomalies,
        suggestions: r.suggestions,
        features: r.features ?? null,
        transcript: r.transcript ?? '',
        blobSize: audioBlobSize,
      })

      if (!demoMode && user) {
        try {
          const existing = JSON.parse(localStorage.getItem('vocal_vitals_journal') || '[]')
          existing.unshift({
            id: `${Date.now()}`,
            timestamp: new Date().toISOString(),
            userId: user.uid,
            features: r.features ?? null,
            transcript: r.transcript ?? '',
            analysis: r,
          })
          localStorage.setItem('vocal_vitals_journal', JSON.stringify(existing.slice(0, 100)))
        } catch {
          // Journal save may fail if storage is full
        }
      }
    } catch (err) {
      setIsStreaming(false)
      setPhase('idle')
      setUploadError(err?.message || 'Analysis failed')
      showToast('Analysis failed: ' + (err?.message || 'Unknown error'), 'error')
    } finally {
      setLoading(false)
    }
  }, [demoMode, user, geolocation, persistAnalysis, clearAnalysisState])

  const handleStopRecording = useCallback(async () => {
    const blob = await stopRecording()
    if (!blob || !blob.size) {
      setUploadError('No audio was captured. Please try again.')
      showToast('No audio captured', 'error')
      return
    }

    setUploadError(null)
    setPhase('uploading')

    try {
      if (demoMode) {
        await runAnalysis({ demo: true, audioBlobSize: blob.size })
        return
      }

      await runAnalysis({
        file: new File([blob], 'recording.webm', { type: blob.type || 'audio/webm' }),
        demo: false,
        audioBlobSize: blob.size,
      })
    } catch (err) {
      setUploadError(err.message)
      setPhase('idle')
      showToast('Analysis failed', 'error')
    }
  }, [stopRecording, demoMode, runAnalysis])

  const handleSocraticAnswer = useCallback(async (answer, round) => {
    setInterviewLoading(true)
    const history = [...interviewHistory, { question: questions[round], answer, round }]
    setInterviewHistory(history)

    try {
      const response = await fetch('/analyze/socratic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          originalFeatures: features || DEMO_FEATURES,
          originalAnalysis: result,
          conversationHistory: history,
          newAnswer: answer,
        }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const msg = JSON.parse(line.slice(6))
            if (msg.done && msg.result) {
              const r = msg.result
              setUpdatedConditions(r.updated_conditions || [])
              const nextQ = r.new_question
              if (nextQ && round < 2) {
                setQuestions(prev => {
                  const q = [...prev]
                  q[round + 1] = nextQ
                  return q
                })
                setCurrentRound(round + 1)
              } else {
                setCurrentRound(3) // Done
                setPhase('report')
              }
            }
          } catch { /* continue parsing */ }
        }
      }
    } catch {
      showToast('Interview error', 'error')
    } finally {
      setInterviewLoading(false)
    }
  }, [interviewHistory, questions, features, result])

  const resetAll = () => {
    setPhase('idle')
    setLoading(false)
    setResult(null)
    setAnalysisData(null)
    setClinic(null)
    setFeatures(null)
    setTranscript('')
    setQuestions([])
    setCurrentRound(0)
    setInterviewHistory([])
    setStreamConditions([])
    setStreamSeverity(null)
    setStreamExplanation('')
    setConsistencyScore(null)
    setIsStreaming(false)
    setUploadError(null)
  }

  const riskEntries = analysisData
    ? [
        ['fatigue', analysisData.fatigue],
        ['stress', analysisData.stress],
        ['respiratory', analysisData.respiratory],
        ['depression', analysisData.depression],
        ['nervousness', analysisData.nervousness],
        ['consistency', analysisData.consistency],
        ['cough', analysisData.cough],
        ['coughNatural', analysisData.coughNatural],
      ]
    : []

  return (
    <div className="page-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-5xl mx-auto">

        {/* Demo Mode Banner */}
        {demoMode && (
          <div className="card border-[var(--color-trend-rising)] bg-[var(--color-trend-rising)]/5 p-3 mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-[var(--color-trend-rising)] text-sm font-medium">
              <span className="w-2 h-2 rounded-full bg-[var(--color-trend-rising)]" />
              <span>Demo Mode — Using sample data. Results are not saved.</span>
            </div>
            <button onClick={() => { setDemoMode(false); resetAll() }} className="btn btn-ghost text-xs">
              Exit Demo
            </button>
          </div>
        )}

        <div className="grid lg:grid-cols-[1fr,1fr] gap-6">
          {/* Left Panel — Recording */}
          <div className="space-y-4">
            <div className="card p-6">
              <div className="flex items-center justify-between mb-4">
                <h1 className="text-xl font-medium text-[var(--color-text-primary)] flex items-center gap-2">
                  <MicrophoneIcon />
                  Voice Analysis
                </h1>
                {!demoMode && phase === 'idle' && (
                  <button
                    onClick={() => setDemoMode(true)}
                    className="btn btn-ghost text-xs"
                    id="demo-mode-toggle"
                  >
                    Try Demo
                  </button>
                )}
              </div>

              {/* Waveform */}
              <WaveformVisualizer analyserNode={analyserNode} isRecording={isRecording} height={140} />

              {/* Duration */}
              {(isRecording || duration > 0) && (
                <div className="flex items-center gap-2 mt-2">
                  {isRecording && <span className="w-2 h-2 rounded-full bg-[var(--color-error)] animate-pulse" />}
                  <span className="font-mono text-sm text-[var(--color-text-secondary)]">
                    {Math.floor(duration / 60).toString().padStart(2, '0')}:{(duration % 60).toString().padStart(2, '0')}
                  </span>
                  {isRecording && <span className="text-xs text-[var(--color-error)]">Recording</span>}
                </div>
              )}

              {/* Record Button */}
              {(phase === 'idle' || isRecording) && (
                <div className="flex gap-3 mt-5">
                  {!isRecording ? (
                    <button
                      id="record-btn"
                      onClick={handleStartRecording}
                      className="flex-1 btn btn-primary py-3 text-base flex items-center justify-center gap-2"
                    >
                      <span className="w-2.5 h-2.5 rounded-full bg-[var(--color-error)]" />
                      {demoMode ? 'Run Demo Analysis' : 'Start Recording'}
                    </button>
                  ) : (
                    <button
                      id="stop-btn"
                      onClick={handleStopRecording}
                      className="flex-1 btn btn-danger py-3 text-base flex items-center justify-center gap-2"
                    >
                      <StopIcon />
                      Stop & Analyze
                    </button>
                  )}
                </div>
              )}

              {/* Demo quick-run without mic */}
              {demoMode && phase === 'idle' && !isRecording && (
                <button
                  onClick={() => runAnalysis({ demo: true })}
                  className="w-full mt-3 btn btn-primary py-3 flex items-center justify-center gap-2"
                >
                  <ActivityIcon />
                  Run Demo Analysis
                </button>
              )}

              {/* Phase indicators */}
              {phase === 'uploading' && (
                <div className="mt-4 flex items-center gap-3 text-sm text-[var(--color-text-muted)]">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" />
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" style={{ animationDelay: '0.2s' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" style={{ animationDelay: '0.4s' }} />
                  </div>
                  Uploading audio...
                </div>
              )}

              {uploadError && (
                <div className="mt-3 p-3 card border-[var(--color-error)]/30 bg-[var(--color-error)]/5">
                  <p className="text-[var(--color-error)] text-sm flex items-center gap-2">
                    <AlertTriangleIcon />
                    Upload failed: {uploadError}
                  </p>
                  <button onClick={() => setPhase('idle')} className="mt-2 text-xs text-[var(--color-text-muted)] underline">Retry</button>
                </div>
              )}

              {recError && (
                <div className="mt-3 p-3 card border-[var(--color-error)]/30 bg-[var(--color-error)]/5">
                  <p className="text-[var(--color-error)] text-sm flex items-center gap-2">
                    <AlertTriangleIcon />
                    {recError}
                  </p>
                </div>
              )}

              {/* Audio playback */}
              {localUrl && phase !== 'idle' && (
                <audio src={localUrl} controls className="w-full mt-3 h-8 rounded" />
              )}

              {phase !== 'idle' && (
                <button onClick={resetAll} className="mt-3 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] underline flex items-center gap-1">
                  <RefreshIcon className="icon-sm" />
                  Start over
                </button>
              )}
            </div>

            {/* Streaming Status */}
            {isStreaming && (
              <div className="card p-4">
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" />
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" style={{ animationDelay: '0.2s' }} />
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)] animate-pulse" style={{ animationDelay: '0.4s' }} />
                  </div>
                  <span className="text-sm text-[var(--color-text-muted)] font-mono">{streamStatus}</span>
                </div>
                <div className="h-1 bg-[var(--color-surface-overlay)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--color-primary)] rounded-full animate-pulse" style={{ width: '60%' }} />
                </div>
              </div>
            )}

            {/* Feature Grid */}
            {(features || (demoMode && streamConditions.length > 0)) && (
              <div className="card p-4">
                <h3 className="text-xs uppercase tracking-widest text-[var(--color-text-muted)] mb-3">Acoustic Biomarkers</h3>
                <FeatureGrid features={features || DEMO_FEATURES} />
              </div>
            )}

            {/* Transcript */}
            {transcript && (
              <div className="card p-4">
                <h3 className="text-xs uppercase tracking-widest text-[var(--color-text-muted)] mb-2">Transcript</h3>
                <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed italic">&ldquo;{transcript}&rdquo;</p>
              </div>
            )}
          </div>

          {/* Right Panel — Results */}
          <div className="space-y-4">
            {loading && (
              <div className="card p-6 text-center">
                <div className="flex justify-center gap-1 mb-2">
                  <span className="w-2 h-2 rounded-full bg-[var(--color-primary)] animate-pulse" />
                  <span className="w-2 h-2 rounded-full bg-[var(--color-primary)] animate-pulse" style={{ animationDelay: '0.2s' }} />
                  <span className="w-2 h-2 rounded-full bg-[var(--color-primary)] animate-pulse" style={{ animationDelay: '0.4s' }} />
                </div>
                <p className="text-sm text-[var(--color-text-muted)]">Analyzing recording...</p>
              </div>
            )}
            {/* Results */}
            {analysisData && (
              <div className="card p-5">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-medium text-[var(--color-text-primary)]">AI Assessment</h2>
                  {streamSeverity && (
                    <span className={`trend-badge trend-${streamSeverity === 'high' ? 'rising' : streamSeverity === 'medium' ? 'rising' : 'stable'}`}>
                      {streamSeverity.toUpperCase()} RISK
                    </span>
                  )}
                </div>

                <div className="grid md:grid-cols-2 gap-3">
                  {riskEntries.map(([key, value]) => (
                    <div key={key} className="card p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium text-[var(--color-text-primary)] text-sm capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className="font-medium font-mono text-[var(--color-primary)]">{value}%</span>
                      </div>
                      <div className="w-full h-1 bg-[var(--color-surface-overlay)] rounded-full">
                        <div className="h-full bg-[var(--color-primary)] rounded-full transition-all" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
                      </div>
                      <p className="text-xs text-[var(--color-text-muted)] mt-2">Screening score</p>
                    </div>
                  ))}
                </div>

                {result?.key_insights?.length > 0 && (
                  <div className="mt-4 p-4 bg-[var(--color-surface-overlay)] rounded">
                    <h3 className="text-xs uppercase tracking-widest text-[var(--color-text-muted)] mb-2">Key Insights</h3>
                    <ul className="space-y-1 text-sm text-[var(--color-text-secondary)]">
                      {result.key_insights.map((insight, index) => (
                        <li key={index}>• {insight}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {result?.anomalies?.length > 0 && (
                  <div className="mt-4 p-4 bg-[var(--color-error)]/5 border border-[var(--color-error)]/20 rounded">
                    <h3 className="text-xs uppercase tracking-widest text-[var(--color-text-muted)] mb-2">Anomalies</h3>
                    <ul className="space-y-1 text-sm text-[var(--color-text-secondary)]">
                      {result.anomalies.map((item, index) => (
                        <li key={index}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {result?.suggestions?.length > 0 && (
                  <div className="mt-4 p-4 bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/20 rounded">
                    <h3 className="text-xs uppercase tracking-widest text-[var(--color-text-muted)] mb-2">Suggestions</h3>
                    <ul className="space-y-1 text-sm text-[var(--color-text-secondary)]">
                      {result.suggestions.map((item, index) => (
                        <li key={index}>• {item}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {streamExplanation && !result?.key_insights?.length && (
                  <p className="mt-3 text-sm text-[var(--color-text-muted)] leading-relaxed">{streamExplanation}</p>
                )}

                {/* Consistency Score */}
                {consistencyScore != null && (
                  <div className="mt-4 pt-4 border-t border-[var(--color-border)] flex justify-center">
                    <ConsistencyScore score={consistencyScore} />
                  </div>
                )}
              </div>
            )}

            {/* Socratic Interview */}
            {phase === 'interview' && questions.length > 0 && (
              <div className="card p-5">
                <SocraticChat
                  questions={questions}
                  onAnswer={handleSocraticAnswer}
                  currentRound={currentRound}
                  totalRounds={3}
                  isLoading={interviewLoading}
                />

                {/* Updated conditions during interview */}
                {updatedConditions.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
                    <p className="text-xs text-[var(--color-text-muted)] mb-2 uppercase tracking-widest">Refined Diagnosis</p>
                    {updatedConditions.map((c, i) => (
                      <div key={i} className="flex items-center justify-between py-1">
                        <span className="text-sm text-[var(--color-text-secondary)]">{c.name}</span>
                        <span className="text-sm font-mono text-[var(--color-primary)]">{c.confidence}%</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Nearby Clinic Card */}
            {clinic && (
              <div>
                <p className="text-xs uppercase tracking-widest text-[var(--color-text-muted)] mb-2">Nearby Specialist</p>
                <ClinicCard clinic={clinic} />
              </div>
            )}

            {/* Final Report CTA */}
            {phase === 'report' && result && (
              <div className="card p-5 border-[var(--color-primary)]/20">
                <h3 className="font-medium text-[var(--color-text-primary)] mb-2 flex items-center gap-2">
                  <FileTextIcon />
                  Analysis Complete
                </h3>
                <p className="text-sm text-[var(--color-text-muted)] mb-4">
                  Your full pre-consultation report is ready. Generate a PDF to share with your doctor.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={async () => {
                      const resp = await fetch('/report/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          audioUrl: '/demo.wav',
                          userId: user?.uid || 'demo',
                          userName: user?.displayName || 'Patient',
                          interviewRounds: interviewHistory,
                          originalFeatures: features || DEMO_FEATURES,
                          originalTranscript: transcript || DEMO_TRANSCRIPT,
                        }),
                      })
                      const data = await resp.json()
                      if (data.pdf_base64) {
                        const link = document.createElement('a')
                        link.href = `data:application/pdf;base64,${data.pdf_base64}`
                        link.download = 'vocal-vitals-report.pdf'
                        link.click()
                        showToast('Report downloaded', 'success')
                      }
                    }}
                    className="btn btn-primary px-4 py-2 text-sm flex items-center gap-2"
                  >
                    <FileTextIcon />
                    Download PDF Report
                  </button>
                  <button onClick={resetAll} className="btn btn-secondary px-4 py-2 text-sm">
                    New Analysis
                  </button>
                </div>
              </div>
            )}

            {/* Empty state */}
            {phase === 'idle' && !isStreaming && streamConditions.length === 0 && (
              <div className="card p-8 text-center">
                <ActivityIcon className="w-10 h-10 mx-auto mb-3 text-[var(--color-text-muted)] opacity-40" />
                <p className="text-[var(--color-text-muted)] text-sm">
                  Record your voice to begin AI-powered health screening.
                  <br />Results will appear here in real-time.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-center text-xs text-[var(--color-text-muted)] mt-8 flex items-center justify-center gap-1">
          <AlertTriangleIcon className="icon-sm" />
          Vocal Vitals is a screening tool, not a medical diagnostic device. Always consult a qualified healthcare professional.
        </p>
      </div>
    </div>
  )
}

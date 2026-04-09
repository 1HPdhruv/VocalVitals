import { useState, useRef, useEffect } from 'react'
import PropTypes from 'prop-types'
import { useAuth } from '../contexts/AuthContext'
import { db, storage } from '../firebase'
import { collection, addDoc, query, where, orderBy, getDocs, serverTimestamp, limit } from 'firebase/firestore'
import { ref, uploadBytes, getDownloadURL } from 'firebase/storage'
import ClinicCard from '../components/ClinicCard'
import { UsersIcon, CheckIcon, AlertTriangleIcon, MicrophoneIcon } from '../components/Icons'

const FLAG_DEFS = [
  { key: 'word_finding_pauses', label: 'Word-Finding Pauses', desc: 'Silent gaps > 2s mid-sentence' },
  { key: 'jitter_high',         label: "Parkinson's Tremor Risk", desc: 'Jitter > 1.04%' },
  { key: 'hnr_low',             label: 'Respiratory Distress',    desc: 'HNR < 10 dB' },
  { key: 'repetitions_detected',label: 'Phrase Repetition',        desc: 'Duplicate phrases detected' },
  { key: 'speech_rate_low',     label: 'Slow Speech Rate',         desc: '< 1.5 words/second' },
]

function ElderFlag({ flags }) {
  const activeFlags = FLAG_DEFS.filter(f => {
    const val = flags?.[f.key]
    return val === true || (typeof val === 'number' && val > 0)
  })

  if (activeFlags.length === 0) return (
    <div className="text-sm text-[var(--color-primary)] flex items-center gap-2">
      <CheckIcon className="icon-sm" /> No cognitive/physical decline flags detected
    </div>
  )

  return (
    <div className="space-y-2">
      {activeFlags.map(f => (
        <div key={f.key} className="flex items-start gap-2 text-sm">
          <AlertTriangleIcon className="icon-sm text-[var(--color-trend-rising)] mt-0.5 flex-shrink-0" />
          <div>
            <span className="text-[var(--color-text-primary)] font-medium">{f.label}</span>
            <span className="text-[var(--color-text-muted)] ml-1">— {f.desc}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

ElderFlag.propTypes = {
  flags: PropTypes.object,
}

export default function Caregiver() {
  const { user } = useAuth()
  const [patientName, setPatientName] = useState('')
  const [file, setFile]               = useState(null)
  const [phase, setPhase]             = useState('idle')
  const [result, setResult]           = useState(null)
  const [history, setHistory]         = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [geolocation, setGeolocation] = useState(null)
  const fileRef = useRef(null)

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        p => setGeolocation({ lat: p.coords.latitude, lon: p.coords.longitude }),
        () => {}
      )
    }
  }, [])

  const loadHistory = async (name) => {
    if (!name || !user) return
    setHistoryLoading(true)
    try {
      if (!db) { setHistoryLoading(false); return; }
      const q = query(
        collection(db, 'caregiverLinks'),
        where('caregiverId', '==', user.uid),
        where('patientName', '==', name),
        orderBy('timestamp', 'desc'),
        limit(10)
      )
      const snap = await getDocs(q)
      setHistory(snap.docs.map(d => ({ id: d.id, ...d.data() })))
    } catch { /* Query may fail if index not created */ }
    finally { setHistoryLoading(false) }
  }

  const handleSubmit = async () => {
    if (!file || !patientName.trim()) return
    setPhase('uploading')
    setResult(null)

    try {
      const path = `caregiver/${user?.uid}/${Date.now()}-${file.name}`
      if (!storage) return;
      const fileRef2 = ref(storage, path)
      await uploadBytes(fileRef2, file)
      const audioUrl = await getDownloadURL(fileRef2)

      setPhase('analyzing')
      const resp = await fetch('/caregiver/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audioUrl, patientName, caregiverId: user?.uid, ...geolocation }),
      })
      const data = await resp.json()
      setResult(data)
      setPhase('done')

      if (user && db) {
        await addDoc(collection(db, 'caregiverLinks'), {
          caregiverId:  user.uid,
          patientName:  patientName,
          timestamp:    serverTimestamp(),
          analysisId:   null,
          summary:      data.summary?.summary || '',
          severity:     data.summary?.severity,
          audioUrl,
        })
      }
    } catch {
      setPhase('error')
    }
  }

  const isHighSeverity = result?.summary?.severity === 'high'
  const severityClass = {
    high: 'trend-badge trend-rising',
    medium: 'trend-badge trend-rising',
    low: 'trend-badge trend-stable',
  }

  return (
    <div className="page-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-4xl mx-auto space-y-5">
        <div>
          <h1 className="text-2xl font-medium text-[var(--color-text-primary)] flex items-center gap-2">
            <UsersIcon />
            Elder Care Analysis
          </h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">AI-powered cognitive and physical decline detection for caregivers</p>
        </div>

        {/* High severity alert */}
        {isHighSeverity && (
          <div className="p-4 rounded card bg-[var(--color-error)]/10 border-[var(--color-error)]/50 flex items-start gap-3">
            <AlertTriangleIcon className="text-[var(--color-error)] flex-shrink-0" />
            <div>
              <p className="text-[var(--color-error)] font-medium">HIGH SEVERITY ALERT</p>
              <p className="text-sm text-[var(--color-error)]/80 mt-1">
                {result.summary?.recommended_action || 'Seek immediate medical evaluation.'}
              </p>
            </div>
          </div>
        )}

        <div className="grid lg:grid-cols-[1fr,1.5fr] gap-6">
          {/* Upload Form */}
          <div className="card p-5 space-y-4">
            <h2 className="font-medium text-[var(--color-text-primary)]">Submit Audio</h2>

            <div>
              <label className="text-xs text-[var(--color-text-muted)] uppercase tracking-widest block mb-1">Patient Name</label>
              <input
                type="text"
                value={patientName}
                onChange={e => { setPatientName(e.target.value); loadHistory(e.target.value) }}
                placeholder="Enter patient name"
                className="w-full bg-[var(--color-surface-overlay)] border border-[var(--color-border)] focus:border-[var(--color-primary)]/50 rounded px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none"
              />
            </div>

            <div>
              <label className="text-xs text-[var(--color-text-muted)] uppercase tracking-widest block mb-1">Audio File</label>
              <div
                onClick={() => fileRef.current?.click()}
                className="border-2 border-dashed border-[var(--color-border)] hover:border-[var(--color-primary)]/40 rounded p-6 text-center cursor-pointer transition-all"
              >
                <input ref={fileRef} type="file" accept="audio/*" className="hidden" onChange={e => setFile(e.target.files[0])} />
                {file ? (
                  <div>
                    <p className="text-sm text-[var(--color-text-primary)]">{file.name}</p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-1">{(file.size / 1024).toFixed(0)} KB</p>
                  </div>
                ) : (
                  <div>
                    <MicrophoneIcon className="w-8 h-8 mx-auto mb-2 text-[var(--color-text-muted)]" />
                    <p className="text-sm text-[var(--color-text-secondary)]">Click to upload audio</p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-1">WAV, MP3, WebM, M4A</p>
                  </div>
                )}
              </div>
            </div>

            <button
              onClick={handleSubmit}
              disabled={!file || !patientName.trim() || phase === 'uploading' || phase === 'analyzing'}
              className="w-full btn btn-primary py-3 disabled:opacity-40"
            >
              {phase === 'uploading' ? 'Uploading...' :
               phase === 'analyzing' ? 'Analyzing...' :
               'Analyze Recording'}
            </button>

            {phase === 'error' && (
              <p className="text-[var(--color-error)] text-sm flex items-center gap-2">
                <AlertTriangleIcon className="icon-sm" />
                Analysis failed. Please try again.
              </p>
            )}
          </div>

          {/* Results */}
          <div className="space-y-4">
            {phase === 'done' && result ? (
              <>
                {/* Summary */}
                <div className="card p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium text-[var(--color-text-primary)]">Analysis Summary</h3>
                    {result.summary?.severity && (
                      <span className={severityClass[result.summary.severity] || 'trend-badge trend-stable'}>
                        {result.summary.severity.toUpperCase()}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">{result.summary?.summary}</p>
                  {result.summary?.flags?.length > 0 && (
                    <ul className="mt-3 space-y-1">
                      {result.summary.flags.map((f, i) => (
                        <li key={i} className="text-xs text-[var(--color-trend-rising)] flex gap-1">
                          <AlertTriangleIcon className="icon-sm" />{f}
                        </li>
                      ))}
                    </ul>
                  )}
                  {result.summary?.recommended_action && (
                    <div className="mt-3 p-3 bg-[var(--color-primary)]/5 border border-[var(--color-primary)]/20 rounded">
                      <p className="text-xs text-[var(--color-primary)] font-medium">Recommended Action</p>
                      <p className="text-sm text-[var(--color-text-secondary)] mt-1">{result.summary.recommended_action}</p>
                    </div>
                  )}
                </div>

                {/* Elder Flags */}
                <div className="card p-5">
                  <h3 className="font-medium text-[var(--color-text-primary)] mb-3">Cognitive & Physical Flags</h3>
                  <ElderFlag flags={result.elder_care_flags} />
                </div>

                {/* Nearby Clinic */}
                {result.nearby_clinic && (
                  <div>
                    <p className="text-xs uppercase tracking-widest text-[var(--color-text-muted)] mb-2">Nearest Specialist</p>
                    <ClinicCard clinic={result.nearby_clinic} />
                  </div>
                )}
              </>
            ) : (
              /* Patient History */
              <div className="card p-5">
                <h3 className="font-medium text-[var(--color-text-primary)] mb-3">Patient History</h3>
                {historyLoading ? (
                  <div className="skeleton h-4 w-32" />
                ) : history.length === 0 ? (
                  <p className="text-[var(--color-text-muted)] text-sm">No prior submissions for this patient.</p>
                ) : (
                  <div className="space-y-3">
                    {history.map(h => (
                      <div key={h.id} className="card p-3">
                        <div className="flex items-center gap-2 mb-1">
                          {h.severity && <span className={severityClass[h.severity] || 'trend-badge trend-stable'}>{h.severity}</span>}
                          <span className="text-xs text-[var(--color-text-muted)] font-mono">
                            {h.timestamp?.toDate?.()?.toLocaleDateString() || 'Date unknown'}
                          </span>
                        </div>
                        <p className="text-xs text-[var(--color-text-secondary)] line-clamp-2">{h.summary}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

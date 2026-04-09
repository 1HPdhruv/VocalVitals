import { useState, useRef, useCallback, useEffect } from 'react'

const DEMO_FEATURES = {
  pitch_mean: 187.3, pitch_std: 24.1, jitter: 0.89, shimmer: 3.2,
  hnr: 11.4, speech_rate: 3.1, pause_freq: 4, breathiness: 0.42,
  duration: 15.0,
  mfcc: [-6.2, 112.3, -18.4, 8.1, -5.3, 2.7, -1.1, 0.9, -0.4, 1.2, 0.3, -0.8, 0.2],
}
const DEMO_TRANSCRIPT = "I have been feeling quite tired lately and my throat has been sore for about a week now. My voice feels strained when I speak for long periods."

export function useAudioRecorder({ userId, demoMode = false }) {
  const [isRecording, setIsRecording]   = useState(false)
  const [audioBlob, setAudioBlob]       = useState(null)
  const [audioUrl, setAudioUrl]         = useState(null)  // Firebase Storage URL
  const [localUrl, setLocalUrl]         = useState(null)  // Object URL for playback
  const [duration, setDuration]         = useState(0)
  const [error, setError]               = useState(null)
  const [uploading, setUploading]       = useState(false)
  const [analyserNode, setAnalyserNode] = useState(null)

  const mediaRef      = useRef(null)
  const streamRef     = useRef(null)
  const audioCtxRef   = useRef(null)
  const chunksRef     = useRef([])
  const timerRef      = useRef(null)
  const autoStopRef   = useRef(null)
  const startTimeRef  = useRef(null)
  const stopPromiseRef = useRef(null)
  const stopResolveRef = useRef(null)
  const stoppingRef   = useRef(false)

  useEffect(() => {
    return () => {
      clearInterval(timerRef.current)
      clearTimeout(autoStopRef.current)
      stoppingRef.current = false
      try { mediaRef.current?.stop?.() } catch {}
      try { streamRef.current?.getTracks?.().forEach(t => t.stop()) } catch {}
      try { audioCtxRef.current?.close?.() } catch {}
    }
  }, [])

  const startRecording = useCallback(async () => {
    setError(null)
    setAudioBlob(null)
    setAudioUrl(null)
    setLocalUrl(null)
    chunksRef.current = []
    stoppingRef.current = false

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
      streamRef.current = stream

      // Set up Web Audio API analyser
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      audioCtxRef.current = audioCtx
      const source   = audioCtx.createMediaStreamSource(stream)
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 2048
      source.connect(analyser)
      setAnalyserNode(analyser)

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const mr = new MediaRecorder(stream, { mimeType })
      mr.ondataavailable = e => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data)
        }
      }
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        setAudioBlob(blob)
        setLocalUrl(URL.createObjectURL(blob))
        stream.getTracks().forEach(t => t.stop())
        audioCtx.close()
        setAnalyserNode(null)
        clearInterval(timerRef.current)
        clearTimeout(autoStopRef.current)
        stoppingRef.current = false
        if (stopResolveRef.current) {
          stopResolveRef.current(blob)
          stopResolveRef.current = null
          stopPromiseRef.current = null
        }
      }

      mr.start(250) // collect every 250ms for stable chunks
      mediaRef.current = mr
      setIsRecording(true)
      startTimeRef.current = Date.now()
      timerRef.current = setInterval(() => {
        setDuration(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }, 1000)
      autoStopRef.current = setTimeout(() => {
        stopRecording()
      }, 30000)
    } catch (err) {
      setError(`Microphone access denied: ${err.message}`)
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (stoppingRef.current) return stopPromiseRef.current || Promise.resolve(null)
    stoppingRef.current = true
    clearTimeout(autoStopRef.current)

    const promise = new Promise((resolve) => {
      stopResolveRef.current = resolve
      if (!mediaRef.current || mediaRef.current.state === 'inactive') {
        resolve(null)
        stopResolveRef.current = null
        stopPromiseRef.current = null
        stoppingRef.current = false
        return
      }

      setIsRecording(false)
      mediaRef.current.stop()
    })

    stopPromiseRef.current = promise
    return promise
  }, [])

  const getDemoData = useCallback(() => ({
    features:   DEMO_FEATURES,
    transcript: DEMO_TRANSCRIPT,
    audioUrl:   '/demo.wav',
  }), [])

  return {
    isRecording, audioBlob, audioUrl, localUrl, duration, error, uploading, analyserNode,
    startRecording, stopRecording, getDemoData,
    DEMO_FEATURES, DEMO_TRANSCRIPT,
  }
}

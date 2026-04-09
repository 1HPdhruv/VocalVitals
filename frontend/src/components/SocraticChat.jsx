import React, { useState, useRef } from 'react'

/**
 * Socratic interview chat UI.
 * Claude questions on left with cyan avatar, patient answers on right.
 */
export default function SocraticChat({ questions, onAnswer, currentRound, totalRounds, isLoading }) {
  const [messages, setMessages] = useState([])
  const [inputText, setInputText]   = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const bottomRef = useRef(null)
  const mediaRef  = useRef(null)
  const chunksRef = useRef([])

  React.useEffect(() => {
    if (questions[currentRound] && (messages.length === 0 || messages[messages.length - 1]?.role !== 'claude')) {
      setMessages(prev => [
        ...prev,
        { role: 'claude', text: questions[currentRound], round: currentRound }
      ])
    }
  }, [currentRound, questions])

  React.useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const submitAnswer = (text) => {
    if (!text.trim()) return
    const updated = [...messages, { role: 'patient', text, round: currentRound }]
    setMessages(updated)
    setInputText('')
    onAnswer(text, currentRound)
  }

  const startVoiceRecord = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream)
      chunksRef.current = []
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        // Convert to text via simple playback — in production connect to Whisper endpoint
        // For now, prompt user to type after short recording preview
        stream.getTracks().forEach(t => t.stop())
        setIsRecording(false)
      }
      mr.start()
      mediaRef.current = mr
      setIsRecording(true)
    } catch {
      // Mic access may be denied
    }
  }

  const stopVoiceRecord = () => {
    mediaRef.current?.stop()
  }

  return (
    <div className="flex flex-col h-full">
      {/* Progress */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-xs text-gray-500 uppercase tracking-widest">Socratic Interview</span>
        <span className="text-xs font-mono text-cyan-DEFAULT">
          Round {Math.min(currentRound + 1, totalRounds)} / {totalRounds}
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1 bg-dark-600 rounded-full mb-4">
        <div
          className="h-full rounded-full bg-gradient-to-r from-cyan-600 to-cyan-DEFAULT transition-all duration-700"
          style={{ width: `${((currentRound) / totalRounds) * 100}%` }}
        />
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 mb-4 pr-1" style={{ maxHeight: 320 }}>
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-2 ${msg.role === 'patient' ? 'flex-row-reverse' : ''}`}>
            {/* Avatar */}
            <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-sm font-bold
              ${msg.role === 'claude'
                ? 'bg-cyan-400/20 border border-cyan-400/40 text-cyan-DEFAULT'
                : 'bg-dark-600 border border-dark-500 text-gray-400'
              }`}>
              {msg.role === 'claude' ? '◈' : '👤'}
            </div>
            {/* Bubble */}
            <div className={`max-w-xs lg:max-w-md p-3 text-sm
              ${msg.role === 'claude' ? 'chat-claude text-gray-200' : 'chat-patient text-gray-300'}`}>
              {msg.text}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-2">
            <div className="w-8 h-8 rounded-full bg-cyan-400/20 border border-cyan-400/40 flex items-center justify-center text-cyan-DEFAULT text-sm font-bold">◈</div>
            <div className="chat-claude p-3 flex gap-1 items-center">
              <span className="streaming-dot" />
              <span className="streaming-dot" />
              <span className="streaming-dot" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      {currentRound < totalRounds && !isLoading && (
        <div className="flex gap-2">
          <input
            type="text"
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && submitAnswer(inputText)}
            placeholder="Type your answer or use voice…"
            className="flex-1 bg-dark-700 border border-dark-500 focus:border-cyan-400/50 rounded-lg px-3 py-2 text-sm text-white outline-none transition-colors"
          />
          <button
            onClick={() => isRecording ? stopVoiceRecord() : startVoiceRecord()}
            className={`p-2 rounded-lg border transition-all ${isRecording
              ? 'bg-red-alert/10 border-red-alert/50 text-red-alert recording-pulse'
              : 'border-dark-500 text-gray-400 hover:border-cyan-400/50 hover:text-cyan-DEFAULT'}`}
          >
            🎙️
          </button>
          <button
            onClick={() => submitAnswer(inputText)}
            disabled={!inputText.trim()}
            className="btn-solid-cyan px-3 py-2 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
      )}

      {currentRound >= totalRounds && !isLoading && (
        <div className="text-center py-3 text-sm text-green-vital">
          ✓ Interview complete — generating final report…
        </div>
      )}
    </div>
  )
}

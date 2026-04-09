import React, { useEffect, useRef } from 'react'

/**
 * Real-time oscilloscope waveform visualizer using Web Audio API.
 * Draws cyan waveform on dark background with scan-line effect.
 */
export default function WaveformVisualizer({ analyserNode, isRecording, width = '100%', height = 140 }) {
  const canvasRef = useRef(null)
  const animRef   = useRef(null)
  const timeRef   = useRef(0)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const render = () => {
      timeRef.current += 1
      const W = canvas.width
      const H = canvas.height

      // Dark background
      ctx.fillStyle = 'rgba(8, 12, 16, 0.85)'
      ctx.fillRect(0, 0, W, H)

      // Draw grid
      ctx.strokeStyle = 'rgba(0, 255, 209, 0.06)'
      ctx.lineWidth = 1
      const gridX = 40
      const gridY = 35
      for (let x = 0; x <= W; x += gridX) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke()
      }
      for (let y = 0; y <= H; y += gridY) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke()
      }

      // Center line
      ctx.strokeStyle = 'rgba(0, 255, 209, 0.15)'
      ctx.lineWidth = 1
      ctx.beginPath(); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke()

      if (analyserNode && isRecording) {
        // Real waveform from microphone
        const bufferLength = analyserNode.frequencyBinCount
        const dataArray    = new Uint8Array(bufferLength)
        analyserNode.getByteTimeDomainData(dataArray)

        // Glow effect
        ctx.shadowBlur  = 12
        ctx.shadowColor = '#00FFD1'
        ctx.strokeStyle = '#00FFD1'
        ctx.lineWidth   = 2
        ctx.beginPath()

        const sliceWidth = W / bufferLength
        let x = 0
        for (let i = 0; i < bufferLength; i++) {
          const v = dataArray[i] / 128.0
          const y = (v * H) / 2
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
          x += sliceWidth
        }
        ctx.lineTo(W, H / 2)
        ctx.stroke()
        ctx.shadowBlur = 0
      } else {
        // Idle: draw a subtle sine wave animation
        ctx.shadowBlur  = 8
        ctx.shadowColor = 'rgba(0, 255, 209, 0.4)'
        ctx.strokeStyle = 'rgba(0, 255, 209, 0.35)'
        ctx.lineWidth   = 1.5
        ctx.beginPath()
        for (let x = 0; x <= W; x++) {
          const t = x / W
          const y = H / 2 + Math.sin(t * Math.PI * 6 + timeRef.current * 0.03) * (H * 0.08)
                         + Math.sin(t * Math.PI * 3 + timeRef.current * 0.02) * (H * 0.05)
          x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
        }
        ctx.stroke()
        ctx.shadowBlur = 0
      }

      // Horizontal scan-line overlay
      const scanY = ((timeRef.current * 1.5) % (H + 20)) - 10
      const grad = ctx.createLinearGradient(0, scanY - 2, 0, scanY + 2)
      grad.addColorStop(0, 'transparent')
      grad.addColorStop(0.5, 'rgba(0, 255, 209, 0.08)')
      grad.addColorStop(1, 'transparent')
      ctx.fillStyle = grad
      ctx.fillRect(0, scanY - 2, W, 4)

      animRef.current = requestAnimationFrame(render)
    }

    animRef.current = requestAnimationFrame(render)
    return () => cancelAnimationFrame(animRef.current)
  }, [analyserNode, isRecording])

  // Resize canvas to match container
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ro = new ResizeObserver(() => {
      canvas.width  = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    })
    ro.observe(canvas)
    return () => ro.disconnect()
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height }}
      className="waveform-canvas w-full"
    />
  )
}

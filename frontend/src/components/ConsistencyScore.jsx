import React from 'react'

/**
 * SVG circular progress indicator for 0-100 consistency score.
 */
export default function ConsistencyScore({ score = 0, size = 120 }) {
  const radius      = (size - 16) / 2
  const circumference = 2 * Math.PI * radius
  const progress    = Math.max(0, Math.min(100, Number(score) || 0))
  const percentage  = progress / 100
  const offset      = circumference * (1 - percentage)

  const color = progress >= 70
    ? '#00CC88'   // green — consistent
    : progress >= 40
    ? '#FFA500'   // amber — moderate
    : '#FF4444'   // red — inconsistent

  const label = progress >= 70 ? 'Consistent' : progress >= 40 ? 'Moderate' : 'Inconsistent'

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} className="circular-progress" style={{ filter: `drop-shadow(0 0 8px ${color}66)` }}>
        {/* Track */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={8}
        />
        {/* Progress */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: 'stroke-dashoffset 1s ease' }}
        />
      </svg>
      {/* Center score */}
      <div className="relative" style={{ marginTop: -(size / 2 + 24) }}>
        <div className="flex flex-col items-center justify-center" style={{ width: size, height: size }}>
          <span className="text-2xl font-bold font-mono" style={{ color }}>
            {progress}
          </span>
          <span className="text-xs text-gray-500">/ 100</span>
        </div>
      </div>
      <div className="text-xs font-medium mt-1" style={{ color }}>{label}</div>
      <div className="text-xs text-gray-500">Consistency Score</div>
    </div>
  )
}

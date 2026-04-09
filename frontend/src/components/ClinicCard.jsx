import React from 'react'

export default function ClinicCard({ clinic }) {
  if (!clinic) return null

  return (
    <div className="glass-card p-4 border-green-vital/20 bg-green-vital/5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-green-vital text-lg">🏥</span>
            <h3 className="font-semibold text-white truncate">{clinic.name}</h3>
          </div>
          <p className="text-sm text-gray-400 mb-1">{clinic.address}</p>
          <div className="flex items-center gap-1 text-xs text-gray-500 font-mono">
            <span>📍</span>
            <span>{clinic.distance_km} km away</span>
          </div>
        </div>
        <a
          href={clinic.maps_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0 px-3 py-2 rounded-lg text-sm font-medium text-green-vital border border-green-vital/30 hover:bg-green-vital/10 transition-all hover:shadow-green-glow"
        >
          Open in Maps →
        </a>
      </div>
    </div>
  )
}

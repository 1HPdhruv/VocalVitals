import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MicrophoneIcon, ChartIcon, PhoneIcon, UsersIcon, GitCompareIcon, FileTextIcon, ActivityIcon, WaveformIcon } from '../components/Icons'

const STEPS = [
  { Icon: MicrophoneIcon, title: 'Record Your Voice', desc: 'Speak naturally for 15-60 seconds into your browser microphone.' },
  { Icon: ActivityIcon, title: 'Acoustic Analysis', desc: 'Clinical-grade biomarkers extracted: jitter, shimmer, HNR, pitch, MFCC.' },
  { Icon: WaveformIcon, title: 'AI Reasoning', desc: 'AI cross-references your acoustic signature against known vocal health patterns.' },
  { Icon: FileTextIcon, title: 'Doctor-Ready Report', desc: 'Receive a structured pre-consultation note with specialist recommendation.' },
]

const FEATURES = [
  { Icon: ChartIcon, title: 'Longitudinal Journal', desc: 'Track 30-day voice trends with interactive graphs' },
  { Icon: PhoneIcon, title: 'Phone Screening', desc: 'Call our Twilio line and get SMS results in minutes' },
  { Icon: UsersIcon, title: 'Elder Care Mode', desc: 'Cognitive decline detection for caregivers' },
  { Icon: GitCompareIcon, title: 'Second Opinion', desc: 'Compare two recordings side-by-side with delta analysis' },
]

// Static waveform SVG - clean, no animation
function StaticWaveform() {
  return (
    <svg 
      className="w-full h-16 opacity-30" 
      viewBox="0 0 200 40" 
      preserveAspectRatio="none"
    >
      <path
        d="M0 20 Q10 10, 20 20 T40 20 T60 20 T80 20 T100 20 T120 20 T140 20 T160 20 T180 20 T200 20"
        fill="none"
        stroke="var(--color-primary)"
        strokeWidth="1.5"
      />
      <path
        d="M0 20 Q15 5, 30 20 T60 20 T90 20 T120 20 T150 20 T180 20"
        fill="none"
        stroke="var(--color-primary)"
        strokeWidth="1"
        opacity="0.5"
      />
    </svg>
  )
}

export default function Landing() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    setVisible(true)
  }, [])

  return (
    <div className="page-bg min-h-screen pt-14">
      {/* Hero Section */}
      <section className="relative">
        <div className="max-w-4xl mx-auto px-4 pt-20 pb-16 text-center">
          {/* Badge */}
          <div
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-sm border border-[var(--color-border)] bg-[var(--color-surface-elevated)] text-xs text-[var(--color-text-secondary)] font-medium mb-6 transition-opacity duration-500 ${visible ? 'opacity-100' : 'opacity-0'}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-primary)]" />
            AI-Powered Voice Health Screening
          </div>

          {/* Headline */}
          <h1
            className={`text-4xl md:text-5xl font-medium mb-6 transition-opacity duration-500 delay-100 ${visible ? 'opacity-100' : 'opacity-0'}`}
          >
            <span className="text-[var(--color-primary)]">Your Voice</span>
            <br />
            <span className="text-[var(--color-text-primary)]">Knows Your Health</span>
          </h1>

          <p
            className={`text-base text-[var(--color-text-secondary)] max-w-xl mx-auto mb-8 leading-relaxed transition-opacity duration-500 delay-200 ${visible ? 'opacity-100' : 'opacity-0'}`}
          >
            Clinical-grade acoustic biomarkers extracted from your voice. 
            Receive a doctor-ready pre-consultation report in minutes.
          </p>

          {/* CTA */}
          <div
            className={`flex flex-col sm:flex-row gap-3 justify-center items-center transition-opacity duration-500 delay-300 ${visible ? 'opacity-100' : 'opacity-0'}`}
          >
            <Link
              to="/screen"
              id="start-screening-cta"
              className="btn btn-primary px-6 py-3"
            >
              <MicrophoneIcon />
              <span>Start Screening</span>
            </Link>
            <a
              href="#how-it-works"
              className="btn btn-secondary px-6 py-3"
            >
              <span>How It Works</span>
            </a>
          </div>

          {/* Static waveform decoration */}
          <div className={`mt-12 max-w-lg mx-auto transition-opacity duration-500 delay-500 ${visible ? 'opacity-100' : 'opacity-0'}`}>
            <StaticWaveform />
          </div>
        </div>
      </section>

      {/* Stats Bar */}
      <section className="border-y border-[var(--color-border)] bg-[var(--color-surface-elevated)]">
        <div className="max-w-4xl mx-auto px-4 py-6 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
          {[
            { num: '13', label: 'Acoustic Biomarkers' },
            { num: '8',  label: 'Clinical Features' },
            { num: '3',  label: 'Interview Rounds' },
            { num: '<2m', label: 'Full Report' },
          ].map(({ num, label }) => (
            <div key={label}>
              <div className="text-2xl font-medium font-mono text-[var(--color-primary)]">{num}</div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">{label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="max-w-4xl mx-auto px-4 py-16">
        <div className="text-center mb-10">
          <h2 className="text-2xl font-medium text-[var(--color-text-primary)] mb-2">How It Works</h2>
          <p className="text-sm text-[var(--color-text-muted)]">Four steps from voice to clinical insight</p>
        </div>

        <div className="grid md:grid-cols-4 gap-4">
          {STEPS.map((step, i) => (
            <div key={i} className="relative card p-5">
              <div className="absolute -top-2 -left-2 w-6 h-6 rounded-sm bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center justify-center text-xs font-medium text-[var(--color-primary)] font-mono">
                {i + 1}
              </div>
              <step.Icon className="icon-lg text-[var(--color-primary)] mb-3" />
              <h3 className="font-medium text-[var(--color-text-primary)] mb-1 text-sm">{step.title}</h3>
              <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features Grid */}
      <section className="bg-[var(--color-surface-elevated)] py-16">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center mb-10">
            <h2 className="text-2xl font-medium text-[var(--color-text-primary)] mb-2">Everything You Need</h2>
            <p className="text-sm text-[var(--color-text-muted)]">A complete voice health platform</p>
          </div>
          <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-4">
            {FEATURES.map((f, i) => (
              <div key={i} className="card p-4 text-center">
                <f.Icon className="icon-lg text-[var(--color-primary)] mx-auto mb-3" />
                <h3 className="font-medium text-[var(--color-text-primary)] mb-1 text-sm">{f.title}</h3>
                <p className="text-xs text-[var(--color-text-muted)]">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Bottom */}
      <section className="max-w-2xl mx-auto px-4 py-16 text-center">
        <div className="card p-8">
          <h2 className="text-xl font-medium text-[var(--color-text-primary)] mb-2">Ready to Screen?</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-6">No app download. No hardware. Just your voice and a browser.</p>
          <Link
            to="/screen"
            className="btn btn-primary px-6 py-3"
          >
            <MicrophoneIcon />
            <span>Start Free Screening</span>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--color-border)] py-6 text-center text-xs text-[var(--color-text-muted)]">
        <p>Vocal Vitals - AI Voice Health Screening - Not a medical device</p>
        <p className="mt-1">Always consult a qualified healthcare professional for medical advice.</p>
      </footer>
    </div>
  )
}

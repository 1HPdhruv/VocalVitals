/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        cyan: {
          DEFAULT: '#00FFD1',
          400: '#00FFD1',
          500: '#00E6BC',
          600: '#00CCA8',
          glow: 'rgba(0, 255, 209, 0.15)',
        },
        dark: {
          900: '#080C10',
          800: '#0D1117',
          700: '#161B22',
          600: '#21262D',
          500: '#30363D',
        },
        green: {
          vital: '#00CC88',
          glow: 'rgba(0, 204, 136, 0.15)',
        },
        red: {
          alert: '#FF4444',
          glow: 'rgba(255, 68, 68, 0.15)',
        },
        amber: {
          warn: '#FFA500',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-cyan': 'pulse-cyan 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan-line': 'scan-line 3s linear infinite',
        'waveform': 'waveform 1.5s ease-in-out infinite alternate',
        'float': 'float 6s ease-in-out infinite',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'pulse-cyan': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.4 },
        },
        'scan-line': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100vw)' },
        },
        'waveform': {
          '0%': { transform: 'scaleY(0.3)' },
          '100%': { transform: 'scaleY(1)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(0, 255, 209, 0.3)' },
          '50%': { boxShadow: '0 0 40px rgba(0, 255, 209, 0.7)' },
        }
      },
      backgroundImage: {
        'grid-pattern': "linear-gradient(rgba(0,255,209,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,209,0.05) 1px, transparent 1px)",
        'oscilloscope-bg': 'radial-gradient(ellipse at center, #0D1117 0%, #080C10 100%)',
      },
      backgroundSize: {
        'grid': '40px 40px',
      },
      boxShadow: {
        'cyan-glow': '0 0 20px rgba(0, 255, 209, 0.4)',
        'cyan-glow-lg': '0 0 40px rgba(0, 255, 209, 0.6)',
        'green-glow': '0 0 20px rgba(0, 204, 136, 0.4)',
        'red-glow': '0 0 20px rgba(255, 68, 68, 0.4)',
        'inner-dark': 'inset 0 2px 20px rgba(0,0,0,0.5)',
      },
      dropShadow: {
        'cyan': '0 0 8px rgba(0, 255, 209, 0.8)',
      }
    },
  },
  plugins: [],
}

import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { ActivityIcon } from '../components/Icons'

export default function Login() {
  const { handleDemoLogin } = useAuth()
  const navigate = useNavigate()

  const onDemoClick = () => {
    handleDemoLogin()
    navigate('/screen')
  }

  return (
    <div className="page-bg min-h-screen pt-16 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-medium font-mono text-[var(--color-primary)]">Vocal Vitals</h1>
          <p className="text-[var(--color-text-muted)] text-sm mt-1">AI Voice Health Screening Platform</p>
        </div>

        <div className="card p-8 text-center space-y-6">
          <h2 className="text-xl text-[var(--color-text-primary)] font-medium">Welcome to Vocal Vitals</h2>
          <p className="text-[var(--color-text-secondary)] text-sm">
            Click below to enter Demo Mode and explore the voice analysis features.
          </p>

          <button
            onClick={onDemoClick}
            className="w-full btn btn-primary py-3 text-lg flex items-center justify-center gap-2"
          >
            <ActivityIcon />
            Enter Demo Mode
          </button>
        </div>

        <p className="text-center text-xs text-[var(--color-text-muted)] mt-4">
          <Link to="/" className="hover:text-[var(--color-primary)] transition-colors">Back to home</Link>
        </p>
      </div>
    </div>
  )
}

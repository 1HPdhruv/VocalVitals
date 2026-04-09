import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { 
  MicrophoneIcon, 
  ChartIcon, 
  PhoneIcon, 
  UsersIcon, 
  GitCompareIcon,
  LogOutIcon,
  LogInIcon,
  HomeIcon,
  ActivityIcon
} from './Icons'

const NAV_LINKS = [
  { to: '/screen',    label: 'Screen',    Icon: MicrophoneIcon },
  { to: '/journal',   label: 'Journal',   Icon: ChartIcon },
  { to: '/insights',  label: 'Insights',  Icon: ActivityIcon },
  { to: '/calls',     label: 'Calls',     Icon: PhoneIcon },
  { to: '/caregiver', label: 'Caregiver', Icon: UsersIcon },
  { to: '/compare',   label: 'Compare',   Icon: GitCompareIcon },
]

export default function Navbar() {
  const { user, logOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = async () => {
    await logOut()
    navigate('/')
  }

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-surface)]/95 backdrop-blur-sm">
      <div className="max-w-7xl mx-auto px-4 flex items-center justify-between h-14">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2">
          <HomeIcon className="icon text-[var(--color-primary)]" />
          <span className="text-base font-medium tracking-tight">
            <span className="text-[var(--color-primary)]">Vocal</span>
            <span className="text-[var(--color-text-primary)]">Vitals</span>
          </span>
        </Link>

        {/* Desktop Links */}
        {user && (
          <div className="hidden md:flex items-center gap-1">
            {NAV_LINKS.map(({ to, label, Icon }) => {
              const isActive = location.pathname.startsWith(to)
              return (
                <Link
                  key={to}
                  to={to}
                  className={`nav-link ${isActive ? 'active' : ''}`}
                >
                  <Icon />
                  <span>{label}</span>
                </Link>
              )
            })}
          </div>
        )}

        {/* Right side */}
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="hidden md:block text-xs text-[var(--color-text-muted)] font-mono">
                {user.email?.split('@')[0]}
              </span>
              <button
                onClick={handleLogout}
                className="btn btn-ghost flex items-center gap-2"
              >
                <LogOutIcon />
                <span className="hidden sm:inline">Sign Out</span>
              </button>
            </>
          ) : (
            <Link
              to="/login"
              className="btn btn-secondary flex items-center gap-2"
            >
              <LogInIcon />
              <span>Sign In</span>
            </Link>
          )}
          {/* Mobile menu toggle */}
          <button
            className="md:hidden p-2 text-[var(--color-text-secondary)]"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <svg className="icon-lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {menuOpen && user && (
        <div className="md:hidden bg-[var(--color-surface-elevated)] border-t border-[var(--color-border)] px-4 py-2">
          {NAV_LINKS.map(({ to, label, Icon }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setMenuOpen(false)}
              className="nav-link py-3"
            >
              <Icon />
              <span>{label}</span>
            </Link>
          ))}
        </div>
      )}
    </nav>
  )
}

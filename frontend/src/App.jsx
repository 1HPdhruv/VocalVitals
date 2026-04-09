import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Navbar from './components/Navbar'
import { Toast } from './components/Toast'
import Landing from './pages/Landing'
import Screen from './pages/Screen'
import Journal from './pages/Journal'
import Insights from './pages/Insights'
import Calls from './pages/Calls'
import TwilioLive from './pages/TwilioLive'
import Caregiver from './pages/Caregiver'
import Compare from './pages/Compare'
import Report from './pages/Report'
import Login from './pages/Login'

function ProtectedRoute({ children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return children
}

function AppRoutes() {
  return (
    <>
      <Navbar />
      <Toast />
      <Routes>
        <Route path="/"          element={<Landing />} />
        <Route path="/login"     element={<Login />} />
        <Route path="/screen"    element={<ProtectedRoute><Screen /></ProtectedRoute>} />
        <Route path="/journal"   element={<ProtectedRoute><Journal /></ProtectedRoute>} />
        <Route path="/insights"  element={<ProtectedRoute><Insights /></ProtectedRoute>} />
        <Route path="/calls"     element={<ProtectedRoute><Calls /></ProtectedRoute>} />
        <Route path="/live"      element={<TwilioLive />} />
        <Route path="/caregiver" element={<ProtectedRoute><Caregiver /></ProtectedRoute>} />
        <Route path="/compare"   element={<ProtectedRoute><Compare /></ProtectedRoute>} />
        <Route path="/report/:id" element={<ProtectedRoute><Report /></ProtectedRoute>} />
        <Route path="*"          element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}

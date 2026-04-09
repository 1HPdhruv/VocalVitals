import React, { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const savedUser = localStorage.getItem('demo_user')
    if (savedUser) {
      const parsedUser = JSON.parse(savedUser)
      setUser(parsedUser)
      setProfile(parsedUser)
    }
    setLoading(false)
  }, [])

  const handleDemoLogin = () => {
    const demoUser = {
      uid: 'demo-123',
      name: 'Anant Singh',
      email: 'demo@vocalvitals.com',
      role: 'Patient',
    }
    localStorage.setItem('demo_user', JSON.stringify(demoUser))
    setUser(demoUser)
    setProfile(demoUser)
  }

  const logOut = () => {
    localStorage.removeItem('demo_user')
    setUser(null)
    setProfile(null)
  }

  const isCaregiver = profile?.role?.toLowerCase() === 'caregiver'

  return (
    <AuthContext.Provider value={{ user, profile, loading, handleDemoLogin, logOut, isCaregiver }}>
      {!loading && children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

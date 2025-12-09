import { createContext, useContext, useState, useEffect } from 'react'
import PropTypes from 'prop-types'

const AuthContext = createContext(null)

/**
 * SECURITY NOTICE: PILOT/DEMO AUTHENTICATION ONLY
 *
 * This authentication implementation is NOT production-ready and contains
 * critical security vulnerabilities:
 * - Credentials stored in environment variables (visible in client bundle)
 * - No backend validation (client-side only)
 * - Session stored in localStorage (vulnerable to XSS)
 * - No session expiration or token refresh
 * - No rate limiting or CSRF protection
 *
 * ACCEPTABLE FOR: MOX pilot deployment with public manual PDFs
 * REQUIRED FOR PRODUCTION: Backend API authentication with JWT tokens,
 * HTTP-only cookies, rate limiting, and proper session management
 */
const VALID_CREDENTIALS = [
  {
    username: import.meta.env.VITE_USERNAME || 'pilot',
    password: import.meta.env.VITE_PASSWORD || 'change-me-in-production'
  }
]

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Check localStorage for existing session
    const session = localStorage.getItem('metextractor_auth')
    if (session) {
      setIsAuthenticated(true)
    }
    setIsLoading(false)
  }, [])

  const login = (username, password) => {
    const valid = VALID_CREDENTIALS.some(
      cred => cred.username === username && cred.password === password
    )

    if (valid) {
      localStorage.setItem('metextractor_auth', 'true')
      setIsAuthenticated(true)
      return true
    }
    return false
  }

  const logout = () => {
    localStorage.removeItem('metextractor_auth')
    setIsAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

AuthProvider.propTypes = {
  children: PropTypes.node.isRequired
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

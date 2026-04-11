import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [ready, setReady] = useState(false)
  const [authRequired, setAuthRequired] = useState(true)
  const [geofenceRequired, setGeofenceRequired] = useState(false)
  const [authenticated, setAuthenticated] = useState(false)
  const [user, setUser] = useState(null)

  const refresh = useCallback(async () => {
    const [cfg, me] = await Promise.all([
      axios.get(`${API_BASE_URL}/auth/config`),
      axios.get(`${API_BASE_URL}/auth/me`),
    ])
    if (cfg.data?.success) {
      setAuthRequired(!!cfg.data.auth_required)
      setGeofenceRequired(!!cfg.data.geofence_required)
    }
    if (me.data?.success && me.data.authenticated) {
      setAuthenticated(true)
      setUser(me.data.user || null)
    } else {
      setAuthenticated(false)
      setUser(null)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        await refresh()
      } catch {
        if (!cancelled) {
          setAuthRequired(true)
          setAuthenticated(false)
          setUser(null)
        }
      } finally {
        if (!cancelled) setReady(true)
      }
    })()
    return () => { cancelled = true }
  }, [refresh])

  const login = useCallback(async (username, password, coords) => {
    const body = { username, password }
    if (coords) {
      body.latitude = coords.latitude
      body.longitude = coords.longitude
    }
    const res = await axios.post(`${API_BASE_URL}/auth/login`, body)
    if (res.data?.success) {
      setAuthenticated(true)
      setUser(res.data.user || null)
    }
    return res.data
  }, [])

  const logout = useCallback(async () => {
    try {
      await axios.post(`${API_BASE_URL}/auth/logout`)
    } catch { /* ignore */ }
    setAuthenticated(false)
    setUser(null)
  }, [])

  const value = useMemo(
    () => ({
      ready,
      authRequired,
      geofenceRequired,
      authenticated,
      user,
      isAdmin: !authRequired || (user && user.role === 'admin'),
      refresh,
      login,
      logout,
    }),
    [ready, authRequired, geofenceRequired, authenticated, user, refresh, login, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

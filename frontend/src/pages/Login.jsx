import React, { useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { LogIn, MapPin, Loader } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

function readCoords() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('This browser does not support location.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude }),
      (err) => reject(new Error(err.message || 'Location permission denied')),
      { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
    )
  })
}

export default function Login() {
  const location = useLocation()
  const { ready, authRequired, geofenceRequired, authenticated, login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const from = location.state?.from?.pathname || '/'

  if (ready && (!authRequired || authenticated)) {
    return <Navigate to={from} replace />
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!username.trim() || !password) {
      setError('Enter username and password.')
      return
    }
    setBusy(true)
    try {
      let coords = null
      if (geofenceRequired) {
        coords = await readCoords()
      }
      const data = await login(username.trim(), password, coords)
      if (!data?.success) {
        setError(data?.error || 'Login failed')
      }
    } catch (err) {
      setError(err.response?.data?.error || err.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  if (!ready) {
    return (
      <div className="login-page">
        <div className="login-card">
          <Loader className="spin" size={28} />
          <p>Loading…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Sign in</h1>
        <p className="login-lead">Face Recognition Attendance</p>
        {geofenceRequired && (
          <div className="login-geofence-note" role="note">
            <MapPin size={16} />
            <span>
              Your location is checked at sign-in so the app can only be used on site.
              Allow location when the browser asks.
            </span>
          </div>
        )}
        <form onSubmit={onSubmit} className="login-form">
          <label>
            Username
            <input
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={busy}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
          </label>
          {error && <div className="error-banner login-error">{error}</div>}
          <button type="submit" className="btn btn-primary login-submit" disabled={busy}>
            {busy ? <Loader size={18} className="spin" /> : <LogIn size={18} />}
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}

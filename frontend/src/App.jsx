import React, { useEffect, useState } from 'react'
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Link,
  useLocation,
  Navigate,
  Outlet,
} from 'react-router-dom'
import Attendance from './pages/Attendance'
import AttendanceRecords from './pages/AttendanceRecords'
import UserManagement from './pages/UserManagement'
import TrainingCapture from './pages/TrainingCapture'
import ModelTraining from './pages/ModelTraining'
import Login from './pages/Login'
import { AuthProvider, useAuth } from './context/AuthContext'
import { isCameraAllowedByBrowser } from './utils/camera'
import './App.css'

function SecureContextBanner() {
  const [blocked, setBlocked] = useState(false)

  useEffect(() => {
    setBlocked(typeof window !== 'undefined' && !isCameraAllowedByBrowser())
  }, [])

  if (!blocked) return null

  return (
    <div className="secure-context-banner" role="alert">
      <strong>Webcam needs HTTPS or localhost.</strong>
      <span>
        {' '}
        Opening this app as <code>http://a-public-ip</code> blocks the camera in Chrome, Edge, and
        Safari.
      </span>
      <ul>
        <li>
          <strong>Fast test:</strong> from your PC run{' '}
          <code>ssh -L 8002:127.0.0.1:8002 root@YOUR_SERVER</code> then open{' '}
          <strong>http://localhost:8002</strong> (and rebuild UI with{' '}
          <code>VITE_API_URL=http://localhost:8002/api</code> if needed).
        </li>
        <li>
          <strong>Production:</strong> put HTTPS in front (nginx + Let&apos;s Encrypt) on port 443.
        </li>
      </ul>
    </div>
  )
}

function Navigation() {
  const location = useLocation()
  const { isAdmin, user, logout } = useAuth()

  const isActive = (path) => location.pathname === path

  return (
    <nav className="navigation">
      <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`}>
        <span>Attendance</span>
      </Link>
      {isAdmin && (
        <>
          <Link to="/users" className={`nav-link ${isActive('/users') ? 'active' : ''}`}>
            <span>Users</span>
          </Link>
          <Link to="/training" className={`nav-link ${isActive('/training') ? 'active' : ''}`}>
            <span>Training</span>
          </Link>
          <Link to="/train-model" className={`nav-link ${isActive('/train-model') ? 'active' : ''}`}>
            <span>Train Model</span>
          </Link>
        </>
      )}
      <Link to="/records" className={`nav-link ${isActive('/records') ? 'active' : ''}`}>
        <span>Records</span>
      </Link>
      <div className="nav-trailing">
        {user && (
          <span className="nav-user" title={user.role === 'admin' ? 'Administrator' : 'Staff'}>
            {user.username}
          </span>
        )}
        <button type="button" className="btn btn-secondary btn-sm nav-logout" onClick={() => logout()}>
          Log out
        </button>
      </div>
    </nav>
  )
}

function ProtectedLayout() {
  const location = useLocation()
  const { ready, authRequired, authenticated } = useAuth()

  if (!ready) {
    return (
      <div className="app app-loading">
        <p>Loading…</p>
      </div>
    )
  }

  if (authRequired && !authenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return (
    <div className="app">
      <header className="header">
        <h1>Face Recognition Attendance</h1>
        <SecureContextBanner />
      </header>
      <Navigation />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}

function RequireAdmin() {
  const { ready, authRequired, authenticated, isAdmin } = useAuth()
  if (!ready) {
    return (
      <div className="app app-loading">
        <p>Loading…</p>
      </div>
    )
  }
  if (authRequired && !authenticated) {
    return <Navigate to="/login" replace />
  }
  if (!isAdmin) {
    return <Navigate to="/" replace />
  }
  return <Outlet />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<Attendance />} />
        <Route path="/records" element={<AttendanceRecords />} />
        <Route element={<RequireAdmin />}>
          <Route path="/users" element={<UserManagement />} />
          <Route path="/training" element={<TrainingCapture />} />
          <Route path="/train-model" element={<ModelTraining />} />
        </Route>
      </Route>
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <Router basename={import.meta.env.BASE_URL}>
        <AppRoutes />
      </Router>
    </AuthProvider>
  )
}

export default App

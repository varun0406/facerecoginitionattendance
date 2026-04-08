import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import Attendance from './pages/Attendance'
import AttendanceRecords from './pages/AttendanceRecords'
import UserManagement from './pages/UserManagement'
import TrainingCapture from './pages/TrainingCapture'
import ModelTraining from './pages/ModelTraining'
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
  
  const isActive = (path) => location.pathname === path
  
  return (
    <nav className="navigation">
      <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`}>
        <span>Attendance</span>
      </Link>
      <Link to="/users" className={`nav-link ${isActive('/users') ? 'active' : ''}`}>
        <span>Users</span>
      </Link>
      <Link to="/training" className={`nav-link ${isActive('/training') ? 'active' : ''}`}>
        <span>Training</span>
      </Link>
      <Link to="/records" className={`nav-link ${isActive('/records') ? 'active' : ''}`}>
        <span>Records</span>
      </Link>
      <Link to="/train-model" className={`nav-link ${isActive('/train-model') ? 'active' : ''}`}>
        <span>Train Model</span>
      </Link>
    </nav>
  )
}

function App() {
  return (
    <Router basename={import.meta.env.BASE_URL}>
      <div className="app">
        <header className="header">
          <h1>Face Recognition Attendance</h1>
          <SecureContextBanner />
        </header>
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Attendance />} />
            <Route path="/users" element={<UserManagement />} />
            <Route path="/training" element={<TrainingCapture />} />
            <Route path="/records" element={<AttendanceRecords />} />
            <Route path="/train-model" element={<ModelTraining />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

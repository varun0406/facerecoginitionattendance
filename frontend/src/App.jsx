import React from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import Attendance from './pages/Attendance'
import UserManagement from './pages/UserManagement'
import TrainingCapture from './pages/TrainingCapture'
import ModelTraining from './pages/ModelTraining'
import './App.css'

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
      <Link to="/train-model" className={`nav-link ${isActive('/train-model') ? 'active' : ''}`}>
        <span>Train Model</span>
      </Link>
    </nav>
  )
}

function App() {
  return (
    <Router>
      <div className="app">
        <header className="header">
          <h1>Face Recognition Attendance</h1>
        </header>
        <Navigation />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Attendance />} />
            <Route path="/users" element={<UserManagement />} />
            <Route path="/training" element={<TrainingCapture />} />
            <Route path="/train-model" element={<ModelTraining />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App

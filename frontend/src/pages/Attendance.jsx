import React, { useState, useRef, useEffect } from 'react'
import { Camera, CheckCircle, XCircle, Loader, Wifi, WifiOff } from 'lucide-react'
import axios from 'axios'
import {
  requestCameraAccess,
  getCameraConstraints,
  bindStreamToVideoElement,
  waitForVideoDrawReady,
} from '../utils/camera'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'

function Attendance() {
  const [status, setStatus] = useState('idle')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [processingTime, setProcessingTime] = useState(0)
  const [isOnline, setIsOnline] = useState(true)
  const [pendingSync, setPendingSync] = useState(0)
  const [mediaStream, setMediaStream] = useState(null)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const timeoutRef = useRef(null)

  useEffect(() => {
    checkSystemStatus()
    const interval = setInterval(checkSystemStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const video = videoRef.current
    if (!mediaStream || !video) return
    bindStreamToVideoElement(video, mediaStream)
    return () => {
      if (video.srcObject === mediaStream) {
        video.srcObject = null
      }
    }
  }, [mediaStream, status])

  const checkSystemStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/status`)
      setIsOnline(response.data.database_connected)
      setPendingSync(response.data.pending_sync || 0)
    } catch (error) {
      setIsOnline(false)
    }
  }

  const startCamera = async () => {
    try {
      const result = await requestCameraAccess(getCameraConstraints())

      if (!result.success) {
        setError(result.error || 'Failed to access camera')
        setStatus('error')
        setMediaStream(null)
        return
      }

      streamRef.current = result.stream
      setMediaStream(result.stream)
    } catch (error) {
      setError('Camera access denied. Please allow camera permissions.')
      setStatus('error')
      setMediaStream(null)
    }
  }

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    setMediaStream(null)
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
  }

  const captureAndRecognize = async () => {
    if (!videoRef.current || !canvasRef.current) {
      setError('Camera not ready. Please start camera first.')
      return
    }

    const video = videoRef.current
    const canvas = canvasRef.current

    const drawReady = await waitForVideoDrawReady(video, 20000)
    if (!drawReady) {
      setError(
        'Video not ready. Please wait a moment and try again, or restart the camera.'
      )
      return
    }

    setStatus('capturing')
    setError(null)
    setResult(null)
    
    const ctx = canvas.getContext('2d')

    // Set canvas dimensions to match video
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    
    // Draw video frame to canvas
    try {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    } catch (error) {
      setError('Error drawing video to canvas: ' + error.message)
      setStatus('idle')
      return
    }

    // Convert to base64 with quality setting
    let imageData
    try {
      imageData = canvas.toDataURL('image/jpeg', 0.8)
      
      // Validate image data
      if (!imageData || imageData.length < 100) {
        setError('Failed to capture image. Please try again.')
        setStatus('idle')
        return
      }
    } catch (error) {
      setError('Error capturing image: ' + error.message)
      setStatus('idle')
      return
    }
    const startTime = Date.now()
    
    timeoutRef.current = setTimeout(() => {
      if (status === 'processing') {
        setError('Processing timeout. Please try again.')
        setStatus('error')
        stopCamera()
      }
    }, 20000)

    setStatus('processing')

    try {
      // Log image data size for debugging
      console.log('Image data length:', imageData.length)
      
      const response = await axios.post(`${API_BASE_URL}/recognize`, {
        image: imageData
      }, {
        timeout: 25000,
        headers: {
          'Content-Type': 'application/json'
        }
      })

      const elapsed = (Date.now() - startTime) / 1000
      setProcessingTime(elapsed)

      if (response.data.success) {
        const att = response.data.attendance
        setResult(response.data)
        if (att && att.success === false && att.day_complete) {
          setStatus('day-complete')
        } else if (att && att.success === false) {
          setStatus('error')
          setError(att.message || 'Could not save attendance')
        } else {
          setStatus('success')
          setTimeout(() => {
            resetState()
          }, 4000)
        }
      } else {
        setError(response.data.error || 'Recognition failed')
        setStatus('error')
      }
    } catch (error) {
      const elapsed = (Date.now() - startTime) / 1000
      setProcessingTime(elapsed)
      
      if (error.code === 'ECONNABORTED' || elapsed >= 20) {
        setError('Processing timeout. Please try again.')
      } else {
        setError(error.response?.data?.error || 'Network error. Please check connection.')
      }
      setStatus('error')
    } finally {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }

  const resetState = () => {
    setStatus('idle')
    setResult(null)
    setError(null)
    setProcessingTime(0)
  }

  const handleStart = async () => {
    setError(null)
    await startCamera()
  }

  const handleStop = () => {
    stopCamera()
    resetState()
  }

  return (
    <div className="attendance-page">
      <div className="status-indicators">
        <div className={`status-indicator ${isOnline ? 'online' : 'offline'}`}>
          {isOnline ? <Wifi size={18} /> : <WifiOff size={18} />}
          <span>{isOnline ? 'Online' : 'Offline'}</span>
        </div>
        {pendingSync > 0 && (
          <div className="sync-indicator">
            <span>{pendingSync} pending sync</span>
          </div>
        )}
      </div>

      {status === 'idle' && !mediaStream && (
        <div className="start-screen">
          <Camera size={64} className="camera-icon" />
          <h2>Clock in / Clock out</h2>
          <p>
            First scan today records <strong>start time</strong>; second scan records <strong>stop time</strong>.
            The face must match a registered person (training ID = user ID).
          </p>
          <button className="btn btn-primary" onClick={handleStart}>
            Start Camera
          </button>
        </div>
      )}

      {(status === 'idle' || status === 'capturing' || status === 'processing') &&
        mediaStream && (
        <div className="camera-container">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="video-preview"
          />
          <canvas ref={canvasRef} style={{ display: 'none' }} />
          
          {status === 'idle' && (
            <div className="camera-controls">
              <button className="btn btn-capture" onClick={captureAndRecognize}>
                <Camera size={24} />
                Capture & Recognize
              </button>
              <button className="btn btn-secondary" onClick={handleStop}>
                Stop Camera
              </button>
            </div>
          )}

          {status === 'processing' && (
            <div className="processing-overlay">
              <Loader className="spinner" size={48} />
              <p>Processing... (Max 20 seconds)</p>
              {processingTime > 0 && (
                <p className="time-indicator">{processingTime.toFixed(1)}s</p>
              )}
            </div>
          )}
        </div>
      )}

      {status === 'day-complete' && result && (
        <div className="result-screen info">
          <CheckCircle size={64} className="success-icon" />
          <h2>Recognized — day already complete</h2>
          <p className="info-message">
            Face matches <strong>{result.recognition.name}</strong> (ID {result.recognition.user_id}).
            Start and stop are already recorded for today.
          </p>
          <div className="result-details">
            <div className="detail-item">
              <span className="label">Start time:</span>
              <span className="value">{result.attendance.start_time || '—'}</span>
            </div>
            <div className="detail-item">
              <span className="label">Stop time:</span>
              <span className="value">{result.attendance.stop_time || '—'}</span>
            </div>
            <div className="detail-item">
              <span className="label">Date:</span>
              <span className="value">{result.attendance.date}</span>
            </div>
          </div>
          <div className="button-group">
            <button className="btn btn-primary" onClick={resetState}>OK</button>
          </div>
        </div>
      )}

      {status === 'success' && result && result.attendance?.success !== false && (
        <div className="result-screen success">
          <CheckCircle size={64} className="success-icon" />
          <h2>
            {result.attendance.punch_type === 'clock_out' ? 'Clock-out recorded!' : 'Clock-in recorded!'}
          </h2>
          <div className="result-details">
            <div className="detail-item">
              <span className="label">Name:</span>
              <span className="value">{result.recognition.name}</span>
            </div>
            <div className="detail-item">
              <span className="label">ID:</span>
              <span className="value">{result.recognition.user_id}</span>
            </div>
            {result.recognition.department && (
              <div className="detail-item">
                <span className="label">Department:</span>
                <span className="value">{result.recognition.department}</span>
              </div>
            )}
            <div className="detail-item">
              <span className="label">Start time:</span>
              <span className="value">{result.attendance.start_time || '—'}</span>
            </div>
            <div className="detail-item">
              <span className="label">Stop time:</span>
              <span className="value">{result.attendance.stop_time ?? '—'}</span>
            </div>
            <div className="detail-item">
              <span className="label">Date:</span>
              <span className="value">{result.attendance.date}</span>
            </div>
            {!result.attendance.synced && (
              <div className="sync-warning">
                <WifiOff size={16} />
                <span>Queued for sync when online</span>
              </div>
            )}
          </div>
          <p className="success-message">{result.attendance.message}</p>
        </div>
      )}

      {status === 'error' && (
        <div className="result-screen error">
          <XCircle size={64} className="error-icon" />
          <h2>Recognition Failed</h2>
          <p className="error-message">{error}</p>
          {processingTime > 0 && (
            <p className="time-indicator">Processing time: {processingTime.toFixed(1)}s</p>
          )}
          <div className="button-group">
            <button className="btn btn-primary" onClick={resetState}>
              Try Again
            </button>
            <button className="btn btn-secondary" onClick={handleStop}>
              Stop Camera
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Attendance


import React, { useState, useRef, useEffect } from 'react'
import { Camera, CheckCircle, XCircle, Loader, User } from 'lucide-react'
import axios from 'axios'
import {
  requestCameraAccess,
  getCameraConstraints,
  bindStreamToVideoElement,
  waitForVideoDrawReady,
} from '../utils/camera'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'

function TrainingCapture() {
  const [selectedUserId, setSelectedUserId] = useState('')
  const [vendors, setVendors] = useState([])
  const [imageCount, setImageCount] = useState(0)
  const [minRequired, setMinRequired] = useState(18)
  const [recommended, setRecommended] = useState(30)
  const [maxImages, setMaxImages] = useState(120)
  const [status, setStatus] = useState('idle')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [mediaStream, setMediaStream] = useState(null)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => {
    loadVendors()
  }, [])

  useEffect(() => {
    if (selectedUserId) {
      loadImageCount()
    }
  }, [selectedUserId])

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

  const loadVendors = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/vendors`)
      if (response.data.success) {
        setVendors(response.data.vendors)
      }
    } catch (error) {
      console.error('Error loading vendors:', error)
    }
  }

  const loadImageCount = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/training/count/${selectedUserId}`)
      if (response.data.success) {
        setImageCount(response.data.image_count)
        if (response.data.min_required != null) {
          setMinRequired(response.data.min_required)
        }
        if (response.data.recommended != null) {
          setRecommended(response.data.recommended)
        }
        if (response.data.max_images != null) {
          setMaxImages(response.data.max_images)
        }
      }
    } catch (error) {
      console.error('Error loading image count:', error)
    }
  }

  const startCamera = async () => {
    if (!selectedUserId) {
      setError('Please select a user first')
      return
    }

    setStatus('loading')
    setError('')

    try {
      // Use camera utility for cross-platform compatibility
      const result = await requestCameraAccess(getCameraConstraints())
      
      if (!result.success) {
        setError(result.error || 'Failed to access camera')
        setStatus('error')
        setMediaStream(null)
        return
      }
      
      const stream = result.stream
      streamRef.current = stream
      setMediaStream(stream)

      setStatus('ready')
      setError('')
    } catch (error) {
      console.error('Camera error:', error)
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
    setStatus('idle')
  }

  const captureImage = async () => {
    if (!videoRef.current || !canvasRef.current || !selectedUserId) {
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
    setError('')
    setMessage('')
    
    const ctx = canvas.getContext('2d')

    // Set canvas dimensions to match video
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    
    // Draw video frame to canvas
    try {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    } catch (error) {
      setError('Error drawing video to canvas: ' + error.message)
      setStatus('ready')
      return
    }

    // Convert to base64 with quality setting
    let imageData
    try {
      imageData = canvas.toDataURL('image/jpeg', 0.8)
      
      // Validate image data
      if (!imageData || imageData.length < 100) {
        setError('Failed to capture image. Please try again.')
        setStatus('ready')
        return
      }
    } catch (error) {
      setError('Error capturing image: ' + error.message)
      setStatus('ready')
      return
    }

    try {
      const response = await axios.post(`${API_BASE_URL}/training/capture`, {
        user_id: parseInt(selectedUserId),
        image: imageData
      })

      if (response.data.success) {
        setMessage(response.data.message)
        setStatus('success')
        loadImageCount()
        setTimeout(() => {
          setStatus('ready')
          setMessage('')
        }, 2000)
      } else {
        setError(response.data.error || 'Failed to save image')
        setStatus('ready')
      }
    } catch (error) {
      setError(error.response?.data?.error || 'Error capturing image')
      setStatus('ready')
    }
  }

  const selectedUser = vendors.find(v => v.vendor_id.toString() === selectedUserId)

  return (
    <div className="training-capture-page">
      <h2>Capture Training Images</h2>
      <p className="page-description">
        Samples are rejected unless the server sees one clear, sharp face with decent lighting.
        Capture many angles and distances — the server enforces a minimum before training is allowed.
      </p>

      <div className="training-checklist">
        <strong>Quality checklist (enforced by API)</strong>
        <ul>
          <li>Exactly <strong>one</strong> person visible (no crowd behind you).</li>
          <li>Face large enough on screen; avoid blur and extreme dark/backlight.</li>
          <li>Match <strong>vendor ID</strong> to the person (same ID used at attendance).</li>
          <li>After enough images, use <strong>Train model</strong> — training will refuse if anyone is short.</li>
        </ul>
      </div>

      <div className="user-selector">
        <label>Select User:</label>
        <select
          value={selectedUserId}
          onChange={(e) => {
            setSelectedUserId(e.target.value)
            stopCamera()
          }}
          disabled={status !== 'idle'}
        >
          <option value="">-- Select User --</option>
          {vendors.map((vendor) => (
            <option key={vendor.vendor_id} value={vendor.vendor_id}>
              {vendor.vendor_id} - {vendor.name}
            </option>
          ))}
        </select>
        {selectedUser && (
          <div className="user-info user-info-stack">
            <div className="user-info-row">
              <User size={20} />
              <span>{selectedUser.name} — {selectedUser.department || 'No department'}</span>
            </div>
            <div className="training-progress-meta">
              <span className="image-count">
                Saved: {imageCount} / {minRequired} minimum ({recommended} recommended, max {maxImages})
              </span>
            </div>
            <div className="training-progress-bar" aria-hidden="true">
              <div
                className={`training-progress-fill ${imageCount >= minRequired ? 'complete' : ''}`}
                style={{
                  width: `${Math.min(100, (imageCount / Math.max(minRequired, 1)) * 100)}%`,
                }}
              />
            </div>
          </div>
        )}
      </div>

      {selectedUserId && (
        <div className="camera-section">
          {status === 'idle' && (
            <button className="btn btn-primary" onClick={startCamera}>
              <Camera size={20} />
              Start Camera
            </button>
          )}

          {status === 'loading' && (
            <div className="camera-container">
              <div className="processing-overlay">
                <Loader className="spinner" size={48} />
                <p>Starting camera...</p>
                <p className="hint" style={{ fontSize: '0.875rem', marginTop: '0.5rem' }}>Please wait while the camera initializes</p>
              </div>
            </div>
          )}

          {(status === 'ready' || status === 'capturing' || status === 'success') && (
            <div className="camera-container">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="video-preview"
              />
              <canvas ref={canvasRef} style={{ display: 'none' }} />
              
              {status === 'ready' && (
                <div className="camera-controls">
                  <button className="btn btn-capture" onClick={captureImage}>
                    <Camera size={24} />
                    Capture Image
                  </button>
                  <button className="btn btn-secondary" onClick={stopCamera}>
                    Stop Camera
                  </button>
                </div>
              )}

              {status === 'capturing' && (
                <div className="processing-overlay">
                  <Loader className="spinner" size={48} />
                  <p>Saving image...</p>
                </div>
              )}

              {status === 'success' && (
                <div className="success-overlay">
                  <CheckCircle size={48} className="success-icon" />
                  <p>{message}</p>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="error-message">
              <XCircle size={20} />
              <span>{error}</span>
            </div>
          )}

          {message && status !== 'success' && (
            <div className="info-message">
              <CheckCircle size={20} />
              <span>{message}</span>
            </div>
          )}
        </div>
      )}

      {!selectedUserId && (
        <div className="empty-state">
          <User size={64} />
          <p>Please select a user to start capturing training images.</p>
          <p className="hint">Make sure you've added users in the User Management page first.</p>
        </div>
      )}
    </div>
  )
}

export default TrainingCapture


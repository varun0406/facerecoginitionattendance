import React, { useState, useEffect, useCallback } from 'react'
import { Play, CheckCircle, XCircle, Loader, AlertCircle, RefreshCw } from 'lucide-react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

function ModelTraining() {
  const [training, setTraining] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [readiness, setReadiness] = useState(null)
  const [loadingReadiness, setLoadingReadiness] = useState(true)

  const loadReadiness = useCallback(async () => {
    setLoadingReadiness(true)
    try {
      const response = await axios.get(`${API_BASE_URL}/training/readiness`)
      if (response.data?.success) {
        setReadiness(response.data)
      } else {
        setReadiness({
          users: [],
          can_train: false,
          messages: [response.data?.error || 'Unexpected readiness response'],
        })
      }
    } catch (e) {
      console.error(e)
      setReadiness({
        users: [],
        can_train: false,
        messages: [
          'Could not reach the API. Build the frontend with VITE_API_URL pointing at this server, or open the app from the same host as Flask.',
        ],
      })
    } finally {
      setLoadingReadiness(false)
    }
  }, [])

  useEffect(() => {
    loadReadiness()
  }, [loadReadiness])

  const handleTrain = async () => {
    await loadReadiness()
    const fresh = await axios.get(`${API_BASE_URL}/training/readiness`).catch(() => null)
    if (fresh?.data && fresh.data.can_train === false) {
      setReadiness(fresh.data)
      setError(
        fresh.data.messages?.join(' ') ||
          'Training requirements not met. See the checklist below.',
      )
      return
    }

    if (!confirm('Train the LBPH model from all saved face images? This replaces classifier.xml.')) {
      return
    }

    setTraining(true)
    setResult(null)
    setError('')

    try {
      const response = await axios.post(`${API_BASE_URL}/training/train`)

      if (response.data.success) {
        setResult(response.data)
        loadReadiness()
      } else {
        setError(response.data.error || 'Training failed')
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Error training model')
    } finally {
      setTraining(false)
    }
  }

  const canTrain = readiness?.can_train === true && !loadingReadiness

  return (
    <div className="model-training-page">
      <h2>Train Face Recognition Model</h2>
      <p className="page-description">
        Training only runs when every user who has photos on disk meets the minimum image count and
        every <code>vendor_id</code> matches a user in the database. Capture uses blur, lighting, and
        single-face checks so the model is safer for production.
      </p>

      <div className="training-section">
        <div className="training-info">
          <AlertCircle size={24} />
          <div>
            <h3>Before training</h3>
            <ul>
              <li>Add each person under <strong>Users</strong> first (their ID must match training).</li>
              <li>Capture <strong>at least the minimum</strong> images per person (see table).</li>
              <li>Vary angle, distance, and lighting; avoid hats/glare; one face in frame.</li>
              <li>After training, test on <strong>Attendance</strong> with the same lighting you expect on the VM.</li>
            </ul>
          </div>
        </div>

        <div className="readiness-toolbar">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={loadReadiness}
            disabled={loadingReadiness}
          >
            <RefreshCw size={18} className={loadingReadiness ? 'spinner' : ''} />
            Refresh status
          </button>
        </div>

        {readiness?.messages?.length > 0 && (
          <div className="readiness-messages" style={{ marginBottom: '1rem' }}>
            {readiness.messages.map((m, i) => (
              <p key={i} className="hint error-text">
                {m}
              </p>
            ))}
          </div>
        )}

        {readiness?.users?.length > 0 && (
          <div className="readiness-table-wrap">
            <table className="readiness-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Name</th>
                  <th>Images</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {readiness.users.map((u) => (
                  <tr key={u.vendor_id}>
                    <td>{u.vendor_id}</td>
                    <td>{u.name}</td>
                    <td>
                      {u.image_count} / {u.min_required}
                      {u.image_count >= u.recommended ? ' (recommended met)' : ''}
                    </td>
                    <td>
                      {u.ready ? (
                        <span className="text-ok">Ready</span>
                      ) : u.image_count === 0 ? (
                        <span className="text-warn">No images</span>
                      ) : (
                        <span className="text-warn">Need {u.short_by} more</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <button
          className="btn btn-primary btn-large"
          onClick={handleTrain}
          disabled={training || !canTrain}
          title={
            !canTrain
              ? 'Meet minimum images for every user that has training data, and fix any messages above.'
              : ''
          }
        >
          {training ? (
            <>
              <Loader className="spinner" size={20} />
              Training model…
            </>
          ) : (
            <>
              <Play size={20} />
              Train model
            </>
          )}
        </button>

        {!canTrain && !loadingReadiness && readiness && (
          <p className="hint" style={{ marginTop: '1rem' }}>
            Train button stays disabled until the server reports <code>can_train: true</code> (strict
            checks). Add images on the Training page, then refresh status.
          </p>
        )}

        {result && (
          <div className="result-card success">
            <CheckCircle size={48} className="success-icon" />
            <h3>Training successful</h3>
            <div className="result-details">
              <div className="detail-item">
                <span className="label">Total images:</span>
                <span className="value">{result.total_images}</span>
              </div>
              <div className="detail-item">
                <span className="label">Users in model:</span>
                <span className="value">{result.unique_users}</span>
              </div>
              <div className="detail-item">
                <span className="label">Model file:</span>
                <span className="value">{result.classifier_path}</span>
              </div>
            </div>
            <p className="success-message">{result.message}</p>
            <p className="hint">Open <strong>Attendance</strong> and run a live recognition test.</p>
          </div>
        )}

        {error && (
          <div className="result-card error">
            <XCircle size={48} className="error-icon" />
            <h3>Cannot train</h3>
            <p className="error-message">{error}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default ModelTraining

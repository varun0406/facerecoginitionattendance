import React, { useState, useEffect, useCallback } from 'react'
import { Users, UserPlus, Trash2, Shield, User } from 'lucide-react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'

export default function StaffAccounts() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [meId, setMeId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [uRes, meRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/auth/users`),
        axios.get(`${API_BASE_URL}/auth/me`),
      ])
      if (uRes.data.success) setUsers(uRes.data.users || [])
      if (meRes.data?.success && meRes.data?.user?.id != null) {
        setMeId(meRes.data.user.id)
      }
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const createStaff = async (e) => {
    e.preventDefault()
    setMsg('')
    setError('')
    setSaving(true)
    try {
      const res = await axios.post(`${API_BASE_URL}/auth/users`, { username, password })
      if (res.data.success) {
        setMsg(res.data.message || 'Staff created')
        setUsername('')
        setPassword('')
        load()
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Create failed')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!window.confirm('Remove this login? They will no longer be able to sign in.')) return
    setError('')
    try {
      await axios.delete(`${API_BASE_URL}/auth/users/${id}`)
      setMsg('User removed')
      load()
    } catch (err) {
      setError(err.response?.data?.error || 'Delete failed')
    }
  }

  return (
    <div className="staff-accounts-page">
      <div className="page-header">
        <h2>Staff accounts</h2>
        <p className="page-description">
          Create logins for staff. They can mark attendance and view records; only administrators can edit or delete attendance rows.
        </p>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {msg && <div className="info-message login-info-banner">{msg}</div>}

      <div className="form-container staff-create-form">
        <h3>Add staff</h3>
        <form onSubmit={createStaff} className="user-form">
          <div className="form-row">
            <div className="form-group">
              <label>Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                minLength={2}
                autoComplete="off"
              />
            </div>
            <div className="form-group">
              <label>Password (min 8 characters)</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <UserPlus size={18} /> {saving ? 'Creating…' : 'Create staff account'}
          </button>
        </form>
      </div>

      <div className="users-list">
        <h3>Accounts ({users.length})</h3>
        {loading ? (
          <div className="loading-state">Loading…</div>
        ) : users.length === 0 ? (
          <div className="empty-state">
            <Users size={48} />
            <p>No web logins yet.</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table className="att-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td className="name-cell">{u.username}</td>
                    <td>
                      {u.role === 'admin' ? (
                        <span className="badge badge-auto"><Shield size={12} /> Admin</span>
                      ) : (
                        <span className="badge badge-face"><User size={12} /> Staff</span>
                      )}
                    </td>
                    <td className="time-cell">{u.created_at || '—'}</td>
                    <td>
                      {u.id !== meId && (
                        <button
                          type="button"
                          className="btn-icon danger"
                          title="Remove login"
                          onClick={() => remove(u.id)}
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                      {u.id === meId && (
                        <span className="text-muted">You</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

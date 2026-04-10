import React, { useState, useEffect, useCallback } from 'react'
import {
  Clock, Users, Calendar, Download, RefreshCw, Filter,
  Pencil, Trash2, Check, X, ChevronDown,
} from 'lucide-react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'
const PAGE_SIZE = 100

// ── helpers ────────────────────────────────────────────────────────────────

function todayISO() {
  const n = new Date()
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`
}

function isoToDDMM(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function durationBadgeClass(minutes) {
  if (minutes == null) return 'badge-pending'
  if (minutes < 60) return 'badge-short'
  if (minutes < 240) return 'badge-medium'
  return 'badge-full'
}

function checkoutBadge(type) {
  if (!type || type === 'face') return <span className="badge badge-face">Face</span>
  if (type === 'manual') return <span className="badge badge-manual">Manual</span>
  if (type === 'auto') return <span className="badge badge-auto">Auto</span>
  return <span className="badge badge-face">{type}</span>
}

function downloadCSV(records) {
  const header = ['Date', 'ID', 'Name', 'Dept', 'Clock-in', 'Clock-out', 'Duration', 'Type', 'Status']
  const rows = records.map(r => [
    r.date, r.user_id, r.name, r.department || '',
    r.start_time || '', r.end_time || '', r.duration || '',
    r.checkout_type || 'face', r.status || 'Present',
  ])
  const csv = [header, ...rows]
    .map(row => row.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `attendance_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── inline-edit row ────────────────────────────────────────────────────────

function EditRow({ record, onSave, onCancel }) {
  const [start, setStart] = useState(record.start_time || '')
  const [end, setEnd] = useState(record.end_time || '')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState('')

  const save = async () => {
    if (!start) { setErr('Clock-in time required'); return }
    setSaving(true)
    setErr('')
    try {
      await axios.put(`${API_BASE_URL}/attendance/${record.id}`, {
        start_time: start,
        end_time: end || null,
      })
      onSave()
    } catch (e) {
      setErr(e.response?.data?.error || 'Save failed')
      setSaving(false)
    }
  }

  return (
    <tr className="row-edit">
      <td>{record.date}</td>
      <td>
        <span className="name-cell">{record.name}</span>
        <span className="id-badge">#{record.user_id}</span>
      </td>
      <td>{record.department || '—'}</td>
      <td>
        <input
          type="time" step="1" className="time-input"
          value={start} onChange={e => setStart(e.target.value)}
        />
      </td>
      <td>
        <input
          type="time" step="1" className="time-input"
          value={end} onChange={e => setEnd(e.target.value)}
        />
      </td>
      <td>—</td>
      <td>
        <span className="badge badge-manual">editing</span>
      </td>
      <td>
        <div className="row-actions">
          <button className="btn-icon success" title="Save" onClick={save} disabled={saving}>
            <Check size={15} />
          </button>
          <button className="btn-icon" title="Cancel" onClick={onCancel} disabled={saving}>
            <X size={15} />
          </button>
          {err && <span className="field-error">{err}</span>}
        </div>
      </td>
    </tr>
  )
}

// ── main component ─────────────────────────────────────────────────────────

export default function AttendanceRecords() {
  const [tab, setTab] = useState('records')

  const [records, setRecords] = useState([])
  const [summary, setSummary] = useState([])
  const [limit, setLimit] = useState(PAGE_SIZE)

  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [editingId, setEditingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  const buildParams = useCallback((extraLimit) => {
    const p = { limit: extraLimit || limit }
    if (dateFrom) p.date_from = isoToDDMM(dateFrom)
    if (dateTo) p.date_to = isoToDDMM(dateTo)
    return p
  }, [dateFrom, dateTo, limit])

  const fetchRecords = useCallback(async (overrideLimit) => {
    setLoading(true); setError(null)
    try {
      const res = await axios.get(`${API_BASE_URL}/attendance`, { params: buildParams(overrideLimit) })
      if (res.data.success) setRecords(res.data.records || [])
      else setError('Failed to load records')
    } catch (e) {
      setError(e.response?.data?.error || 'Network error')
    } finally { setLoading(false) }
  }, [buildParams])

  const fetchSummary = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await axios.get(`${API_BASE_URL}/attendance/summary`, { params: buildParams(500) })
      if (res.data.success) setSummary(res.data.summary || [])
      else setError('Failed to load summary')
    } catch (e) {
      setError(e.response?.data?.error || 'Network error')
    } finally { setLoading(false) }
  }, [buildParams])

  useEffect(() => {
    if (tab === 'records') fetchRecords()
    else fetchSummary()
  }, [tab, dateFrom, dateTo, limit, fetchRecords, fetchSummary])

  const deleteRecord = async (id) => {
    setDeletingId(id)
    try {
      await axios.delete(`${API_BASE_URL}/attendance/${id}`)
      setRecords(prev => prev.filter(r => r.id !== id))
    } catch (e) {
      setError('Delete failed: ' + (e.response?.data?.error || e.message))
    } finally { setDeletingId(null) }
  }

  const loadMore = () => {
    const next = limit + PAGE_SIZE
    setLimit(next)
  }

  const totalHours = records.reduce((s, r) => s + (r.duration_minutes || 0), 0)
  const completeCount = records.filter(r => r.end_time).length
  const pendingCount = records.filter(r => !r.end_time).length

  const today = todayISO()

  return (
    <div className="records-page">
      <div className="records-header">
        <h2>Attendance Records</h2>

        <div className="records-controls">
          <div className="date-range-filter">
            <Filter size={15} />
            <label>From</label>
            <input type="date" className="date-input" value={dateFrom} max={today}
              onChange={e => setDateFrom(e.target.value)} />
            <label>To</label>
            <input type="date" className="date-input" value={dateTo} max={today}
              onChange={e => setDateTo(e.target.value)} />
            {(dateFrom || dateTo) && (
              <button className="btn-icon" title="Clear" onClick={() => { setDateFrom(''); setDateTo('') }}>
                <X size={14} />
              </button>
            )}
          </div>

          <button className="btn btn-secondary btn-sm"
            onClick={() => tab === 'records' ? fetchRecords() : fetchSummary()}
            disabled={loading}>
            <RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh
          </button>

          {tab === 'records' && records.length > 0 && (
            <button className="btn btn-secondary btn-sm" onClick={() => downloadCSV(records)}>
              <Download size={15} /> CSV
            </button>
          )}
        </div>
      </div>

      <div className="tab-bar">
        <button className={`tab ${tab === 'records' ? 'active' : ''}`} onClick={() => setTab('records')}>
          <Calendar size={15} /> Records
        </button>
        <button className={`tab ${tab === 'summary' ? 'active' : ''}`} onClick={() => setTab('summary')}>
          <Users size={15} /> Per-Person Summary
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {tab === 'records' && (
        <>
          <div className="stats-row">
            <div className="stat-card">
              <Clock size={20} />
              <div>
                <div className="stat-value">{records.length}</div>
                <div className="stat-label">Total entries</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-dot complete" />
              <div>
                <div className="stat-value">{completeCount}</div>
                <div className="stat-label">Complete</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-dot pending" />
              <div>
                <div className="stat-value">{pendingCount}</div>
                <div className="stat-label">In progress</div>
              </div>
            </div>
            <div className="stat-card">
              <Clock size={20} />
              <div>
                <div className="stat-value">{Math.floor(totalHours / 60)}h {totalHours % 60}m</div>
                <div className="stat-label">Total tracked</div>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="loading-state">Loading…</div>
          ) : records.length === 0 ? (
            <div className="empty-state">
              <Calendar size={48} />
              <p>No attendance records{(dateFrom || dateTo) ? ' for selected range' : ''}.</p>
            </div>
          ) : (
            <>
              <div className="table-wrapper">
                <table className="att-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Name</th>
                      <th>Dept</th>
                      <th>Clock-in</th>
                      <th>Clock-out</th>
                      <th>Duration</th>
                      <th>Type</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {records.map(r =>
                      editingId === r.id ? (
                        <EditRow
                          key={r.id}
                          record={r}
                          onSave={() => { setEditingId(null); fetchRecords() }}
                          onCancel={() => setEditingId(null)}
                        />
                      ) : (
                        <tr key={r.id} className={r.end_time ? '' : 'row-open'}>
                          <td>{r.date}</td>
                          <td>
                            <span className="name-cell">{r.name}</span>
                            <span className="id-badge">#{r.user_id}</span>
                          </td>
                          <td>{r.department || '—'}</td>
                          <td className="time-cell">{r.start_time || '—'}</td>
                          <td className="time-cell">
                            {r.end_time || <span className="text-muted">pending</span>}
                          </td>
                          <td>
                            {r.duration
                              ? <span className={`duration-badge ${durationBadgeClass(r.duration_minutes)}`}>{r.duration}</span>
                              : <span className="text-muted">—</span>}
                          </td>
                          <td>{checkoutBadge(r.checkout_type)}</td>
                          <td>
                            <div className="row-actions">
                              <button className="btn-icon" title="Edit" onClick={() => setEditingId(r.id)}>
                                <Pencil size={14} />
                              </button>
                              <button
                                className="btn-icon danger" title="Delete"
                                disabled={deletingId === r.id}
                                onClick={() => deleteRecord(r.id)}>
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>

              <div className="load-more-row">
                <span className="record-count">{records.length} record{records.length !== 1 ? 's' : ''} shown</span>
                {records.length >= limit && (
                  <button className="btn btn-secondary btn-sm" onClick={loadMore} disabled={loading}>
                    <ChevronDown size={15} /> Load more
                  </button>
                )}
              </div>
            </>
          )}
        </>
      )}

      {tab === 'summary' && (
        <>
          {loading ? (
            <div className="loading-state">Loading…</div>
          ) : summary.length === 0 ? (
            <div className="empty-state">
              <Users size={48} />
              <p>No summary data{(dateFrom || dateTo) ? ' for selected range' : ''}.</p>
            </div>
          ) : (
            <div className="table-wrapper">
              <table className="att-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Department</th>
                    <th>Days present</th>
                    <th>Days complete</th>
                    <th>Total time</th>
                    <th>Avg / day</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.map(s => {
                    const avgMin = s.days_complete > 0 ? Math.round(s.total_minutes / s.days_complete) : null
                    const avgStr = avgMin != null ? `${Math.floor(avgMin / 60)}h ${avgMin % 60}m` : '—'
                    return (
                      <tr key={s.user_id}>
                        <td>#{s.user_id}</td>
                        <td className="name-cell">{s.name}</td>
                        <td>{s.department || '—'}</td>
                        <td className="center">{s.days_present}</td>
                        <td className="center">{s.days_complete}</td>
                        <td>
                          {s.total_duration
                            ? <span className={`duration-badge ${durationBadgeClass(s.total_minutes)}`}>{s.total_duration}</span>
                            : <span className="text-muted">—</span>}
                        </td>
                        <td className="time-cell">{avgStr}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}

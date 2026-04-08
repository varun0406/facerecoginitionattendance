import React, { useState, useEffect, useCallback } from 'react'
import { Clock, Users, Calendar, Download, RefreshCw, Filter } from 'lucide-react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'

function durationBadgeClass(minutes) {
  if (minutes == null) return 'badge-pending'
  if (minutes < 60) return 'badge-short'
  if (minutes < 240) return 'badge-medium'
  return 'badge-full'
}

function todayISO() {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function isoToDDMM(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function downloadCSV(records) {
  const header = ['Date', 'User ID', 'Name', 'Department', 'Clock-in', 'Clock-out', 'Duration', 'Status']
  const rows = records.map((r) => [
    r.date,
    r.user_id,
    r.name,
    r.department || '',
    r.start_time || '',
    r.end_time || '',
    r.duration || '',
    r.status || 'Present',
  ])
  const csv = [header, ...rows].map((row) => row.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `attendance_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function AttendanceRecords() {
  const [tab, setTab] = useState('records')
  const [records, setRecords] = useState([])
  const [summary, setSummary] = useState([])
  const [filterDate, setFilterDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchRecords = useCallback(async (dateFilter) => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 200 }
      if (dateFilter) params.date = isoToDDMM(dateFilter)
      const res = await axios.get(`${API_BASE_URL}/attendance`, { params })
      if (res.data.success) {
        setRecords(res.data.records || [])
      } else {
        setError('Failed to load records')
      }
    } catch (e) {
      setError(e.response?.data?.error || 'Network error')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchSummary = useCallback(async (dateFilter) => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 500 }
      if (dateFilter) params.date = isoToDDMM(dateFilter)
      const res = await axios.get(`${API_BASE_URL}/attendance/summary`, { params })
      if (res.data.success) {
        setSummary(res.data.summary || [])
      } else {
        setError('Failed to load summary')
      }
    } catch (e) {
      setError(e.response?.data?.error || 'Network error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (tab === 'records') fetchRecords(filterDate)
    else fetchSummary(filterDate)
  }, [tab, filterDate, fetchRecords, fetchSummary])

  const totalHours = records.reduce((s, r) => s + (r.duration_minutes || 0), 0)
  const completeCount = records.filter((r) => r.end_time).length
  const pendingCount = records.filter((r) => !r.end_time).length

  return (
    <div className="records-page">
      <div className="records-header">
        <h2>Attendance Records</h2>

        <div className="records-controls">
          <div className="date-filter">
            <Filter size={16} />
            <input
              type="date"
              value={filterDate}
              onChange={(e) => setFilterDate(e.target.value)}
              className="date-input"
              max={todayISO()}
            />
            {filterDate && (
              <button className="btn-icon" title="Clear filter" onClick={() => setFilterDate('')}>
                ×
              </button>
            )}
          </div>

          <button
            className="btn btn-secondary btn-sm"
            onClick={() => (tab === 'records' ? fetchRecords(filterDate) : fetchSummary(filterDate))}
            disabled={loading}
          >
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            Refresh
          </button>

          {tab === 'records' && records.length > 0 && (
            <button className="btn btn-secondary btn-sm" onClick={() => downloadCSV(records)}>
              <Download size={15} />
              CSV
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
                <div className="stat-label">Complete (in+out)</div>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-dot pending" />
              <div>
                <div className="stat-value">{pendingCount}</div>
                <div className="stat-label">Clocked in only</div>
              </div>
            </div>
            <div className="stat-card">
              <Clock size={20} />
              <div>
                <div className="stat-value">
                  {Math.floor(totalHours / 60)}h {totalHours % 60}m
                </div>
                <div className="stat-label">Total hours tracked</div>
              </div>
            </div>
          </div>

          {loading ? (
            <div className="loading-state">Loading…</div>
          ) : records.length === 0 ? (
            <div className="empty-state">
              <Calendar size={48} />
              <p>No attendance records{filterDate ? ` for ${isoToDDMM(filterDate)}` : ''}.</p>
            </div>
          ) : (
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
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <tr key={r.id} className={r.end_time ? '' : 'row-open'}>
                      <td>{r.date}</td>
                      <td>
                        <span className="name-cell">{r.name}</span>
                        <span className="id-badge">#{r.user_id}</span>
                      </td>
                      <td>{r.department || '—'}</td>
                      <td className="time-cell">{r.start_time || '—'}</td>
                      <td className="time-cell">{r.end_time || <span className="text-muted">pending</span>}</td>
                      <td>
                        {r.duration ? (
                          <span className={`duration-badge ${durationBadgeClass(r.duration_minutes)}`}>
                            {r.duration}
                          </span>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>
                      <td>
                        <span className={`status-badge ${r.end_time ? 'status-complete' : 'status-open'}`}>
                          {r.end_time ? 'Complete' : 'In progress'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
              <p>No summary data{filterDate ? ` for ${isoToDDMM(filterDate)}` : ''}.</p>
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
                  {summary.map((s) => {
                    const avgMin =
                      s.days_complete > 0 ? Math.round(s.total_minutes / s.days_complete) : null
                    const avgStr =
                      avgMin != null
                        ? `${Math.floor(avgMin / 60)}h ${avgMin % 60}m`
                        : '—'
                    return (
                      <tr key={s.user_id}>
                        <td>#{s.user_id}</td>
                        <td className="name-cell">{s.name}</td>
                        <td>{s.department || '—'}</td>
                        <td className="center">{s.days_present}</td>
                        <td className="center">{s.days_complete}</td>
                        <td>
                          {s.total_duration ? (
                            <span className={`duration-badge ${durationBadgeClass(s.total_minutes)}`}>
                              {s.total_duration}
                            </span>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
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

import React, { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, User, AlertTriangle, X, CheckCircle } from 'lucide-react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'

const EMPTY_FORM = {
  vendor_id: '', name: '', department: '', purpose: '',
  visited_by: '', visit_type: '', dob: '', gender: '',
  number: '', vendor_company: '', address: '', photo: 'NO',
}

function Toast({ message, type, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 3500)
    return () => clearTimeout(t)
  }, [onClose])
  return (
    <div className={`toast toast-${type}`}>
      {type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
      <span>{message}</span>
      <button className="toast-close" onClick={onClose}><X size={14} /></button>
    </div>
  )
}

function DeleteModal({ vendor, deleteInfo, onConfirm, onCancel, deleting }) {
  return (
    <div className="modal-overlay">
      <div className="modal-box">
        <div className="modal-icon danger"><AlertTriangle size={28} /></div>
        <h3>Delete {vendor.name}?</h3>
        <p className="modal-desc">This will permanently delete:</p>
        <ul className="modal-list">
          <li><strong>{deleteInfo.training_images}</strong> training image{deleteInfo.training_images !== 1 ? 's' : ''}</li>
          <li><strong>{deleteInfo.attendance_records}</strong> attendance record{deleteInfo.attendance_records !== 1 ? 's' : ''}</li>
          <li>The user account (ID #{vendor.vendor_id})</li>
        </ul>
        <p className="modal-warn">This action cannot be undone.</p>
        <div className="modal-actions">
          <button className="btn btn-danger" onClick={onConfirm} disabled={deleting}>
            {deleting ? 'Deleting…' : 'Yes, delete'}
          </button>
          <button className="btn btn-secondary" onClick={onCancel} disabled={deleting}>Cancel</button>
        </div>
      </div>
    </div>
  )
}

function UserManagement() {
  const [vendors, setVendors] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editingVendor, setEditingVendor] = useState(null)
  const [formData, setFormData] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [loadingVendors, setLoadingVendors] = useState(false)

  // Delete modal state
  const [deleteTarget, setDeleteTarget] = useState(null)   // vendor object
  const [deleteInfo, setDeleteInfo] = useState(null)        // {training_images, attendance_records}
  const [loadingDeleteInfo, setLoadingDeleteInfo] = useState(false)
  const [deleting, setDeleting] = useState(false)

  // Toast
  const [toast, setToast] = useState(null)

  const showToast = (message, type = 'success') => setToast({ message, type })

  useEffect(() => { loadVendors() }, [])

  const loadVendors = async () => {
    setLoadingVendors(true)
    try {
      const res = await axios.get(`${API_BASE_URL}/vendors`)
      if (res.data.success) setVendors(res.data.vendors)
      else showToast('Failed to load users', 'error')
    } catch {
      showToast('Network error loading users', 'error')
    } finally {
      setLoadingVendors(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = { ...formData, vendor_id: Number(formData.vendor_id) }
      if (editingVendor) {
        await axios.put(`${API_BASE_URL}/vendors/${editingVendor}`, payload)
        showToast('User updated successfully')
      } else {
        await axios.post(`${API_BASE_URL}/vendors`, payload)
        showToast('User added successfully')
      }
      loadVendors()
      resetForm()
    } catch (err) {
      showToast('Error saving user: ' + (err.response?.data?.error || err.message), 'error')
    } finally {
      setSaving(false)
    }
  }

  const openDeleteModal = async (vendor) => {
    setDeleteTarget(vendor)
    setLoadingDeleteInfo(true)
    try {
      const res = await axios.get(`${API_BASE_URL}/vendors/${vendor.vendor_id}/delete-info`)
      setDeleteInfo(res.data)
    } catch {
      setDeleteInfo({ training_images: '?', attendance_records: '?' })
    } finally {
      setLoadingDeleteInfo(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      const res = await axios.delete(`${API_BASE_URL}/vendors/${deleteTarget.vendor_id}`)
      showToast(
        `Deleted ${deleteTarget.name} — ${res.data.training_images_deleted} images, ` +
        `${res.data.attendance_records_deleted} records removed`
      )
      loadVendors()
    } catch (err) {
      showToast('Delete failed: ' + (err.response?.data?.error || err.message), 'error')
    } finally {
      setDeleting(false)
      setDeleteTarget(null)
      setDeleteInfo(null)
    }
  }

  const handleEdit = (vendor) => {
    setEditingVendor(vendor.vendor_id)
    setFormData({
      vendor_id: vendor.vendor_id,
      name: vendor.name || '',
      department: vendor.department || '',
      purpose: vendor.purpose || '',
      visited_by: vendor.visited_by || '',
      visit_type: vendor.visit_type || '',
      dob: vendor.dob || '',
      gender: vendor.gender || '',
      number: vendor.number || '',
      vendor_company: vendor.vendor_company || '',
      address: vendor.address || '',
      photo: vendor.photo || 'NO',
    })
    setShowForm(true)
  }

  const resetForm = () => {
    setFormData(EMPTY_FORM)
    setEditingVendor(null)
    setShowForm(false)
  }

  const field = (key, val) => setFormData(f => ({ ...f, [key]: val }))

  return (
    <div className="user-management-page">
      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />
      )}

      {deleteTarget && !loadingDeleteInfo && deleteInfo && (
        <DeleteModal
          vendor={deleteTarget}
          deleteInfo={deleteInfo}
          onConfirm={confirmDelete}
          onCancel={() => { setDeleteTarget(null); setDeleteInfo(null) }}
          deleting={deleting}
        />
      )}

      <div className="page-header">
        <h2>User Management</h2>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus size={20} /> Add User
        </button>
      </div>

      {showForm && (
        <div className="form-container">
          <h3>{editingVendor ? 'Edit User' : 'Add New User'}</h3>
          <form onSubmit={handleSubmit} className="user-form">
            <div className="form-row">
              <div className="form-group">
                <label>User ID *</label>
                <input type="number" value={formData.vendor_id}
                  onChange={e => field('vendor_id', e.target.value)}
                  required disabled={!!editingVendor} min="1" />
              </div>
              <div className="form-group">
                <label>Name *</label>
                <input type="text" value={formData.name}
                  onChange={e => field('name', e.target.value)} required />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Department</label>
                <select value={formData.department} onChange={e => field('department', e.target.value)}>
                  <option value="">Select Department</option>
                  <option value="HR">HR</option>
                  <option value="IT">IT</option>
                  <option value="CSR">CSR</option>
                  <option value="OT">OT</option>
                  <option value="Accounts">Accounts</option>
                  <option value="Operations">Operations</option>
                  <option value="Sales">Sales</option>
                </select>
              </div>
              <div className="form-group">
                <label>Gender</label>
                <select value={formData.gender} onChange={e => field('gender', e.target.value)}>
                  <option value="">Select</option>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Contact Number</label>
                <input type="text" value={formData.number}
                  onChange={e => field('number', e.target.value)} />
              </div>
              <div className="form-group">
                <label>Date of Birth</label>
                <input type="text" placeholder="DD-MM-YYYY" value={formData.dob}
                  onChange={e => field('dob', e.target.value)} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Company</label>
                <input type="text" value={formData.vendor_company}
                  onChange={e => field('vendor_company', e.target.value)} />
              </div>
              <div className="form-group">
                <label>Purpose</label>
                <input type="text" value={formData.purpose}
                  onChange={e => field('purpose', e.target.value)} />
              </div>
            </div>

            <div className="form-group">
              <label>Address</label>
              <textarea value={formData.address}
                onChange={e => field('address', e.target.value)} rows="2" />
            </div>

            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Saving…' : (editingVendor ? 'Update' : 'Save') + ' User'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="users-list">
        <h3>Users ({vendors.length})</h3>
        {loadingVendors ? (
          <div className="loading-state">Loading users…</div>
        ) : vendors.length === 0 ? (
          <div className="empty-state">
            <User size={48} />
            <p>No users found. Add your first user above.</p>
          </div>
        ) : (
          <div className="users-grid">
            {vendors.map((vendor) => (
              <div key={vendor.vendor_id} className="user-card">
                <div className="user-card-header">
                  <User size={24} />
                  <h4>{vendor.name}</h4>
                </div>
                <div className="user-card-body">
                  <p><strong>ID:</strong> {vendor.vendor_id}</p>
                  {vendor.department && <p><strong>Dept:</strong> {vendor.department}</p>}
                  {vendor.number && <p><strong>Contact:</strong> {vendor.number}</p>}
                  {vendor.gender && <p><strong>Gender:</strong> {vendor.gender}</p>}
                </div>
                <div className="user-card-actions">
                  <button className="btn-icon" title="Edit" onClick={() => handleEdit(vendor)}>
                    <Edit size={18} />
                  </button>
                  <button className="btn-icon danger" title="Delete"
                    onClick={() => openDeleteModal(vendor)}>
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default UserManagement

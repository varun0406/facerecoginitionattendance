import React, { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, User } from 'lucide-react'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002/api'

function UserManagement() {
  const [vendors, setVendors] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [editingVendor, setEditingVendor] = useState(null)
  const [formData, setFormData] = useState({
    vendor_id: '',
    name: '',
    department: '',
    purpose: '',
    visited_by: '',
    visit_type: '',
    dob: '',
    gender: '',
    number: '',
    vendor_company: '',
    address: '',
    photo: 'NO'
  })

  useEffect(() => {
    loadVendors()
  }, [])

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

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      if (editingVendor) {
        await axios.put(`${API_BASE_URL}/vendors/${editingVendor}`, formData)
      } else {
        await axios.post(`${API_BASE_URL}/vendors`, formData)
      }
      loadVendors()
      resetForm()
      alert('User saved successfully!')
    } catch (error) {
      alert('Error saving user: ' + (error.response?.data?.error || error.message))
    }
  }

  const handleDelete = async (vendorId) => {
    if (!confirm('Are you sure you want to delete this user?')) return
    
    try {
      await axios.delete(`${API_BASE_URL}/vendors/${vendorId}`)
      loadVendors()
      alert('User deleted successfully!')
    } catch (error) {
      alert('Error deleting user: ' + (error.response?.data?.error || error.message))
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
      photo: vendor.photo || 'NO'
    })
    setShowForm(true)
  }

  const resetForm = () => {
    setFormData({
      vendor_id: '',
      name: '',
      department: '',
      purpose: '',
      visited_by: '',
      visit_type: '',
      dob: '',
      gender: '',
      number: '',
      vendor_company: '',
      address: '',
      photo: 'NO'
    })
    setEditingVendor(null)
    setShowForm(false)
  }

  return (
    <div className="user-management-page">
      <div className="page-header">
        <h2>User Management</h2>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowForm(true) }}>
          <Plus size={20} />
          Add User
        </button>
      </div>

      {showForm && (
        <div className="form-container">
          <h3>{editingVendor ? 'Edit User' : 'Add New User'}</h3>
          <form onSubmit={handleSubmit} className="user-form">
            <div className="form-row">
              <div className="form-group">
                <label>User ID *</label>
                <input
                  type="number"
                  value={formData.vendor_id}
                  onChange={(e) => setFormData({...formData, vendor_id: e.target.value})}
                  required
                  disabled={!!editingVendor}
                />
              </div>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({...formData, name: e.target.value})}
                  required
                />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Department</label>
                <select
                  value={formData.department}
                  onChange={(e) => setFormData({...formData, department: e.target.value})}
                >
                  <option value="">Select Department</option>
                  <option value="HR">HR</option>
                  <option value="IT">IT</option>
                  <option value="CSR">CSR</option>
                  <option value="OT">OT</option>
                </select>
              </div>
              <div className="form-group">
                <label>Gender</label>
                <select
                  value={formData.gender}
                  onChange={(e) => setFormData({...formData, gender: e.target.value})}
                >
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
                <input
                  type="text"
                  value={formData.number}
                  onChange={(e) => setFormData({...formData, number: e.target.value})}
                />
              </div>
              <div className="form-group">
                <label>Date of Birth</label>
                <input
                  type="text"
                  placeholder="DD-MM-YYYY"
                  value={formData.dob}
                  onChange={(e) => setFormData({...formData, dob: e.target.value})}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Address</label>
              <textarea
                value={formData.address}
                onChange={(e) => setFormData({...formData, address: e.target.value})}
                rows="2"
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Company</label>
                <input
                  type="text"
                  value={formData.vendor_company}
                  onChange={(e) => setFormData({...formData, vendor_company: e.target.value})}
                />
              </div>
              <div className="form-group">
                <label>Purpose</label>
                <input
                  type="text"
                  value={formData.purpose}
                  onChange={(e) => setFormData({...formData, purpose: e.target.value})}
                />
              </div>
            </div>

            <div className="form-actions">
              <button type="submit" className="btn btn-primary">
                {editingVendor ? 'Update' : 'Save'} User
              </button>
              <button type="button" className="btn btn-secondary" onClick={resetForm}>
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="users-list">
        <h3>Users ({vendors.length})</h3>
        {vendors.length === 0 ? (
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
                </div>
                <div className="user-card-actions">
                  <button className="btn-icon" onClick={() => handleEdit(vendor)}>
                    <Edit size={18} />
                  </button>
                  <button className="btn-icon danger" onClick={() => handleDelete(vendor.vendor_id)}>
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



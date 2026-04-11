# Face Recognition Attendance System - Setup Guide

## Overview

A modern web-based face recognition attendance system optimized for:

- **VM Deployment** - Runs on virtual machines
- **Mobile/Tablet Access** - Responsive React frontend
- **PostgreSQL Database** - Enterprise-grade database
- **20-Second Processing** - Fast recognition with timeout
- **Offline Mode** - Local queue with delayed sync
- **Indian Face Optimization** - Tuned for Indian facial features

## Architecture

### Backend (Python/Flask)

- Flask REST API
- PostgreSQL database
- Offline storage with sync
- Face recognition service

### Frontend (React/Vite)

- Modern React application
- Mobile-responsive design
- Real-time camera access
- Status indicators

## Prerequisites

1. **Python 3.8+**
2. **Node.js 18+** (for frontend)
3. **PostgreSQL 12+**
4. **OpenCV dependencies** (for face recognition)

## Installation Steps

### 1. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure database in config.py
# Update DATABASE_CONFIG with your PostgreSQL credentials:
# - host
# - port
# - user
# - password
# - database
```

### 2. PostgreSQL Database Setup

```sql
-- Create database
CREATE DATABASE attendance_db;

-- The application will create tables automatically on first run
-- Or you can run the create_tables() method manually
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run build
```

### 4. Configure Application

Edit `config.py`:

- Update PostgreSQL connection details
- Adjust face recognition parameters
- Configure server host/port for VM access

## Running the Application

### Development Mode

**Backend:**

```bash
python app.py
```

**Frontend (separate terminal):**

```bash
cd frontend
npm run dev
```

### Production Mode (VM Deployment)

**Build frontend:**

```bash
cd frontend
npm run build
```

**Run backend (accessible from network):**

```bash
python app.py
```

The app will be available at:

- Backend API: `http://VM_IP:8002/api`
- Frontend: `http://VM_IP:8002/` (if serving static files)

## API Endpoints

- `POST /api/recognize` - Recognize face from image
- `GET /api/attendance` - Get attendance records
- `GET /api/status` - Get system status
- `POST /api/sync` - Manually trigger sync

## Features

### 1. 20-Second Timeout

- Maximum processing time per user
- Automatic timeout handling
- Clear error messages

### 2. Offline Mode

- Local queue storage
- Automatic sync when online
- Manual sync option
- Status indicators

### 3. Mobile Optimized

- Responsive design
- Touch-friendly interface
- Camera access via browser
- Works on phones/tablets

### 4. Indian Face Optimization

- Lower confidence threshold (75%)
- Optimized detection parameters
- Better accuracy for Indian faces

## File Structure

```
.
├── app.py                      # Flask application
├── config.py                   # Configuration
├── database.py                 # PostgreSQL operations
├── offline_storage.py          # Offline queue management
├── face_recognition_service.py # Face recognition logic
├── requirements.txt         # Python dependencies
├── frontend/                    # React frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
└── static/                    # Built frontend (after build)
```

## Troubleshooting

### Camera Not Working

- Ensure HTTPS or localhost (browsers require secure context)
- Check browser permissions
- Try different browser

### Database Connection Failed

- Verify PostgreSQL is running
- Check credentials in config.py
- Ensure database exists

### Face Recognition Not Working

- Ensure classifier.xml exists
- Check haarcascade_frontalface_default.xml is present
- Train model with Indian faces for better accuracy

## Production Deployment

1. Use a production WSGI server (Gunicorn, uWSGI)
2. Set up reverse proxy (Nginx)
3. Configure SSL/HTTPS
4. Set up PostgreSQL connection pooling
5. Configure firewall rules for VM access

## Notes

- The system automatically creates database tables on first run
- Offline records sync every 60 seconds when online
- Maximum queue size: 1000 records
- Processing optimized for low-latency networks


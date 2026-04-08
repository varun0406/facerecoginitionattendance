# Quick Start Guide - Local Testing with MySQL

## ✅ Database Connection Verified!

Your MySQL connection is working:
- **Host:** localhost
- **Database:** attendance
- **User:** root
- **Password:** 87654321

## Steps to Run the Application

### 1. Install Frontend Dependencies (First Time Only)

```bash
cd frontend
npm install
npm run build
cd ..
```

### 2. Start the Flask Application

```bash
python app.py
```

Or use the batch file:
```bash
start.bat
```

### 3. Access the Application

Open your browser and go to:
- **Local:** http://localhost:8002
- **Network:** http://YOUR_IP:8002 (for phone/tablet access)

### 4. Test with Phone/Tablet

1. Make sure your phone/tablet is on the same network
2. Find your computer's IP address:
   - Windows: `ipconfig` (look for IPv4 Address)
   - Example: `192.168.1.100`
3. On your phone/tablet browser, go to: `http://192.168.1.100:8002`
4. Allow camera permissions when prompted

## API Endpoints

- `GET /api/status` - Check system status
- `POST /api/recognize` - Recognize face from image
- `GET /api/attendance` - Get attendance records
- `POST /api/sync` - Manually sync offline records

## Testing the API

You can test the API directly:

```bash
# Check status
curl http://localhost:8002/api/status

# Get attendance records
curl http://localhost:8002/api/attendance
```

## Important Notes

1. **Camera Access:** Browsers require HTTPS or localhost for camera access
2. **Face Recognition:** Make sure `classifier.xml` exists (train the model first)
3. **Database:** Tables are created automatically on first run
4. **Offline Mode:** Records are queued locally if database is unavailable

## Troubleshooting

### Camera Not Working
- Use `localhost` or `127.0.0.1` (HTTPS not required for localhost)
- Check browser permissions
- Try Chrome or Firefox

### Database Connection Failed
- Verify MySQL is running
- Check credentials in `config.py`
- Ensure database `attendance` exists

### Frontend Not Loading
- Build the frontend: `cd frontend && npm run build`
- Check `static/` folder exists with `index.html`

## Next Steps

1. Train face recognition model with your data
2. Add vendor/user data to `vendor_details` table
3. Test face recognition with trained faces
4. Deploy to VM when ready (change host to `0.0.0.0` in config.py)



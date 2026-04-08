@echo off
REM Start script for Face Recognition Attendance System (Windows)

echo Starting Face Recognition Attendance System...

REM Check if PostgreSQL is configured
echo Checking PostgreSQL configuration...
python -c "from config import DATABASE_CONFIG; print('Database:', DATABASE_CONFIG['database'])"

REM Initialize database
echo Initializing database...
python -c "from database import Database; Database.initialize_pool(); Database.create_tables(); print('Database initialized')"

REM Check if frontend is built
if not exist "static\index.html" (
    echo Frontend not built. Building now...
    cd frontend
    call npm install
    call npm run build
    cd ..
)

REM Start Flask application (port 8002 — set FLASK_PORT to override)
set FLASK_PORT=8002
echo Starting Flask server on port %FLASK_PORT%...
python app.py

pause



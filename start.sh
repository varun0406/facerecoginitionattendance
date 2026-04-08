#!/bin/bash

# Start script for Face Recognition Attendance System

echo "Starting Face Recognition Attendance System..."

# Check if PostgreSQL is configured
echo "Checking PostgreSQL configuration..."
python -c "from config import DATABASE_CONFIG; print(f'Database: {DATABASE_CONFIG[\"database\"]}')"

# Initialize database
echo "Initializing database..."
python -c "from database import Database; Database.initialize_pool(); Database.create_tables(); print('Database initialized')"

# Check if frontend is built
if [ ! -d "static" ] || [ ! -f "static/index.html" ]; then
    echo "Frontend not built. Building now..."
    cd frontend
    npm install
    npm run build
    cd ..
fi

# Start Flask application (port 8002 — override with FLASK_PORT)
export FLASK_PORT="${FLASK_PORT:-8002}"
echo "Starting Flask server on port ${FLASK_PORT}..."
python app.py



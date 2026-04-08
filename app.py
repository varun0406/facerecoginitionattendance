"""
Flask Web Application for Face Recognition Attendance System
Optimized for VM deployment with mobile/tablet access
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import threading
import time
from datetime import datetime
import logging
import os
from config import SERVER_CONFIG, OFFLINE_CONFIG, FILE_PATHS, TRAINING_CONFIG
from database import Database
from offline_storage import OfflineStorage
from face_recognition_service import FaceRecognitionService
from training_service import TrainingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_cors = os.environ.get('CORS_ORIGINS', '').strip()
if _cors:
    CORS(app, origins=[o.strip() for o in _cors.split(',') if o.strip()], supports_credentials=True)
else:
    CORS(app)

# Before background sync touches the DB (must run before any thread uses Database)
try:
    Database.initialize_pool()
    Database.create_tables()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error("Database initialization failed: %s", e)

# Initialize services
face_service = FaceRecognitionService()
offline_storage = OfflineStorage()
training_service = TrainingService()

# Background sync thread
def background_sync():
    """Background thread for syncing offline records"""
    while True:
        try:
            if offline_storage.check_connectivity():
                result = offline_storage.sync_to_database()
                if result['synced'] > 0:
                    logger.info(f"Synced {result['synced']} records")
            time.sleep(OFFLINE_CONFIG['sync_interval'])
        except Exception as e:
            logger.error(f"Error in background sync: {e}")
            time.sleep(OFFLINE_CONFIG['sync_interval'])

# Start background sync thread
sync_thread = threading.Thread(target=background_sync, daemon=True)
sync_thread.start()

@app.route('/')
def index():
    """Main page - serve React frontend"""
    static_path = FILE_PATHS['static_folder']
    if os.path.exists(os.path.join(static_path, 'index.html')):
        return send_from_directory(static_path, 'index.html')
    else:
        # Fallback if frontend not built yet
        return """
        <html>
            <head><title>Face Recognition Attendance</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px; background: #012b36; color: white;">
                <h1>Face Recognition Attendance System</h1>
                <p>Please build the frontend first:</p>
                <pre style="background: #00353f; padding: 20px; border-radius: 8px; display: inline-block;">
cd frontend
npm install
npm run build
                </pre>
                <p style="margin-top: 20px;">API is available at <a href="/api/status" style="color: #60a5fa;">/api/status</a></p>
            </body>
        </html>
        """

@app.route('/assets/<path:path>')
def serve_assets(path):
    """Serve React build assets"""
    static_path = FILE_PATHS['static_folder']
    assets_path = os.path.join(static_path, 'assets')
    if os.path.exists(assets_path):
        return send_from_directory(assets_path, path)
    return '', 404

@app.route('/api/recognize', methods=['POST'])
def recognize_face():
    """API endpoint for face recognition"""
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({'success': False, 'error': 'No image data provided'}), 400
        
        image_data = data['image']
        
        # Validate image data
        if not image_data:
            return jsonify({'success': False, 'error': 'No image data provided'}), 400
        
        # Check if it's a valid base64 string
        if isinstance(image_data, str):
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            # Basic validation - base64 strings should be longer
            if len(image_data) < 50:
                return jsonify({'success': False, 'error': 'Image data too short. Please ensure camera is capturing properly.'}), 400
        
        # Recognize face
        result = face_service.recognize_face(image_data)
        
        if result['success']:
            # Mark attendance
            attendance_result = face_service.mark_attendance(
                user_id=result['user_id'],
                name=result['name'],
                department=result.get('department', ''),
                address=result.get('address', '')
            )
            
            return jsonify({
                'success': True,
                'recognition': result,
                'attendance': attendance_result
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Recognition failed'),
                'timeout': result.get('timeout', False),
                'processing_time': result.get('processing_time', 0)
            }), 400
    
    except Exception as e:
        logger.error(f"Error in recognize endpoint: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    """Get attendance records, enriched with duration."""
    try:
        date = request.args.get('date')
        limit = int(request.args.get('limit', 100))
        records = Database.get_attendance_records(date=date, limit=limit)
        return jsonify({
            'success': True,
            'records': records,
            'count': len(records)
        })
    except Exception as e:
        logger.error(f"Error fetching attendance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/attendance/summary', methods=['GET'])
def get_attendance_summary():
    """Per-user totals: days present and total hours."""
    try:
        date = request.args.get('date')
        limit = int(request.args.get('limit', 500))
        summary = Database.get_attendance_summary(date=date, limit=limit)
        return jsonify({
            'success': True,
            'summary': summary,
            'count': len(summary)
        })
    except Exception as e:
        logger.error(f"Error fetching attendance summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status"""
    try:
        db_connected = Database.test_connection()
        pending_sync = offline_storage.get_pending_count()
        
        return jsonify({
            'success': True,
            'database_connected': db_connected,
            'pending_sync': pending_sync,
            'offline_mode': pending_sync > 0 and not db_connected
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sync', methods=['POST'])
def manual_sync():
    """Manually trigger sync of offline records"""
    try:
        result = offline_storage.sync_to_database()
        return jsonify({
            'success': True,
            'result': result
        })
    except Exception as e:
        logger.error(f"Error in manual sync: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# User/Vendor Management Endpoints
@app.route('/api/vendors', methods=['GET'])
def get_vendors():
    """Get all vendors/users"""
    try:
        vendors = Database.get_all_vendors()
        return jsonify({
            'success': True,
            'vendors': vendors,
            'count': len(vendors)
        })
    except Exception as e:
        logger.error(f"Error fetching vendors: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vendors', methods=['POST'])
def add_vendor():
    """Add a new vendor/user"""
    try:
        data = request.json
        if not data or 'vendor_id' not in data or 'name' not in data:
            return jsonify({'success': False, 'error': 'vendor_id and name are required'}), 400
        
        Database.add_vendor(data)
        return jsonify({
            'success': True,
            'message': 'Vendor added successfully'
        })
    except Exception as e:
        logger.error(f"Error adding vendor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vendors/<int:vendor_id>', methods=['PUT'])
def update_vendor(vendor_id):
    """Update vendor information"""
    try:
        data = request.json
        if Database.update_vendor(vendor_id, data):
            return jsonify({
                'success': True,
                'message': 'Vendor updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Vendor not found'}), 404
    except Exception as e:
        logger.error(f"Error updating vendor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vendors/<int:vendor_id>', methods=['DELETE'])
def delete_vendor(vendor_id):
    """Delete a vendor"""
    try:
        if Database.delete_vendor(vendor_id):
            return jsonify({
                'success': True,
                'message': 'Vendor deleted successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Vendor not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting vendor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Training Endpoints
@app.route('/api/training/capture', methods=['POST'])
def capture_training_image():
    """Capture a training image for a user"""
    try:
        data = request.json
        if not data or 'user_id' not in data or 'image' not in data:
            return jsonify({'success': False, 'error': 'user_id and image are required'}), 400
        
        user_id = int(data['user_id'])
        image_data = data['image']
        
        # Validate image data
        if not image_data:
            return jsonify({'success': False, 'error': 'No image data provided'}), 400
        
        # Check if it's a valid base64 string
        if isinstance(image_data, str):
            # Remove data URL prefix if present for validation
            check_data = image_data.split(',')[1] if ',' in image_data else image_data
            # Basic validation - base64 strings should be longer
            if len(check_data) < 50:
                return jsonify({'success': False, 'error': 'Image data too short. Please ensure camera is capturing properly.'}), 400
        
        result = training_service.save_training_image(user_id, image_data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error capturing training image: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/training/count/<int:user_id>', methods=['GET'])
def get_training_count(user_id):
    """Get count of training images for a user"""
    try:
        count = training_service.get_user_image_count(user_id)
        return jsonify({
            'success': True,
            'user_id': user_id,
            'image_count': count,
            'min_required': TRAINING_CONFIG['min_images_per_user'],
            'recommended': TRAINING_CONFIG['recommended_images_per_user'],
            'max_images': TRAINING_CONFIG['max_images_per_user'],
        })
    except Exception as e:
        logger.error(f"Error getting training count: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/training/readiness', methods=['GET'])
def training_readiness():
    """Whether dataset meets strict rules before Train Model is allowed."""
    try:
        data = training_service.get_training_readiness()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error training readiness: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/training/train', methods=['POST'])
def train_model():
    """Train the face recognition model"""
    try:
        result = training_service.train_model()
        if result['success']:
            # Reload classifier in face service
            face_service._load_classifier()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error training model: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/training/delete/<int:user_id>', methods=['DELETE'])
def delete_user_images(user_id):
    """Delete all training images for a user"""
    try:
        result = training_service.delete_user_images(user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting images: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(
        host=SERVER_CONFIG['host'],
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug'],
        threaded=SERVER_CONFIG['threaded']
    )


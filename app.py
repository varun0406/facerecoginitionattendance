"""
Flask Web Application for Face Recognition Attendance System
Optimized for VM deployment with mobile/tablet access
"""

from flask import (
    Flask,
    abort,
    make_response,
    request,
    jsonify,
    send_from_directory,
    session,
    Response,
)
from flask_cors import CORS
from functools import wraps
import threading
import time
from datetime import datetime, timedelta
import logging
import os
from werkzeug.security import check_password_hash, generate_password_hash

from config import (
    SERVER_CONFIG,
    OFFLINE_CONFIG,
    FILE_PATHS,
    TRAINING_CONFIG,
    AUTO_CHECKOUT_HOURS,
    AUTH_CONFIG,
    GEOFENCE_CONFIG,
)
from geofence import within_radius
from database import Database
from offline_storage import OfflineStorage
from face_recognition_service import FaceRecognitionService
from training_service import TrainingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = AUTH_CONFIG["secret_key"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

_cors = os.environ.get('CORS_ORIGINS', '').strip()
if _cors:
    CORS(app, origins=[o.strip() for o in _cors.split(',') if o.strip()], supports_credentials=True)
else:
    CORS(app)

# Before background sync touches the DB (must run before any thread uses Database)
try:
    Database.initialize_pool()
    Database.create_tables()
    Database.ensure_attendance_clock_schema()
    Database.ensure_checkout_type_column()
    Database.bootstrap_web_users_from_env()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error("Database initialization failed: %s", e)

AUTH_ENABLED = AUTH_CONFIG["enabled"]
_geof_lat = GEOFENCE_CONFIG["latitude"]
_geof_lon = GEOFENCE_CONFIG["longitude"]
GEOFENCE_ACTIVE = GEOFENCE_CONFIG["enabled"] and (
    abs(_geof_lat) > 1e-5 or abs(_geof_lon) > 1e-5
)
if GEOFENCE_CONFIG["enabled"] and not GEOFENCE_ACTIVE:
    logger.warning(
        "GEOFENCE_ENABLED is set but GEOFENCE_LATITUDE/LONGITUDE look unset; "
        "geofence checks are disabled until you set a valid center."
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not AUTH_ENABLED:
            return view(*args, **kwargs)
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not AUTH_ENABLED:
            return view(*args, **kwargs)
        if not session.get("user_id"):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        if session.get("role") != "admin":
            return jsonify({"success": False, "error": "Admin access required"}), 403
        return view(*args, **kwargs)

    return wrapped

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


def background_auto_checkout():
    """Auto-close sessions open longer than AUTO_CHECKOUT_HOURS every 30 min."""
    while True:
        try:
            closed = Database.auto_checkout_open_sessions(AUTO_CHECKOUT_HOURS)
            if closed:
                logger.info("Auto-checkout: closed %s session(s)", closed)
        except Exception as e:
            logger.error("Error in auto-checkout thread: %s", e)
        time.sleep(1800)


auto_checkout_thread = threading.Thread(target=background_auto_checkout, daemon=True)
auto_checkout_thread.start()


def background_auto_train():
    """Retrain model in background when training_service signals pending."""
    while True:
        time.sleep(60)
        try:
            if training_service._pending_auto_train and not training_service.is_training:
                logger.info("Auto-train triggered in background")
                result = training_service.train_model()
                if result.get("success"):
                    face_service._load_classifier()
                    logger.info("Auto-train complete: %s", result.get("message"))
                else:
                    logger.warning("Auto-train failed: %s", result.get("error"))
        except Exception as e:
            logger.error("Error in auto-train thread: %s", e)


auto_train_thread = threading.Thread(target=background_auto_train, daemon=True)
auto_train_thread.start()


@app.route("/api/auth/config", methods=["GET"])
def auth_config_public():
    """Tell the SPA whether login and browser geolocation are required."""
    tz = os.environ.get("DISPLAY_TIMEZONE", "Asia/Kolkata")
    return jsonify(
        {
            "success": True,
            "auth_required": AUTH_ENABLED,
            "geofence_required": GEOFENCE_ACTIVE,
            "display_timezone": tz,
            "display_timezone_label": "IST" if "Kolkata" in tz else tz,
        }
    )


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    if not AUTH_ENABLED:
        return jsonify(
            {
                "success": True,
                "authenticated": True,
                "user": {"username": "local", "role": "admin"},
            }
        )
    uid = session.get("user_id")
    if not uid:
        return jsonify({"success": True, "authenticated": False, "user": None})
    return jsonify(
        {
            "success": True,
            "authenticated": True,
            "user": {
                "id": uid,
                "username": session.get("username"),
                "role": session.get("role"),
            },
        }
    )


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    if not AUTH_ENABLED:
        return jsonify({"success": False, "error": "Authentication is disabled"}), 400
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    if GEOFENCE_ACTIVE:
        try:
            lat = float(data.get("latitude"))
            lon = float(data.get("longitude"))
        except (TypeError, ValueError):
            return jsonify(
                {
                    "success": False,
                    "error": "Location required: allow browser location and try again.",
                }
            ), 400
        if not within_radius(
            lat,
            lon,
            _geof_lat,
            _geof_lon,
            float(GEOFENCE_CONFIG["radius_meters"]),
        ):
            return jsonify(
                {
                    "success": False,
                    "error": "You are outside the allowed area for this application.",
                }
            ), 403

    row = Database.get_app_user_by_username(username)
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"success": False, "error": "Invalid username or password"}), 401

    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]
    session["username"] = row["username"]
    session["role"] = row["role"]
    return jsonify(
        {
            "success": True,
            "user": {"username": row["username"], "role": row["role"]},
        }
    )


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/auth/users", methods=["GET"])
@admin_required
def list_web_users():
    """Admin: list staff + admin logins (no passwords)."""
    users = Database.list_app_users()
    # Normalise for JSON (SQLite may return bytes for created_at)
    out = []
    for u in users:
        row = dict(u)
        if row.get("created_at") is not None:
            row["created_at"] = str(row["created_at"])
        out.append(row)
    return jsonify({"success": True, "users": out})


@app.route("/api/auth/users", methods=["POST"])
@admin_required
def create_staff_user():
    """Admin: create a staff login (role user). Staff may use attendance + view records only."""
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or len(username) < 2:
        return jsonify({"success": False, "error": "Username must be at least 2 characters"}), 400
    if len(password) < 8:
        return jsonify(
            {"success": False, "error": "Password must be at least 8 characters"}
        ), 400
    if Database.get_app_user_by_username(username):
        return jsonify({"success": False, "error": "Username already exists"}), 409
    h = generate_password_hash(password)
    if not Database.insert_app_user(username, h, "user"):
        return jsonify({"success": False, "error": "Could not create user"}), 500
    return jsonify({"success": True, "message": f"Staff account {username!r} created"})


@app.route("/api/auth/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_web_user(user_id):
    """Admin: remove a staff (or admin) login; cannot delete yourself or last admin."""
    if user_id == session.get("user_id"):
        return jsonify({"success": False, "error": "You cannot delete your own account"}), 403
    ok, err = Database.delete_app_user_by_id(user_id)
    if not ok:
        return jsonify({"success": False, "error": err}), 400
    return jsonify({"success": True, "message": "User deleted"})


def _resolved_asset_file(static_path, path):
    """Absolute path to a file under static/assets, or None if missing / unsafe."""
    assets_dir = os.path.realpath(os.path.join(static_path, 'assets'))
    if not os.path.isdir(assets_dir):
        return None
    norm = path.replace('\\', '/').lstrip('/')
    if not norm or '..' in norm.split('/'):
        return None
    full = os.path.realpath(os.path.join(assets_dir, *norm.split('/')))
    if not full.startswith(assets_dir + os.sep):
        return None
    return full if os.path.isfile(full) else None


def _send_index_no_cache(static_path):
    """Serve index.html; avoid stale shell caching old hashed /assets/* URLs after rebuild."""
    resp = make_response(send_from_directory(static_path, 'index.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp


@app.route('/')
def index():
    """Main page - serve React frontend"""
    static_path = FILE_PATHS['static_folder']
    if os.path.exists(os.path.join(static_path, 'index.html')):
        return _send_index_no_cache(static_path)
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
    """Serve React build assets. Missing files must not return HTML (breaks type=module)."""
    static_path = FILE_PATHS['static_folder']
    assets_path = os.path.realpath(os.path.join(static_path, 'assets'))
    full = _resolved_asset_file(static_path, path)
    if not full:
        return Response('Not Found', status=404, mimetype='text/plain')
    rel = os.path.relpath(full, assets_path)
    resp = make_response(send_from_directory(assets_path, rel))
    # Hashed filenames are content-addressed; safe to cache long-term
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp

@app.route('/api/recognize', methods=['POST'])
@login_required
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
@login_required
def get_attendance():
    """Get attendance records with optional date / date range filtering."""
    try:
        date = request.args.get('date')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        limit = int(request.args.get('limit', 100))
        records = Database.get_attendance_records(
            date=date, date_from=date_from, date_to=date_to, limit=limit
        )
        return jsonify({'success': True, 'records': records, 'count': len(records)})
    except Exception as e:
        logger.error(f"Error fetching attendance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/attendance/summary', methods=['GET'])
@login_required
def get_attendance_summary():
    """Per-user totals: days present and total hours."""
    try:
        date = request.args.get('date')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        limit = int(request.args.get('limit', 500))
        summary = Database.get_attendance_summary(
            date=date, date_from=date_from, date_to=date_to, limit=limit
        )
        return jsonify({'success': True, 'summary': summary, 'count': len(summary)})
    except Exception as e:
        logger.error(f"Error fetching attendance summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/attendance/<int:record_id>', methods=['PUT'])
@admin_required
def update_attendance_record(record_id):
    """Manually edit clock-in / clock-out times."""
    try:
        data = request.get_json()
        start_time = (data.get('start_time') or '').strip()
        end_time = (data.get('end_time') or '').strip()
        if not start_time:
            return jsonify({'success': False, 'error': 'start_time is required'}), 400
        ok = Database.update_attendance_record(record_id, start_time, end_time or None)
        if not ok:
            return jsonify({'success': False, 'error': 'Record not found'}), 404
        return jsonify({'success': True, 'message': 'Attendance record updated'})
    except Exception as e:
        logger.error(f"Error updating attendance: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/attendance/<int:record_id>', methods=['DELETE'])
@admin_required
def delete_attendance_record(record_id):
    """Delete a single attendance record."""
    try:
        ok = Database.delete_attendance_record(record_id)
        if not ok:
            return jsonify({'success': False, 'error': 'Record not found'}), 404
        return jsonify({'success': True, 'message': 'Record deleted'})
    except Exception as e:
        logger.error(f"Error deleting attendance record: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/training/status', methods=['GET'])
@login_required
def get_training_status():
    """Current training state and pending auto-train flag."""
    try:
        return jsonify({
            'success': True,
            'is_training': training_service.is_training,
            'pending_auto_train': training_service._pending_auto_train,
        })
    except Exception as e:
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
@admin_required
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
@login_required
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
@admin_required
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
@admin_required
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
@admin_required
def delete_vendor(vendor_id):
    """Delete vendor + cascade: attendance records + training images."""
    try:
        # Delete training images from disk
        img_result = training_service.delete_user_images(vendor_id)
        had_images = img_result.get('deleted_count', 0) > 0

        # Cascade-delete DB rows (attendance then vendor)
        result = Database.delete_vendor_cascade(vendor_id)
        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Vendor not found')
            }), 404

        # Invalidate embeddings file if this user had training images
        if had_images:
            embeddings_path = FILE_PATHS.get('embeddings', 'face_embeddings.pkl')
            if os.path.exists(embeddings_path):
                os.remove(embeddings_path)
            face_service._load_classifier()

        return jsonify({
            'success': True,
            'message': 'User deleted',
            'training_images_deleted': img_result.get('deleted_count', 0),
            'attendance_records_deleted': result.get('attendance_records_deleted', 0),
        })
    except Exception as e:
        logger.error(f"Error deleting vendor: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vendors/<int:vendor_id>/delete-info', methods=['GET'])
@admin_required
def vendor_delete_info(vendor_id):
    """Return counts of data that will be removed on delete (for the UI warning)."""
    try:
        img_count = training_service.get_user_image_count(vendor_id)
        att_count = Database.get_vendor_attendance_count(vendor_id)
        return jsonify({
            'success': True,
            'vendor_id': vendor_id,
            'training_images': img_count,
            'attendance_records': att_count,
        })
    except Exception as e:
        logger.error(f"Error getting delete info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Training Endpoints
@app.route('/api/training/capture', methods=['POST'])
@admin_required
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
@admin_required
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
@admin_required
def training_readiness():
    """Whether dataset meets strict rules before Train Model is allowed."""
    try:
        data = training_service.get_training_readiness()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error training readiness: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/training/train', methods=['POST'])
@admin_required
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
@admin_required
def delete_user_images(user_id):
    """Delete all training images for a user"""
    try:
        result = training_service.delete_user_images(user_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error deleting images: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/<path:subpath>')
def spa_fallback(subpath):
    """Serve the React app for client-side routes (/login, /records, …)."""
    if subpath.startswith('api/') or subpath.startswith('assets/'):
        abort(404)
    static_path = FILE_PATHS['static_folder']
    index_path = os.path.join(static_path, 'index.html')
    if os.path.exists(index_path):
        return _send_index_no_cache(static_path)
    abort(404)


if __name__ == '__main__':
    app.run(
        host=SERVER_CONFIG['host'],
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug'],
        threaded=SERVER_CONFIG['threaded']
    )


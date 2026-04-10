"""
Configuration file for Face Recognition Attendance System
Optimized for Indian facial features, low-latency, and offline operation
Web-based for VM deployment with mobile access
"""

import os

# Face Recognition Settings — dlib ResNet 128-dim embeddings
FACE_RECOGNITION_CONFIG = {
    # Lower = stricter (0.40 very strict, 0.45 tight, 0.50 default). Tune in prod.
    'face_distance_threshold': float(os.environ.get('FACE_DISTANCE_THRESHOLD', '0.45')),
    'face_detection_scale': 1.1,
    'face_detection_neighbors': 5,
    'recognition_timeout': 20,
    'min_face_size': (40, 40),
    'reject_multiple_faces': os.environ.get('FACE_REJECT_MULTIPLE', 'true').lower()
    in ('1', 'true', 'yes'),
}

# Training capture & train-time gates
TRAINING_CONFIG = {
    'min_images_per_user': int(os.environ.get('TRAINING_MIN_IMAGES', '5')),
    'recommended_images_per_user': int(os.environ.get('TRAINING_RECOMMENDED_IMAGES', '30')),
    'max_images_per_user': int(os.environ.get('TRAINING_MAX_IMAGES', '120')),
    'min_face_size_capture': (
        int(os.environ.get('TRAINING_MIN_FACE_W', '72')),
        int(os.environ.get('TRAINING_MIN_FACE_H', '72')),
    ),
    'face_neighbors_capture': int(os.environ.get('TRAINING_FACE_NEIGHBORS', '6')),
    'min_laplacian_variance': float(os.environ.get('TRAINING_MIN_LAPLACIAN', '38')),
    'min_brightness': float(os.environ.get('TRAINING_MIN_BRIGHTNESS', '42')),
    'max_brightness': float(os.environ.get('TRAINING_MAX_BRIGHTNESS', '230')),
}

# Database — override on the VM via environment (see deploy/env.example)
DATABASE_CONFIG = {
    'host': os.environ.get('DATABASE_HOST', 'localhost'),
    'port': int(os.environ.get('DATABASE_PORT', '3306')),
    'user': os.environ.get('DATABASE_USER', 'root'),
    'password': os.environ.get('DATABASE_PASSWORD', '87654321'),
    'database': os.environ.get('DATABASE_NAME', 'attendance'),
    'connection_timeout': int(os.environ.get('DATABASE_CONNECT_TIMEOUT', '5')),
    'retry_attempts': int(os.environ.get('DATABASE_RETRY_ATTEMPTS', '3')),
    'retry_delay': int(os.environ.get('DATABASE_RETRY_DELAY', '2')),
    'pool_size': int(os.environ.get('DATABASE_POOL_SIZE', '10')),
    # mysql | postgresql | sqlite (sqlite = single file, no server)
    'db_type': os.environ.get('DATABASE_TYPE', 'sqlite').lower(),
    'sqlite_path': os.environ.get('SQLITE_PATH', 'attendance.db'),
}

# Offline/Edge Processing Configuration
OFFLINE_CONFIG = {
    'enable_offline_mode': True,
    'local_storage_path': 'offline_queue',
    'max_queue_size': 1000,  # Maximum records in offline queue
    'sync_interval': 60,  # Sync every 60 seconds when online
    'batch_size': 50,  # Number of records to sync at once
    'auto_sync': True,  # Automatically sync when connection is available
}

# Network Configuration
NETWORK_CONFIG = {
    'check_connectivity_interval': 30,  # Check connectivity every 30 seconds
    'low_bandwidth_mode': True,  # Enable low bandwidth optimizations
    'compress_data': True,  # Compress data for transmission
}

# Performance Settings
PERFORMANCE_CONFIG = {
    'image_resolution': (640, 480),  # Lower resolution for speed
    'frame_skip': 2,  # Process every 2nd frame for speed
    'max_concurrent_users': 1,  # Process one user at a time
    'processing_queue_size': 10,  # Queue size for high traffic
}

# Web Server Configuration (VM: bind all interfaces; set FLASK_DEBUG=false in production)
SERVER_CONFIG = {
    'host': os.environ.get('FLASK_HOST', '0.0.0.0'),
    'port': int(os.environ.get('FLASK_PORT', '8002')),
    'debug': os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes'),
    'threaded': True,
}

# File Paths
FILE_PATHS = {
    'classifier': 'classifier.xml',
    'embeddings': 'face_embeddings.pkl',
    'haar_cascade': 'haarcascade_frontalface_default.xml',
    'attendance_csv': 'attendance.csv',
    'offline_queue_file': 'offline_queue/pending_attendance.json',
    'sync_log': 'offline_queue/sync_log.txt',
    'upload_folder': 'uploads',
    'static_folder': 'static',
    'templates_folder': 'templates',
}

# Auto-checkout (hours before an open session is force-closed)
AUTO_CHECKOUT_HOURS = int(os.environ.get('AUTO_CHECKOUT_HOURS', '9'))

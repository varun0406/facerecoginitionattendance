"""
Face Recognition Service
Optimized for Indian faces, low-latency, and 20-second timeout
"""

import cv2
import numpy as np
import base64
import os
from typing import Dict
from PIL import Image
from datetime import datetime
import time
import logging
from config import FACE_RECOGNITION_CONFIG, PERFORMANCE_CONFIG, FILE_PATHS
from database import Database
from offline_storage import OfflineStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FaceRecognitionService:
    """Face recognition service optimized for speed and Indian faces"""
    
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(FILE_PATHS['haar_cascade'])
        self.classifier = None
        self.classifier_path = FILE_PATHS['classifier']
        self.confidence_threshold = FACE_RECOGNITION_CONFIG['confidence_threshold']
        self.timeout = FACE_RECOGNITION_CONFIG['recognition_timeout']
        self.offline_storage = OfflineStorage()
        self._load_classifier()
    
    def _load_classifier(self):
        """Load face recognition classifier"""
        try:
            self.classifier = cv2.face.LBPHFaceRecognizer_create()
            if os.path.exists(self.classifier_path):
                self.classifier.read(self.classifier_path)
                logger.info("Classifier loaded successfully")
            else:
                logger.warning(f"Classifier file not found: {self.classifier_path}")
        except Exception as e:
            logger.error(f"Error loading classifier: {e}")
    
    def _preprocess_image(self, image_data):
        """Preprocess image for face recognition"""
        try:
            # Decode base64 image
            if isinstance(image_data, str):
                # Remove data URL prefix if present
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                
                # Decode base64
                try:
                    image_bytes = base64.b64decode(image_data)
                except Exception as e:
                    logger.error(f"Base64 decode error: {e}")
                    return None
                
                # Check if decoded data is not empty
                if len(image_bytes) == 0:
                    logger.error("Empty image data after base64 decode")
                    return None
            else:
                image_bytes = image_data
            
            # Convert to numpy array
            nparr = np.frombuffer(image_bytes, np.uint8)
            
            if len(nparr) == 0:
                logger.error("Empty numpy array from image buffer")
                return None
            
            # Decode image
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                logger.error("Failed to decode image with cv2.imdecode")
                return None
            
            # Resize for faster processing
            height, width = img.shape[:2]
            max_size = max(PERFORMANCE_CONFIG['image_resolution'])
            if max(height, width) > max_size:
                scale = max_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
            return img
        except Exception as e:
            logger.error(f"Error preprocessing image: {e}")
            return None
    
    def recognize_face(self, image_data: str) -> Dict:
        """
        Recognize face from image data (base64 encoded)
        Returns recognition result with timeout handling
        """
        start_time = time.time()
        
        try:
            # Preprocess image
            img = self._preprocess_image(image_data)
            if img is None:
                return {'success': False, 'error': 'Invalid image data'}
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detect faces with optimized parameters for speed
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=FACE_RECOGNITION_CONFIG['face_detection_scale'],
                minNeighbors=FACE_RECOGNITION_CONFIG['face_detection_neighbors'],
                minSize=FACE_RECOGNITION_CONFIG['min_face_size'],
                maxSize=FACE_RECOGNITION_CONFIG['max_face_size']
            )
            
            if len(faces) == 0:
                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    return {'success': False, 'error': 'Timeout: No face detected', 'timeout': True}
                return {'success': False, 'error': 'No face detected', 'timeout': False}
            
            if len(faces) > 1 and FACE_RECOGNITION_CONFIG.get('reject_multiple_faces', True):
                return {
                    'success': False,
                    'error': 'Multiple faces detected — only one person should be in frame for attendance.',
                    'timeout': False,
                }
            
            # Process first detected face
            (x, y, w, h) = faces[0]
            face_roi = gray[y:y+h, x:x+w]
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                return {'success': False, 'error': 'Processing timeout', 'timeout': True}
            
            # Recognize face
            if self.classifier is None:
                return {'success': False, 'error': 'Classifier not loaded'}
            
            id, confidence = self.classifier.predict(face_roi)
            confidence_percent = int((1 - confidence / 300) * 100)
            
            # Check timeout again
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                return {'success': False, 'error': 'Recognition timeout', 'timeout': True}
            
            # Check confidence threshold (optimized for Indian faces)
            if confidence_percent >= self.confidence_threshold:
                # Get user details from database
                user_data = Database.get_vendor_by_id(id)
                
                if user_data:
                    elapsed = time.time() - start_time
                    return {
                        'success': True,
                        'user_id': user_data['vendor_id'],
                        'name': user_data['name'],
                        'department': user_data.get('department', ''),
                        'address': user_data.get('address', ''),
                        'confidence': confidence_percent,
                        'processing_time': round(elapsed, 2)
                    }
                else:
                    return {'success': False, 'error': 'User not found in database'}
            else:
                elapsed = time.time() - start_time
                return {
                    'success': False,
                    'error': 'Low confidence',
                    'confidence': confidence_percent,
                    'threshold': self.confidence_threshold,
                    'processing_time': round(elapsed, 2)
                }
        
        except Exception as e:
            logger.error(f"Error in face recognition: {e}")
            elapsed = time.time() - start_time
            return {'success': False, 'error': str(e), 'processing_time': round(elapsed, 2)}
    
    def mark_attendance(self, user_id: int, name: str, department: str, address: str) -> Dict:
        """
        Clock in (start) or clock out (stop) for the recognized person only.
        Face model label must match vendor_id in the database (enforced before this call).
        """
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%d/%m/%Y")
        
        session = Database.get_today_session(user_id, date_str)
        start_display = (
            (session or {}).get('start_time')
            or (session or {}).get('time')
        )
        
        if session is None:
            attendance_id = Database.insert_clock_in(
                user_id=user_id,
                name=name,
                department=department,
                address=address,
                date=date_str,
                start_time=time_str,
                status='Present',
            )
            if attendance_id:
                return {
                    'success': True,
                    'punch_type': 'clock_in',
                    'message': f'Clock-in recorded for {name}',
                    'attendance_id': attendance_id,
                    'start_time': time_str,
                    'stop_time': None,
                    'date': date_str,
                    'synced': True,
                }
            record = {
                'event': 'clock_in',
                'user_id': user_id,
                'name': name,
                'department': department,
                'address': address,
                'start_time': time_str,
                'date': date_str,
                'status': 'Present',
            }
            if self.offline_storage.add_record(record):
                return {
                    'success': True,
                    'punch_type': 'clock_in',
                    'message': f'Clock-in queued for sync: {name}',
                    'start_time': time_str,
                    'stop_time': None,
                    'date': date_str,
                    'synced': False,
                    'pending_sync': True,
                }
            return {
                'success': False,
                'message': 'Failed to record clock-in (queue full)',
                'synced': False,
            }
        
        if not session.get('end_time'):
            if Database.update_clock_out(session['id'], time_str):
                return {
                    'success': True,
                    'punch_type': 'clock_out',
                    'message': f'Clock-out recorded for {name}',
                    'attendance_id': session['id'],
                    'start_time': start_display,
                    'stop_time': time_str,
                    'date': date_str,
                    'synced': True,
                }
            record = {
                'event': 'clock_out',
                'user_id': user_id,
                'name': name,
                'date': date_str,
                'end_time': time_str,
            }
            if self.offline_storage.add_record(record):
                return {
                    'success': True,
                    'punch_type': 'clock_out',
                    'message': f'Clock-out queued for sync: {name}',
                    'start_time': start_display,
                    'stop_time': time_str,
                    'date': date_str,
                    'synced': False,
                    'pending_sync': True,
                }
            return {
                'success': False,
                'message': 'Failed to record clock-out',
                'synced': False,
            }
        
        return {
            'success': False,
            'message': 'Start and stop already recorded for today',
            'punch_type': 'complete',
            'start_time': start_display,
            'stop_time': session.get('end_time'),
            'date': date_str,
            'day_complete': True,
        }


"""
Face Recognition Service — dlib ResNet 128-dim embedding model.
Significantly more accurate than LBPH; works well with 5+ images per person.
"""

import cv2
import numpy as np
import base64
import os
import pickle
from typing import Dict
from datetime import datetime
import time
import logging
from config import FACE_RECOGNITION_CONFIG, PERFORMANCE_CONFIG, FILE_PATHS
from database import Database
from offline_storage import OfflineStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_EMBEDDINGS_PATH = FILE_PATHS['embeddings']
_THRESHOLD = FACE_RECOGNITION_CONFIG['face_distance_threshold']

try:
    import face_recognition as _fr
    _FR_AVAILABLE = True
except ImportError:
    _fr = None
    _FR_AVAILABLE = False
    logger.warning(
        "face_recognition library not installed — recognition will be unavailable. "
        "Run: pip install face_recognition"
    )


class FaceRecognitionService:
    """dlib-powered face recognition with 128-dim embeddings."""

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(FILE_PATHS['haar_cascade'])
        self.timeout = FACE_RECOGNITION_CONFIG['recognition_timeout']
        self.offline_storage = OfflineStorage()
        self._embeddings: Dict[int, list] = {}
        self._load_classifier()

    def _load_classifier(self):
        """Load pre-trained embeddings from disk."""
        self._embeddings = {}
        if not os.path.exists(_EMBEDDINGS_PATH):
            logger.warning("Embeddings file not found: %s — train the model first.", _EMBEDDINGS_PATH)
            return
        try:
            with open(_EMBEDDINGS_PATH, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict):
                self._embeddings = data
                total = sum(len(v) for v in data.values())
                logger.info(
                    "Embeddings loaded: %s users, %s encodings", len(data), total
                )
            else:
                logger.error("Unexpected embeddings format; expected dict.")
        except Exception as e:
            logger.error("Error loading embeddings: %s", e)

    def _preprocess_image(self, image_data) -> np.ndarray | None:
        try:
            if isinstance(image_data, str):
                if "," in image_data:
                    image_data = image_data.split(",", 1)[1]
                image_bytes = base64.b64decode(image_data)
                if not image_bytes:
                    return None
            else:
                image_bytes = image_data

            nparr = np.frombuffer(image_bytes, np.uint8)
            if len(nparr) == 0:
                return None
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            h, w = img.shape[:2]
            max_px = max(PERFORMANCE_CONFIG["image_resolution"])
            if max(h, w) > max_px:
                scale = max_px / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            return img
        except Exception as e:
            logger.error("Preprocess error: %s", e)
            return None

    def recognize_face(self, image_data: str) -> Dict:
        """
        Recognize face from base64 image. Returns user details + punch type.
        Uses dlib 128-dim embeddings; falls back to a clear error if not trained.
        """
        start_time = time.time()

        if not _FR_AVAILABLE:
            return {
                "success": False,
                "error": (
                    "face_recognition library not installed. "
                    "Run: pip install face_recognition on the server."
                ),
            }

        if not self._embeddings:
            # Try reloading in case model was just trained
            self._load_classifier()
            if not self._embeddings:
                return {
                    "success": False,
                    "error": "Model not trained yet. Go to Training and capture + train first.",
                }

        img_bgr = self._preprocess_image(image_data)
        if img_bgr is None:
            return {"success": False, "error": "Invalid image data"}

        # face_recognition works on RGB
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        # Detect face locations (use HOG model — faster; CNN is more accurate but slower)
        face_locations = _fr.face_locations(img_rgb, model="hog")

        elapsed = time.time() - start_time
        if elapsed > self.timeout:
            return {"success": False, "error": "Recognition timeout", "timeout": True}

        if len(face_locations) == 0:
            return {"success": False, "error": "No face detected", "timeout": False}

        if len(face_locations) > 1 and FACE_RECOGNITION_CONFIG.get("reject_multiple_faces", True):
            return {
                "success": False,
                "error": "Multiple faces detected — only one person should be in frame.",
                "timeout": False,
            }

        # Use the largest face
        face_loc = max(face_locations, key=lambda loc: (loc[2] - loc[0]) * (loc[1] - loc[3]))
        encodings = _fr.face_encodings(img_rgb, known_face_locations=[face_loc], model="small")

        if not encodings:
            return {"success": False, "error": "Could not compute face encoding"}

        probe = encodings[0]

        # Compare against all stored embeddings
        best_uid = None
        best_dist = float("inf")

        for uid, known_encs in self._embeddings.items():
            if not known_encs:
                continue
            dists = _fr.face_distance(known_encs, probe)
            min_dist = float(np.min(dists))
            if min_dist < best_dist:
                best_dist = min_dist
                best_uid = uid

        elapsed = time.time() - start_time
        threshold = _THRESHOLD

        if best_uid is None or best_dist > threshold:
            return {
                "success": False,
                "error": "Face not recognised — low confidence",
                "best_distance": round(best_dist, 4) if best_uid else None,
                "threshold": threshold,
                "processing_time": round(elapsed, 2),
                "timeout": False,
            }

        user_data = Database.get_vendor_by_id(best_uid)
        if not user_data:
            return {"success": False, "error": "Recognised user not found in database"}

        confidence_percent = max(0, int((1 - best_dist / threshold) * 100))
        return {
            "success": True,
            "user_id": user_data["vendor_id"],
            "name": user_data["name"],
            "department": user_data.get("department", ""),
            "address": user_data.get("address", ""),
            "confidence": confidence_percent,
            "face_distance": round(best_dist, 4),
            "processing_time": round(elapsed, 2),
        }

    def mark_attendance(self, user_id: int, name: str, department: str, address: str) -> Dict:
        """Clock-in or clock-out for the recognised person."""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%d/%m/%Y")

        session = Database.get_today_session(user_id, date_str)
        start_display = (session or {}).get("start_time") or (session or {}).get("time")

        if session is None:
            attendance_id = Database.insert_clock_in(
                user_id=user_id,
                name=name,
                department=department,
                address=address,
                date=date_str,
                start_time=time_str,
                status="Present",
            )
            if attendance_id:
                return {
                    "success": True,
                    "punch_type": "clock_in",
                    "message": f"Clock-in recorded for {name}",
                    "attendance_id": attendance_id,
                    "start_time": time_str,
                    "stop_time": None,
                    "date": date_str,
                    "synced": True,
                }
            record = {
                "event": "clock_in",
                "user_id": user_id,
                "name": name,
                "department": department,
                "address": address,
                "start_time": time_str,
                "date": date_str,
                "status": "Present",
            }
            if self.offline_storage.add_record(record):
                return {
                    "success": True,
                    "punch_type": "clock_in",
                    "message": f"Clock-in queued for sync: {name}",
                    "start_time": time_str,
                    "stop_time": None,
                    "date": date_str,
                    "synced": False,
                    "pending_sync": True,
                }
            return {"success": False, "message": "Failed to record clock-in (queue full)", "synced": False}

        if not session.get("end_time"):
            if Database.update_clock_out(session["id"], time_str):
                return {
                    "success": True,
                    "punch_type": "clock_out",
                    "message": f"Clock-out recorded for {name}",
                    "attendance_id": session["id"],
                    "start_time": start_display,
                    "stop_time": time_str,
                    "date": date_str,
                    "synced": True,
                }
            record = {
                "event": "clock_out",
                "user_id": user_id,
                "name": name,
                "date": date_str,
                "end_time": time_str,
            }
            if self.offline_storage.add_record(record):
                return {
                    "success": True,
                    "punch_type": "clock_out",
                    "message": f"Clock-out queued for sync: {name}",
                    "start_time": start_display,
                    "stop_time": time_str,
                    "date": date_str,
                    "synced": False,
                    "pending_sync": True,
                }
            return {"success": False, "message": "Failed to record clock-out", "synced": False}

        return {
            "success": False,
            "message": "Start and stop already recorded for today",
            "punch_type": "complete",
            "start_time": start_display,
            "stop_time": session.get("end_time"),
            "date": date_str,
            "day_complete": True,
        }

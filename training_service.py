"""
Training Service for Face Recognition Model
Strict capture validation + minimum samples before training (production / VM safe).
"""

import cv2
import numpy as np
import os
import base64
import logging
from typing import Dict, List, Tuple

from config import FILE_PATHS, TRAINING_CONFIG
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrainingService:
    """Service for training face recognition model with quality gates."""

    def __init__(self):
        self.data_dir = "data"
        self.classifier_path = FILE_PATHS['classifier']
        self.haar_cascade_path = FILE_PATHS['haar_cascade']
        self.face_cascade = cv2.CascadeClassifier(self.haar_cascade_path)
        os.makedirs(self.data_dir, exist_ok=True)

    def _scan_user_image_counts(self) -> Dict[int, int]:
        counts: Dict[int, int] = {}
        try:
            for f in os.listdir(self.data_dir):
                if not f.endswith((".jpg", ".png")):
                    continue
                parts = f.split(".")
                if len(parts) >= 3 and parts[0] == "user":
                    try:
                        uid = int(parts[1])
                        counts[uid] = counts.get(uid, 0) + 1
                    except ValueError:
                        continue
        except OSError:
            pass
        return counts

    def _pick_largest_face(self, faces):
        return max(faces, key=lambda f: f[2] * f[3])

    def _face_quality(self, gray_roi: np.ndarray) -> Tuple[bool, str, float, float]:
        lap = float(cv2.Laplacian(gray_roi, cv2.CV_64F).var())
        mean_b = float(gray_roi.mean())
        if lap < TRAINING_CONFIG["min_laplacian_variance"]:
            return False, "Image looks too blurry — hold still and improve lighting", lap, mean_b
        if mean_b < TRAINING_CONFIG["min_brightness"]:
            return False, "Face too dark — use brighter, even lighting", lap, mean_b
        if mean_b > TRAINING_CONFIG["max_brightness"]:
            return False, "Face too bright / washed out — reduce glare", lap, mean_b
        return True, "", lap, mean_b

    def get_training_readiness(self) -> dict:
        """Per-user progress and whether training is allowed."""
        min_n = TRAINING_CONFIG["min_images_per_user"]
        rec_n = TRAINING_CONFIG["recommended_images_per_user"]
        counts = self._scan_user_image_counts()
        vendors = Database.get_all_vendors() or []
        users_out: List[dict] = []
        for v in vendors:
            vid = v["vendor_id"]
            c = counts.get(vid, 0)
            users_out.append(
                {
                    "vendor_id": vid,
                    "name": v.get("name"),
                    "image_count": c,
                    "min_required": min_n,
                    "recommended": rec_n,
                    "ready": c >= min_n,
                    "short_by": max(0, min_n - c),
                }
            )
        ok, reason = self._validate_dataset_for_training()
        messages = []
        if not ok and reason:
            messages.append(reason)
        vendor_ids = {v["vendor_id"] for v in vendors}
        for uid, c in counts.items():
            if uid not in vendor_ids:
                messages.append(
                    f"Training folder has {c} image(s) for unknown vendor_id {uid}. "
                    "Add that user in User Management or delete those files."
                )
        return {
            "success": True,
            "min_images_per_user": min_n,
            "recommended_images_per_user": rec_n,
            "max_images_per_user": TRAINING_CONFIG["max_images_per_user"],
            "users": users_out,
            "can_train": ok and not any(uid not in vendor_ids for uid in counts),
            "messages": messages,
        }

    def _validate_dataset_for_training(self) -> Tuple[bool, str]:
        min_n = TRAINING_CONFIG["min_images_per_user"]
        counts = self._scan_user_image_counts()
        if not counts:
            return False, "No training images found. Capture samples on the Training page."
        for uid, c in counts.items():
            if not Database.get_vendor_by_id(uid):
                return (
                    False,
                    f"vendor_id {uid} has {c} training image(s) but no user record in the database.",
                )
            if c < min_n:
                return (
                    False,
                    f"User {uid} needs at least {min_n} approved images (currently {c}).",
                )
            if c > TRAINING_CONFIG["max_images_per_user"]:
                return (
                    False,
                    f"User {uid} exceeds max {TRAINING_CONFIG['max_images_per_user']} images. Delete some first.",
                )
        return True, ""

    def save_training_image(self, user_id: int, image_data: str) -> dict:
        if not Database.get_vendor_by_id(user_id):
            return {
                "success": False,
                "error": f"No user with vendor_id {user_id}. Add the user before training.",
            }
        existing = self.get_user_image_count(user_id)
        if existing >= TRAINING_CONFIG["max_images_per_user"]:
            return {
                "success": False,
                "error": f"Maximum {TRAINING_CONFIG['max_images_per_user']} images per user reached.",
            }
        try:
            if isinstance(image_data, str):
                if "," in image_data:
                    image_data = image_data.split(",", 1)[1]
                try:
                    image_bytes = base64.b64decode(image_data)
                except Exception as e:
                    return {"success": False, "error": f"Invalid base64 data: {e}"}
                if len(image_bytes) == 0:
                    return {"success": False, "error": "Empty image data"}
            else:
                image_bytes = image_data

            nparr = np.frombuffer(image_bytes, np.uint8)
            if len(nparr) == 0:
                return {"success": False, "error": "Empty image buffer"}

            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return {
                    "success": False,
                    "error": "Could not decode image. Use a clear JPEG from the camera.",
                }

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            min_sz = TRAINING_CONFIG["min_face_size_capture"]
            neighbors = TRAINING_CONFIG["face_neighbors_capture"]
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.05,
                minNeighbors=neighbors,
                minSize=min_sz,
            )
            if len(faces) == 0:
                return {
                    "success": False,
                    "error": "No face found (or face too small). Move closer, face the camera, and use good light.",
                }
            if len(faces) > 1:
                return {
                    "success": False,
                    "error": "Multiple faces in frame. Only the enrolled person should be visible.",
                }

            x, y, w, h = self._pick_largest_face(faces)
            face_roi = gray[y : y + h, x : x + w]
            ok_q, qmsg, _, _ = self._face_quality(face_roi)
            if not ok_q:
                return {"success": False, "error": qmsg}

            face_resized = cv2.resize(face_roi, (200, 200))
            image_count = existing + 1
            filename = f"user.{user_id}.{image_count}.jpg"
            filepath = os.path.join(self.data_dir, filename)
            cv2.imwrite(filepath, face_resized)
            logger.info("Saved training image: %s", filename)

            return {
                "success": True,
                "filename": filename,
                "image_count": image_count,
                "min_required": TRAINING_CONFIG["min_images_per_user"],
                "recommended": TRAINING_CONFIG["recommended_images_per_user"],
                "message": f"Saved image {image_count}/{TRAINING_CONFIG['max_images_per_user']} — "
                f"aim for at least {TRAINING_CONFIG['min_images_per_user']} varied shots.",
            }
        except Exception as e:
            logger.error("Error saving training image: %s", e)
            return {"success": False, "error": str(e)}

    def get_user_image_count(self, user_id: int) -> int:
        try:
            return len(
                [
                    f
                    for f in os.listdir(self.data_dir)
                    if f.startswith(f"user.{user_id}.")
                ]
            )
        except OSError:
            return 0

    def train_model(self) -> dict:
        ok, reason = self._validate_dataset_for_training()
        if not ok:
            return {"success": False, "error": reason}
        try:
            faces = []
            ids = []
            image_files = [
                f
                for f in os.listdir(self.data_dir)
                if f.endswith((".jpg", ".png"))
            ]
            for image_file in image_files:
                try:
                    parts = image_file.split(".")
                    if len(parts) >= 3 and parts[0] == "user":
                        uid = int(parts[1])
                        image_path = os.path.join(self.data_dir, image_file)
                        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                        if img is not None and img.shape == (200, 200):
                            faces.append(img)
                            ids.append(uid)
                except Exception as e:
                    logger.warning("Skip %s: %s", image_file, e)
                    continue

            if not faces:
                return {
                    "success": False,
                    "error": "No valid 200×200 training faces found in data/. Re-capture images.",
                }

            unique_users = len(set(ids))
            logger.info(
                "Training LBPH on %s images, %s users", len(faces), unique_users
            )
            classifier = cv2.face.LBPHFaceRecognizer_create()
            classifier.train(faces, np.array(ids))
            classifier.write(self.classifier_path)
            logger.info("Model saved to %s", self.classifier_path)

            return {
                "success": True,
                "message": "Model trained and saved. Recognition is now using the new classifier.",
                "total_images": len(faces),
                "unique_users": unique_users,
                "classifier_path": self.classifier_path,
            }
        except Exception as e:
            logger.error("Error training model: %s", e)
            return {"success": False, "error": str(e)}

    def delete_user_images(self, user_id: int) -> dict:
        try:
            deleted_count = 0
            images = [
                f
                for f in os.listdir(self.data_dir)
                if f.startswith(f"user.{user_id}.")
            ]
            for image_file in images:
                filepath = os.path.join(self.data_dir, image_file)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    deleted_count += 1
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Deleted {deleted_count} images for user {user_id}",
            }
        except Exception as e:
            logger.error("Error deleting images: %s", e)
            return {"success": False, "error": str(e)}

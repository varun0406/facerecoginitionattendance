"""
Training Service for Face Recognition Model
Uses dlib-powered face_recognition library for 128-dim embeddings.
Strict capture validation + minimum samples before training.
"""

import cv2
import numpy as np
import os
import base64
import pickle
import logging
import threading
from typing import Dict, List, Tuple

from config import FILE_PATHS, TRAINING_CONFIG
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_HAAR = FILE_PATHS['haar_cascade']
_EMBEDDINGS = FILE_PATHS['embeddings']

# Lazy-import so server starts even when face_recognition not yet installed
try:
    import face_recognition as _fr
    _FR_AVAILABLE = True
except ImportError:
    _fr = None
    _FR_AVAILABLE = False
    logger.warning(
        "face_recognition library not installed. "
        "Run: pip install face_recognition   (needs cmake + build-essential)"
    )


class TrainingService:
    """Capture training images + train dlib-based embedding model."""

    def __init__(self):
        self.data_dir = "data"
        self.haar_cascade_path = _HAAR
        self.face_cascade = cv2.CascadeClassifier(self.haar_cascade_path)
        os.makedirs(self.data_dir, exist_ok=True)

        # Auto-train state (thread-safe)
        self._pending_auto_train: bool = False
        self._training_lock = threading.Lock()
        self.is_training: bool = False

    # ── image file helpers ────────────────────────────────────────────────

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

    # ── readiness ─────────────────────────────────────────────────────────

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
            users_out.append({
                "vendor_id": vid,
                "name": v.get("name"),
                "image_count": c,
                "min_required": min_n,
                "recommended": rec_n,
                "ready": c >= min_n,
                "short_by": max(0, min_n - c),
            })
        ok, reason = self._validate_dataset_for_training()
        messages = []
        if not ok and reason:
            messages.append(reason)
        if not _FR_AVAILABLE:
            messages.insert(0,
                "face_recognition library not installed — run: "
                "pip install face_recognition"
            )
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
            "can_train": ok and _FR_AVAILABLE and not any(uid not in vendor_ids for uid in counts),
            "messages": messages,
            "auto_train_pending": self._pending_auto_train,
            "is_training": self.is_training,
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

    # ── capture ───────────────────────────────────────────────────────────

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
                gray, scaleFactor=1.05, minNeighbors=neighbors, minSize=min_sz,
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
            face_roi = gray[y: y + h, x: x + w]
            ok_q, qmsg, _, _ = self._face_quality(face_roi)
            if not ok_q:
                return {"success": False, "error": qmsg}

            # Save the full colour crop (dlib needs colour BGR→RGB for embeddings)
            face_colour = img[y: y + h, x: x + w]
            face_resized = cv2.resize(face_colour, (200, 200))
            image_count = existing + 1
            filename = f"user.{user_id}.{image_count}.jpg"
            filepath = os.path.join(self.data_dir, filename)
            cv2.imwrite(filepath, face_resized)
            logger.info("Saved training image: %s", filename)

            min_n = TRAINING_CONFIG["min_images_per_user"]
            # Queue background retrain whenever the whole dataset meets train rules
            # (so each new photo can refresh the model once everyone has enough samples).
            dataset_ok, _ = self._validate_dataset_for_training()
            if dataset_ok and _FR_AVAILABLE:
                self._pending_auto_train = True
                logger.info(
                    "Auto-train queued after save (user %s now has %s images)",
                    user_id,
                    image_count,
                )

            return {
                "success": True,
                "filename": filename,
                "image_count": image_count,
                "min_required": min_n,
                "recommended": TRAINING_CONFIG["recommended_images_per_user"],
                "auto_train_triggered": self._pending_auto_train,
                "message": (
                    f"Saved image {image_count}/{TRAINING_CONFIG['max_images_per_user']} — "
                    f"aim for at least {min_n} varied shots."
                    + (
                        " Model will retrain automatically in the background."
                        if self._pending_auto_train
                        else ""
                    )
                ),
            }
        except Exception as e:
            logger.error("Error saving training image: %s", e)
            return {"success": False, "error": str(e)}

    def get_user_image_count(self, user_id: int) -> int:
        try:
            return len([
                f for f in os.listdir(self.data_dir)
                if f.startswith(f"user.{user_id}.")
                and f.endswith((".jpg", ".png"))
            ])
        except OSError:
            return 0

    # ── training ──────────────────────────────────────────────────────────

    def train_model(self) -> dict:
        if not _FR_AVAILABLE:
            self._pending_auto_train = False
            return {
                "success": False,
                "error": (
                    "face_recognition library not installed. "
                    "Run: pip install face_recognition  (needs cmake + build-essential)"
                ),
            }
        ok, reason = self._validate_dataset_for_training()
        if not ok:
            self._pending_auto_train = False
            return {"success": False, "error": reason}

        with self._training_lock:
            if self.is_training:
                return {"success": False, "error": "Training already in progress."}
            self.is_training = True
            self._pending_auto_train = False

        try:
            embeddings: Dict[int, List[np.ndarray]] = {}
            image_files = [
                f for f in os.listdir(self.data_dir)
                if f.endswith((".jpg", ".png"))
            ]
            skipped = 0
            for image_file in image_files:
                parts = image_file.split(".")
                if len(parts) < 3 or parts[0] != "user":
                    continue
                try:
                    uid = int(parts[1])
                except ValueError:
                    continue
                image_path = os.path.join(self.data_dir, image_file)
                # face_recognition expects RGB uint8
                bgr = cv2.imread(image_path)
                if bgr is None:
                    skipped += 1
                    continue
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                # Saved files are already face crops (~200×200). Running the default
                # detector on them often fails; treat the whole image as the face region
                # (same idea as face_recognition_service when a box is already known).
                h, w = rgb.shape[:2]
                if h < 8 or w < 8:
                    skipped += 1
                    continue
                whole = [(0, w, h, 0)]  # top, right, bottom, left (face_recognition / CSS order)
                encs = _fr.face_encodings(rgb, known_face_locations=whole, model="small")
                if not encs:
                    logger.debug("No face encoding in %s (unusable crop) — skipping", image_file)
                    skipped += 1
                    continue
                embeddings.setdefault(uid, []).append(encs[0])

            if not embeddings:
                return {
                    "success": False,
                    "error": "No face encodings extracted. Re-capture training images with clear faces.",
                }

            with open(_EMBEDDINGS, "wb") as f:
                pickle.dump(embeddings, f)

            total_enc = sum(len(v) for v in embeddings.values())
            logger.info(
                "Embeddings saved: %s users, %s encodings (%s skipped)",
                len(embeddings), total_enc, skipped,
            )
            return {
                "success": True,
                "message": "Model trained using dlib embeddings. Recognition is now using the new model.",
                "total_images": total_enc,
                "unique_users": len(embeddings),
                "skipped": skipped,
                "embeddings_path": _EMBEDDINGS,
            }
        except Exception as e:
            logger.error("Error training model: %s", e)
            return {"success": False, "error": str(e)}
        finally:
            with self._training_lock:
                self.is_training = False

    # ── cleanup ───────────────────────────────────────────────────────────

    def delete_user_images(self, user_id: int) -> dict:
        try:
            deleted_count = 0
            images = [
                f for f in os.listdir(self.data_dir)
                if f.startswith(f"user.{user_id}.")
                and f.endswith((".jpg", ".png"))
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

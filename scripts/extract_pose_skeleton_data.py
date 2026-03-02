import argparse
import base64
import json
import logging
import sys
import urllib.request
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_POSE_TASK_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/"
    "float16/latest/pose_landmarker_lite.task"
)
DEFAULT_POSE_TASK_MODEL_PATH = PROJECT_ROOT / "app" / "models" / "pose_landmarker_lite.task"

from app.logging_config import configure_logging
from app.utils.db import get_db_connection


def _decode_base64_to_bgr(image_base64: str) -> Optional[np.ndarray]:
    if not image_base64:
        return None

    payload = image_base64
    if "," in payload:
        _, payload = payload.split(",", 1)

    try:
        image_bytes = base64.b64decode(payload)
    except Exception:
        return None

    arr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _resolve_image_path(filename: str, gender: str) -> Optional[Path]:
    if not filename:
        return None

    file_candidate = Path(filename)
    if file_candidate.is_absolute() and file_candidate.exists():
        return file_candidate

    normalized_gender = str(gender or "").strip().lower()
    root = PROJECT_ROOT

    folders = []
    if normalized_gender == "female":
        folders.extend([
            root / "app" / "static" / "Beach_Dataset" / "Female",
            root / "app" / "static" / "Beach_Dataset" / "female",
        ])
    elif normalized_gender == "male":
        folders.extend([
            root / "app" / "static" / "Beach_Dataset" / "Male",
            root / "app" / "static" / "Beach_Dataset" / "male",
        ])

    folders.extend([
        root / "app" / "static" / "Beach_Dataset" / "Female",
        root / "app" / "static" / "Beach_Dataset" / "Male",
        root / "app" / "static" / "Beach_Dataset" / "female",
        root / "app" / "static" / "Beach_Dataset" / "male",
    ])

    for folder in folders:
        path = folder / filename
        if path.exists():
            return path

    return None


def _load_pose_image(row: dict) -> Optional[np.ndarray]:
    image = _decode_base64_to_bgr(row.get("pose_image_base64"))
    if image is not None:
        return image

    image_path = _resolve_image_path(row.get("pose_image"), row.get("gender"))
    if image_path is None:
        return None

    return cv2.imread(str(image_path), cv2.IMREAD_COLOR)


def _landmarks_to_json(landmarks, width: int, height: int) -> str:
    points = []
    visibilities = []

    if hasattr(landmarks, "landmark"):
        iterable_landmarks = landmarks.landmark
    else:
        iterable_landmarks = landmarks

    for index, landmark in enumerate(iterable_landmarks):
        visibility = float(landmark.visibility)
        points.append(
            {
                "id": index,
                "x": float(round(landmark.x, 6)),
                "y": float(round(landmark.y, 6)),
                "z": float(round(landmark.z, 6)),
                "visibility": float(round(visibility, 6)),
            }
        )
        visibilities.append(visibility)

    payload = {
        "format": "mediapipe_pose_v1",
        "landmarks": points,
        "image": {"width": width, "height": height},
        "stats": {
            "avg_visibility": float(round(float(np.mean(visibilities)) if visibilities else 0.0, 6)),
            "min_visibility": float(round(float(np.min(visibilities)) if visibilities else 0.0, 6)),
        },
    }

    return json.dumps(payload, separators=(",", ":"))


def _resolve_pose_task_model_path(explicit_model_path: Optional[str]) -> Path:
    if explicit_model_path:
        path = Path(explicit_model_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if not path.exists():
            raise RuntimeError(f"Pose task model file not found: {path}")
        return path

    if DEFAULT_POSE_TASK_MODEL_PATH.exists():
        return DEFAULT_POSE_TASK_MODEL_PATH

    DEFAULT_POSE_TASK_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.info("Downloading MediaPipe pose task model to %s", DEFAULT_POSE_TASK_MODEL_PATH)
    try:
        urllib.request.urlretrieve(DEFAULT_POSE_TASK_MODEL_URL, DEFAULT_POSE_TASK_MODEL_PATH)
    except Exception as exc:
        raise RuntimeError(
            "Failed to download default MediaPipe pose task model. "
            "Please provide a local file with --pose-model-path"
        ) from exc

    return DEFAULT_POSE_TASK_MODEL_PATH


def _create_pose_detector(mp, pose_model_path: Optional[str] = None):
    if hasattr(mp, "solutions") and hasattr(mp.solutions, "pose"):
        return (
            "solutions",
            mp.solutions.pose.Pose(
                static_image_mode=True,
                model_complexity=2,
                enable_segmentation=False,
                min_detection_confidence=0.5,
            ),
        )

    if hasattr(mp, "tasks"):
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        model_path = _resolve_pose_task_model_path(pose_model_path)

        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return ("tasks", vision.PoseLandmarker.create_from_options(options))

    raise RuntimeError("Unsupported mediapipe package: neither mp.solutions.pose nor mp.tasks is available")


def _extract_landmarks(mp, detector_type: str, detector, image_bgr: np.ndarray):
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

    if detector_type == "solutions":
        result = detector.process(rgb)
        if not result.pose_landmarks:
            return None
        return result.pose_landmarks.landmark

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = detector.detect(mp_image)
    if not getattr(result, "pose_landmarks", None):
        return None
    if not result.pose_landmarks[0]:
        return None
    return result.pose_landmarks[0]


def extract_and_update(
    limit: Optional[int],
    only_empty_skeleton: bool,
    dry_run: bool,
    pose_model_path: Optional[str] = None,
) -> None:
    try:
        import mediapipe as mp
    except Exception as exc:
        raise RuntimeError(
            "MediaPipe is required for skeleton extraction. Install with: pip install mediapipe"
        ) from exc

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        sql = "SELECT pose_id, pose_image, pose_image_base64, gender, skeleton_data FROM pose_library"
        params = []

        if only_empty_skeleton:
            sql += " WHERE skeleton_data IS NULL OR skeleton_data = ''"

        sql += " ORDER BY pose_id ASC"

        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        logging.info("Fetched %s rows for skeleton extraction", len(rows))

        processed = 0
        updated = 0
        skipped = 0
        no_pose_found = 0
        failed = 0

        detector_type, detector = _create_pose_detector(mp, pose_model_path=pose_model_path)
        logging.info("Using MediaPipe detector type=%s", detector_type)

        try:
            for row in rows:
                pose_id = row["pose_id"]
                image_bgr = _load_pose_image(row)
                if image_bgr is None:
                    logging.warning("Skipping pose_id=%s: image not found/decodable", pose_id)
                    skipped += 1
                    continue

                landmarks = _extract_landmarks(mp, detector_type, detector, image_bgr)
                if not landmarks:
                    logging.warning("No skeleton detected for pose_id=%s", pose_id)
                    no_pose_found += 1
                    continue

                height, width = image_bgr.shape[:2]
                skeleton_json = _landmarks_to_json(landmarks, width=width, height=height)

                processed += 1
                if dry_run:
                    logging.info("Dry run pose_id=%s skeleton extracted", pose_id)
                    continue

                cursor.execute(
                    "UPDATE pose_library SET skeleton_data=%s WHERE pose_id=%s",
                    (skeleton_json, pose_id),
                )
                updated += 1

        finally:
            detector.close()

        if not dry_run:
            conn.commit()

        logging.info(
            "Done. processed=%s updated=%s skipped=%s no_pose_found=%s failed=%s dry_run=%s",
            processed,
            updated,
            skipped,
            no_pose_found,
            failed,
            dry_run,
        )
    except Exception:
        logging.exception("Skeleton extraction job failed")
        raise
    finally:
        cursor.close()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract skeleton_data for pose_library images using MediaPipe Pose.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of pose rows to process")
    parser.add_argument(
        "--only-empty-skeleton",
        action="store_true",
        help="Process only rows where skeleton_data is NULL/empty",
    )
    parser.add_argument(
        "--pose-model-path",
        type=str,
        default=None,
        help="Path to MediaPipe .task model (used when mp.tasks API is active)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run extraction without updating DB")
    args = parser.parse_args()

    configure_logging()
    extract_and_update(
        limit=args.limit,
        only_empty_skeleton=args.only_empty_skeleton,
        dry_run=args.dry_run,
        pose_model_path=args.pose_model_path,
    )


if __name__ == "__main__":
    main()

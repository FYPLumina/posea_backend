import argparse
import base64
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.logging_config import configure_logging
from app.services.ai_service import ai_service
from app.utils.db import get_db_connection

SCENE_LABELS = {"beach", "sea", "horizon", "vegetation", "other_negative"}
LIGHTING_LABELS = {"golden_hour", "midday", "overcast"}
MULTI_TAG_CONFIDENCE_THRESHOLD = 0.0

TAG_ALIASES = {
    "goldenhour": "golden_hour",
    "golden-hour": "golden_hour",
    "golden hour": "golden_hour",
    "lightning": "lighting",
    "well_lit": "midday",
    "well-lit": "midday",
}


def normalize_tag(tag: str) -> str:
    normalized = str(tag or "").strip().lower().replace("-", "_").replace(" ", "_")
    return TAG_ALIASES.get(normalized, normalized)


def decode_pose_image_to_rgb(image_base64: str) -> Optional[np.ndarray]:
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
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img


def pick_scene_and_lighting(predictions: list[dict]) -> Tuple[Optional[str], Optional[str]]:
    best_scene: Tuple[Optional[str], float] = (None, -1.0)
    best_lighting: Tuple[Optional[str], float] = (None, -1.0)
    scene_candidates: list[Tuple[str, float]] = []
    lighting_candidates: list[Tuple[str, float]] = []

    for pred in predictions:
        tag = normalize_tag(pred.get("tag", ""))
        confidence = float(pred.get("confidence", 0.0) or 0.0)

        if tag in SCENE_LABELS and confidence > best_scene[1]:
            best_scene = (tag, confidence)
        if tag in SCENE_LABELS and confidence >= MULTI_TAG_CONFIDENCE_THRESHOLD:
            scene_candidates.append((tag, confidence))

        if tag in LIGHTING_LABELS and confidence > best_lighting[1]:
            best_lighting = (tag, confidence)
        if tag in LIGHTING_LABELS and confidence >= MULTI_TAG_CONFIDENCE_THRESHOLD:
            lighting_candidates.append((tag, confidence))

    if scene_candidates:
        dedup_scene = []
        seen_scene = set()
        for tag, confidence in sorted(scene_candidates, key=lambda item: item[1], reverse=True):
            if tag in seen_scene:
                continue
            seen_scene.add(tag)
            dedup_scene.append(tag)
        scene_value = ",".join(dedup_scene)
    else:
        scene_value = best_scene[0]

    if lighting_candidates:
        dedup_lighting = []
        seen_lighting = set()
        for tag, confidence in sorted(lighting_candidates, key=lambda item: item[1], reverse=True):
            if tag in seen_lighting:
                continue
            seen_lighting.add(tag)
            dedup_lighting.append(tag)
        lighting_value = ",".join(dedup_lighting)
    else:
        lighting_value = best_lighting[0]

    return scene_value, lighting_value


def classify_and_update(limit: Optional[int], only_empty_tags: bool, dry_run: bool) -> None:
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        sql = "SELECT pose_id, pose_image, pose_image_base64, scene_tag, lighting_tag FROM pose_library"
        conditions = []
        params = []

        if only_empty_tags:
            conditions.append("(scene_tag IS NULL OR scene_tag = '' OR lighting_tag IS NULL OR lighting_tag = '')")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY pose_id ASC"

        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

        logging.info("Fetched %s pose rows for classification", len(rows))

        updated = 0
        skipped = 0
        failed = 0

        for row in rows:
            pose_id = row["pose_id"]
            rgb = decode_pose_image_to_rgb(row.get("pose_image_base64"))
            if rgb is None:
                logging.warning("Skipping pose_id=%s (%s): invalid/missing base64 image", pose_id, row.get("pose_image"))
                skipped += 1
                continue

            try:
                predictions = ai_service.classify(rgb)
                scene_tag, lighting_tag = pick_scene_and_lighting(predictions)
            except Exception:
                logging.exception("Classification failed for pose_id=%s", pose_id)
                failed += 1
                continue

            logging.info(
                "pose_id=%s scene_tag=%s lighting_tag=%s predictions=%s",
                pose_id,
                scene_tag,
                lighting_tag,
                predictions,
            )

            if dry_run:
                continue

            cursor.execute(
                "UPDATE pose_library SET scene_tag=%s, lighting_tag=%s WHERE pose_id=%s",
                (scene_tag, lighting_tag, pose_id),
            )
            updated += 1

        if not dry_run:
            conn.commit()

        logging.info(
            "Done. updated=%s skipped=%s failed=%s dry_run=%s",
            updated,
            skipped,
            failed,
            dry_run,
        )

    finally:
        cursor.close()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify pose_library images and update scene/lighting tags.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of rows to process")
    parser.add_argument(
        "--only-empty-tags",
        action="store_true",
        help="Process only rows where scene_tag or lighting_tag is empty",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run classification without DB updates")
    args = parser.parse_args()

    configure_logging()
    classify_and_update(limit=args.limit, only_empty_tags=args.only_empty_tags, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

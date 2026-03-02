import argparse
import base64
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from app.logging_config import configure_logging
from app.services.ai_service import ai_service
from app.utils.db import get_db_connection

SCENE_LABELS = {"beach", "sea", "horizon", "vegetation", "other_negative"}
LIGHTING_LABELS = {"golden_hour", "midday", "overcast"}


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
    scene_tag = None
    lighting_tag = None

    for pred in predictions:
        tag = str(pred.get("tag", "")).strip().lower().replace("-", "_").replace(" ", "_")
        if not scene_tag and tag in SCENE_LABELS:
            scene_tag = tag
        if not lighting_tag and tag in LIGHTING_LABELS:
            lighting_tag = tag
        if scene_tag and lighting_tag:
            break

    if not scene_tag and predictions:
        fallback = str(predictions[0].get("tag", "")).strip().lower().replace("-", "_").replace(" ", "_")
        scene_tag = fallback or None

    return scene_tag, lighting_tag


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

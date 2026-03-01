import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.utils.image_utils import validate_image_upload, preprocess_image_bytes

from app.services.ai_service import ai_service
from app.services.pose_service import pose_service
from app.middleware.auth_middleware import get_current_user
from app.schemas import GenericResponse, UploadResponse
from app.utils.tag_utils import normalize_pose_query_tags
import random

router = APIRouter()



# New endpoint: upload background, classify, and suggest poses
from fastapi import Form
import base64

from app.utils.db import get_db_connection
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
MIN_TAG_CONFIDENCE = 0.60
POSE_GENDER_POOL = ["male", "female"]

@router.post("/suggest_poses", response_model=GenericResponse)
async def suggest_poses_by_background(
    file: UploadFile = File(None),
    image_base64: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("sub")
    filename = None
    save_path = None
    bg_dir = "static/background_images"
    os.makedirs(bg_dir, exist_ok=True)
    if file is not None:
        contents = await validate_image_upload(file)
        filename = file.filename
        save_path = os.path.join(bg_dir, filename)
        with open(save_path, "wb") as f:
            f.write(contents)
    elif image_base64 is not None:
        try:
            header, b64data = image_base64.split(",", 1) if "," in image_base64 else (None, image_base64)
            contents = base64.b64decode(b64data)
            filename = f"user_{user_id}_bg_{int(datetime.utcnow().timestamp())}.png"
            save_path = os.path.join(bg_dir, filename)
            with open(save_path, "wb") as f:
                f.write(contents)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="No image file or base64 provided.")

    # Insert into background_image table
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = "INSERT INTO background_image (user_id, file_path, upload_time) VALUES (%s, %s, %s)"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(sql, (user_id, save_path, now))
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    try:
        img_arr = preprocess_image_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        tags = ai_service.classify(img_arr)
    except Exception:
        return {"success": False, "data": None, "error": "AI classification failed"}

    logger.info(
        "Background classification response generated for user_id=%s, tags=%s",
        user_id,
        tags,
    )

    scene_tags, lighting_tags = normalize_pose_query_tags(tags, min_confidence=MIN_TAG_CONFIDENCE)
    all_tags = scene_tags + lighting_tags

    logger.info(
        "Background tags selected for pose query for user_id=%s, scene_tags=%s, lighting_tags=%s",
        user_id,
        scene_tags,
        lighting_tags,
    )

    if not all_tags:
        logger.warning(
            "No mapped scene/lighting tags for user_id=%s. Configure BG_MODEL_LABELS or BG_MODEL_LABEL_MAP to match model classes.",
            user_id,
        )

    # Query suitable poses
    poses = pose_service.get_suggestions_by_context(
        scene_tags=scene_tags,
        lighting_tags=lighting_tags,
        genders=POSE_GENDER_POOL,
        limit=20,
    )
    used_fallback = False
    if not poses or len(poses) < 20:
        used_fallback = True
        logger.info(
            "Using random pose fallback for user_id=%s (filtered_count=%s)",
            user_id,
            0 if not poses else len(poses),
        )
        # Fallback: get 20 random poses
        if hasattr(pose_service, "get_random_poses"):
            poses = pose_service.get_random_poses(20, genders=POSE_GENDER_POOL)
        else:
            # fallback: repeat or mock
            poses = (poses or []) * 10
            poses = poses[:20]
    else:
        poses = poses[:20]

    pose_summary = [
        {
            "pose_id": pose.get("pose_id"),
            "pose_image": pose.get("pose_image"),
            "scene_tag": pose.get("scene_tag"),
            "lighting_tag": pose.get("lighting_tag"),
        }
        for pose in poses
    ]
    logger.info(
        "Final suggested poses for user_id=%s fallback=%s count=%s poses=%s",
        user_id,
        used_fallback,
        len(poses),
        pose_summary,
    )

    return {"success": True, "data": {"poses": poses}, "error": None}

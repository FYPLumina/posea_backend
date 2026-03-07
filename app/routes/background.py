import os
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.utils.image_utils import validate_image_upload, preprocess_image_bytes

from app.services.ai_service import ai_service
from app.services.pose_service import pose_service
from app.middleware.auth_middleware import get_current_user
from app.schemas import GenericResponse, UploadResponse
import random

router = APIRouter()
logger = logging.getLogger(__name__)



# New endpoint: upload background, classify, and suggest poses
from fastapi import Form
import base64

from app.utils.db import get_db_connection
from datetime import datetime

@router.post("/suggest_poses", response_model=GenericResponse)
async def suggest_poses_by_background(
    file: UploadFile = File(None),
    image_base64: str = Form(None),
    gender: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("sub")
    filename = None
    save_path = None
    bg_dir = "static/background_images"
    os.makedirs(bg_dir, exist_ok=True)
    if file is not None:
        filename = file.filename
        contents = await validate_image_upload(file)
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

    # Extract scene and lighting tags, fallback to all model tags when no explicit match.
    raw_tag_names = [t.get("tag", "").strip() for t in tags if isinstance(t, dict) and t.get("tag")]
    tag_names = [tag.lower().replace("-", "_").replace(" ", "_") for tag in raw_tag_names]
    scene_tags = [
        tag for tag in tag_names
        if any(token in tag for token in ["scene", "indoor", "outdoor", "beach", "city", "nature", "studio", "sea", "horizon", "vegetation"])
    ]
    lighting_tags = [
        tag for tag in tag_names
        if any(token in tag for token in ["light", "lighting", "lit", "dark", "night", "sun", "golden_hour", "midday", "overcast"])
    ]
    all_tags = list(dict.fromkeys(scene_tags + lighting_tags))
    if not all_tags:
        all_tags = tag_names

    # Debug visibility for AI outputs used in pose retrieval.
    logger.info(f"AI tags for pose suggestion: raw={raw_tag_names}, normalized={tag_names}, selected={all_tags}")

    # Query suitable poses
    poses = pose_service.get_suggestions(all_tags, user_id=user_id, gender=gender)
    if not poses or len(poses) < 20:
        # Fallback: get 20 random poses
        if hasattr(pose_service, "get_random_poses"):
            poses = pose_service.get_suggestions([], user_id=user_id, gender=gender)
        else:
            # fallback: repeat or mock
            poses = (poses or []) * 10
            poses = poses[:20]
    else:
        poses = poses[:20]

    return {"success": True, "data": {"poses": poses}, "error": None}

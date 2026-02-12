import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.utils.image_utils import validate_image_upload, preprocess_image_bytes

from app.services.ai_service import ai_service
from app.services.pose_service import pose_service
from app.middleware.auth_middleware import get_current_user
from app.schemas import GenericResponse, UploadResponse
import random

router = APIRouter()



# New endpoint: upload background, classify, and suggest poses
from fastapi import Form
import base64

from app.utils.db import get_db_connection
from datetime import datetime

#suggest poses based on background image endpoint. 
#ai.py should call the classify method from ai_service to get tags for the background image. 
#Then it should call a new method in pose_service to get pose suggestions based on those tags. 
#The endpoint should accept either an image file upload or a base64-encoded image string. It should also save the uploaded background image to the server and store its path in the database associated with the user.
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
        filename = file.filename
        save_path = os.path.join(bg_dir, filename)
        with open(save_path, "wb") as f:
            f.write(await file.read())
        contents = await validate_image_upload(file)
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

    # # sql to save background image path in database
    # conn = get_db_connection()
    # cursor = conn.cursor()
    # try:
    #     sql = "INSERT INTO background_image (user_id, file_path, upload_time) VALUES (%s, %s, %s)"
    #     now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    #     cursor.execute(sql, (user_id, save_path, now))
    #     conn.commit()
    # finally:
    #     cursor.close()
    #     conn.close()

    try:
        img_arr = preprocess_image_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        tags = ai_service.classify(img_arr)
    except Exception:
        return {"success": False, "data": None, "error": "AI classification failed"}

    # Extract scene and lightning tags
    scene_tags = [t["tag"] for t in tags if "scene" in t["tag"]]
    lightning_tags = [t["tag"] for t in tags if "light" in t["tag"] or "lighting" in t["tag"]]
    all_tags = scene_tags + lightning_tags

    # Query suitable poses
    poses = pose_service.get_suggestions(all_tags)
    if not poses or len(poses) < 20:
        # Fallback: get 20 random poses
        if hasattr(pose_service, "get_random_poses"):
            poses = pose_service.get_random_poses(20)
        else:
            # fallback: repeat or mock
            poses = (poses or []) * 10
            poses = poses[:20]
    else:
        poses = poses[:20]

    return {"success": True, "data": {"poses": poses}, "error": None}

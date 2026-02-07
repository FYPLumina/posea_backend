
from fastapi import APIRouter, Body, Depends, Query
from app.schemas import PoseSuggestionRequest, GenericResponse
from app.services.pose_service import pose_service
from app.middleware.auth_middleware import get_current_user
from app.utils.db import get_db_connection

router = APIRouter()


# New endpoint to list poses by gender
@router.get("/list", response_model=GenericResponse)
def list_poses(
    gender: str = Query(None, description="male, female, or unisex"),
    limit: int = Query(20, description="Number of poses per page"),
    offset: int = Query(0, description="Offset for pagination")
):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = "SELECT pose_id, pose_image, pose_image_base64, description, skeleton_data, scene_tag, lighting_tag, gender FROM pose_library"
        params = []
        if gender:
            sql += " WHERE gender = %s OR gender = 'unisex'"
            params.append(gender)
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        cursor.execute(sql, tuple(params))
        poses = cursor.fetchall()
        return {"success": True, "data": {"poses": poses, "limit": limit, "offset": offset}, "error": None}
    finally:
        cursor.close()
        conn.close()


@router.post("/suggest", response_model=GenericResponse)
def suggest_pose(payload: PoseSuggestionRequest = Body(...), current_user: dict = Depends(get_current_user)):
    poses = pose_service.get_suggestions(payload.tags)
    if not poses:
        # Default fallback pose
        poses = [{"id": "default-001", "name": "Neutral Pose", "keypoints": None, "thumbnail_url": None}]
    return {"success": True, "data": {"poses": poses}, "error": None}

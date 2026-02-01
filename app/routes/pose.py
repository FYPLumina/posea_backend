from fastapi import APIRouter, Body, Depends
from app.schemas import PoseSuggestionRequest, GenericResponse
from app.services.pose_service import pose_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.post("/suggest", response_model=GenericResponse)
def suggest_pose(payload: PoseSuggestionRequest = Body(...), current_user: dict = Depends(get_current_user)):
    poses = pose_service.get_suggestions(payload.tags)
    if not poses:
        # Default fallback pose
        poses = [{"id": "default-001", "name": "Neutral Pose", "keypoints": None, "thumbnail_url": None}]
    return {"success": True, "data": {"poses": poses}, "error": None}

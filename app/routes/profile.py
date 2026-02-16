from fastapi import APIRouter, Depends, HTTPException

from app.schemas import GenericResponse
from app.services.auth_service import auth_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.delete("/image", response_model=GenericResponse)
def remove_profile_image(current_user: dict = Depends(get_current_user)):
    try:
        user = auth_service.remove_profile_image(current_user.get("sub"))
        return {"success": True, "data": user, "error": None}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/bio", response_model=GenericResponse)
def clear_bio(current_user: dict = Depends(get_current_user)):
    try:
        user = auth_service.clear_bio(current_user.get("sub"))
        return {"success": True, "data": user, "error": None}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

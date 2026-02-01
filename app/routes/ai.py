from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.utils.image_utils import validate_image_upload, preprocess_image_bytes
from app.services.ai_service import ai_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.post("/classify")
async def classify_image(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    contents = await validate_image_upload(file)
    try:
        img_arr = preprocess_image_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        tags = ai_service.classify(img_arr)
    except Exception:
        # Fallback response when AI fails
        return {"success": False, "data": None, "error": "AI classification failed"}

    return {"success": True, "data": {"tags": tags}, "error": None}

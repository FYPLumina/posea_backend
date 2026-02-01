from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.utils.image_utils import validate_image_upload, preprocess_image_bytes
from app.services.ai_service import ai_service
from app.middleware.auth_middleware import get_current_user
from app.schemas import GenericResponse, UploadResponse

router = APIRouter()


@router.post("/upload", response_model=GenericResponse)
async def upload_background(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    # Validate file
    contents = await validate_image_upload(file)
    # Preprocess
    try:
        img_arr = preprocess_image_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Optionally pass to AI service for a quick check (non-blocking in real app)
    try:
        tags = ai_service.classify(img_arr)
    except Exception:
        tags = []

    resp = {"filename": file.filename, "content_type": file.content_type}
    return {"success": True, "data": {"upload": resp, "tags": tags}, "error": None}

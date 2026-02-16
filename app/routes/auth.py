
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Body

from fastapi import UploadFile, File, Form
import os
import base64
from app.schemas import UserRegister, LoginRequest, TokenResponse, GenericResponse, ProfileUpdate, ChangePasswordRequest, UserProfile, ForgotPasswordRequest, ResetPasswordRequest, EmailVerificationRequest, ResendVerificationRequest
from app.services.auth_service import auth_service, get_db_connection
from app.middleware.auth_middleware import get_current_user

PROFILE_IMAGE_DIR = os.path.join(os.path.dirname(__file__), '../static/profile_images')
os.makedirs(PROFILE_IMAGE_DIR, exist_ok=True)

router = APIRouter()

@router.get("/profile", response_model=GenericResponse)
def get_profile(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id, email, name, profile_image, bio FROM users WHERE user_id=%s", (current_user.get("sub"),))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # If profile_image is set, return as base64 string
        profile_image_b64 = None
        if user["profile_image"]:
            image_path = user["profile_image"]
            # Remove leading slash and join with static dir if needed
            if image_path.startswith("/static/"):
                image_path = os.path.join(os.path.dirname(__file__), "..", image_path.lstrip("/"))
            try:
                with open(image_path, "rb") as img_file:
                    encoded = base64.b64encode(img_file.read()).decode("utf-8")
                    profile_image_b64 = f"data:image/png;base64,{encoded}"
            except Exception:
                profile_image_b64 = None
        profile = UserProfile(
            id=user["user_id"],
            email=user["email"],
            name=user["name"],
            profile_image=profile_image_b64,
            bio=user["bio"]
        )
        return {"success": True, "data": profile, "error": None}
    finally:
        cursor.close()
        conn.close()


@router.post("/register", response_model=GenericResponse)
def register(payload: UserRegister = Body(...)):
    user = auth_service.register_user(payload.email, payload.password, payload.name)
    return {"success": True, "data": user, "error": None}


@router.post("/login", response_model=GenericResponse)
def login(payload: LoginRequest = Body(...)):
    user = auth_service.authenticate(payload.email, payload.password)
    if user and user.get("requires_verification"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your email before logging in")
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = auth_service.issue_token(user_id=user["id"])
    return {"success": True, "data": {"access_token": token, "token_type": "bearer"}, "error": None}


@router.post("/logout", response_model=GenericResponse)
def logout(current_user: dict = Depends(get_current_user)):
    auth_service.logout(current_user.get("sub"))
    return {"success": True, "data": True, "error": None}



import base64

import logging

@router.put("/profile", response_model=GenericResponse)
async def update_profile(
    name: str = Form(None),
    bio: str = Form(None),
    file: UploadFile = File(None),
    profile_image_base64: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    logger = logging.getLogger("profile_update")
    profile_image_path = None
    if file:
        filename = f"user_{current_user.get('sub')}_{file.filename}"
        save_path = os.path.join(PROFILE_IMAGE_DIR, filename)
        with open(save_path, "wb") as f:
            f.write(await file.read())
        profile_image_path = f"/static/profile_images/{filename}"
        logger.info(f"Saved file to {save_path}, profile_image_path: {profile_image_path}")
    elif profile_image_base64:
        try:
            header, b64data = profile_image_base64.split(",", 1) if "," in profile_image_base64 else (None, profile_image_base64)
            image_data = base64.b64decode(b64data)
            filename = f"user_{current_user.get('sub')}_profile.png"
            save_path = os.path.join(PROFILE_IMAGE_DIR, filename)
            with open(save_path, "wb") as f:
                f.write(image_data)
            profile_image_path = f"/static/profile_images/{filename}"
            logger.info(f"Saved base64 image to {save_path}, profile_image_path: {profile_image_path}")
        except Exception as e:
            logger.error(f"Base64 decode error: {e}")
            return {"success": False, "data": None, "error": f"Invalid base64 image: {str(e)}"}
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if bio is not None:
        update_data["bio"] = bio
    if profile_image_path:
        update_data["profile_image"] = profile_image_path
    logger.info(f"update_data to send to update_profile: {update_data}")
    user = auth_service.update_profile(current_user.get("sub"), update_data)
    logger.info(f"Returned user: {user}")
    return {"success": True, "data": user, "error": None}


@router.post("/change-password", response_model=GenericResponse)
def change_password(payload: ChangePasswordRequest = Body(...), current_user: dict = Depends(get_current_user)):
    result = auth_service.change_password(current_user.get("sub"), payload.old_password, payload.new_password)
    return {"success": True, "data": result, "error": None}


@router.post("/forgot-password", response_model=GenericResponse)
def forgot_password(payload: ForgotPasswordRequest = Body(...)):
    auth_service.forgot_password(payload.email)
    return {
        "success": True,
        "data": {"message": "If this email exists, reset instructions have been sent."},
        "error": None,
    }


@router.post("/verify-email", response_model=GenericResponse)
def verify_email(payload: EmailVerificationRequest = Body(...)):
    success = auth_service.verify_email(payload.token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    return {"success": True, "data": True, "error": None}


@router.post("/resend-verification", response_model=GenericResponse)
def resend_verification(payload: ResendVerificationRequest = Body(...)):
    auth_service.resend_verification(payload.email)
    return {
        "success": True,
        "data": {"message": "If this email exists and is unverified, a verification email has been sent."},
        "error": None,
    }


@router.post("/reset-password", response_model=GenericResponse)
def reset_password(payload: ResetPasswordRequest = Body(...)):
    try:
        success = auth_service.reset_password(payload.token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    return {"success": True, "data": True, "error": None}


@router.delete("/profile/image", response_model=GenericResponse)
def remove_profile_image(current_user: dict = Depends(get_current_user)):
    try:
        user = auth_service.remove_profile_image(current_user.get("sub"))
        return {"success": True, "data": user, "error": None}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/profile/bio", response_model=GenericResponse)
def clear_bio(current_user: dict = Depends(get_current_user)):
    try:
        user = auth_service.clear_bio(current_user.get("sub"))
        return {"success": True, "data": user, "error": None}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/", response_model=GenericResponse)
def delete_account(current_user: dict = Depends(get_current_user)):
    auth_service.delete_account(current_user.get("sub"))
    return {"success": True, "data": True, "error": None}

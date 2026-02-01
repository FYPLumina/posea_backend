from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Body
from app.schemas import UserRegister, LoginRequest, TokenResponse, GenericResponse, ProfileUpdate, ChangePasswordRequest
from app.services.auth_service import auth_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter()


@router.post("/register", response_model=GenericResponse)
def register(payload: UserRegister = Body(...)):
    user = auth_service.register_user(payload.email, payload.password, payload.name)
    return {"success": True, "data": user, "error": None}


@router.post("/login", response_model=GenericResponse)
def login(payload: LoginRequest = Body(...)):
    user = auth_service.authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = auth_service.issue_token(user_id=user["id"])
    return {"success": True, "data": {"access_token": token, "token_type": "bearer"}, "error": None}


@router.post("/logout", response_model=GenericResponse)
def logout(current_user: dict = Depends(get_current_user)):
    auth_service.logout(current_user.get("sub"))
    return {"success": True, "data": True, "error": None}


@router.put("/profile", response_model=GenericResponse)
def update_profile(payload: ProfileUpdate = Body(...), current_user: dict = Depends(get_current_user)):
    user = auth_service.update_profile(current_user.get("sub"), payload.dict(exclude_none=True))
    return {"success": True, "data": user, "error": None}


@router.post("/change-password", response_model=GenericResponse)
def change_password(payload: ChangePasswordRequest = Body(...), current_user: dict = Depends(get_current_user)):
    result = auth_service.change_password(current_user.get("sub"), payload.old_password, payload.new_password)
    return {"success": True, "data": result, "error": None}


@router.delete("/", response_model=GenericResponse)
def delete_account(current_user: dict = Depends(get_current_user)):
    auth_service.delete_account(current_user.get("sub"))
    return {"success": True, "data": True, "error": None}

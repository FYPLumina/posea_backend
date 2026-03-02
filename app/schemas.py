from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr


class GenericResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdate(BaseModel):
    name: Optional[str]
    bio: Optional[str]
    profile_image: Optional[str] = None

class UserProfile(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str]
    profile_image: Optional[str]
    bio: Optional[str]


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class EmailVerificationRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class UploadResponse(BaseModel):
    filename: str
    content_type: str


class ClassificationTag(BaseModel):
    tag: str
    confidence: float


class ClassificationResult(BaseModel):
    tags: List[ClassificationTag]


class PoseSuggestionRequest(BaseModel):
    tags: List[str]


class PoseData(BaseModel):
    id: str
    name: str
    keypoints: Optional[Any]
    thumbnail_url: Optional[str]


class PoseSuggestionResponse(BaseModel):
    poses: List[PoseData]


class SessionStartRequest(BaseModel):
    user_id: Optional[str]


class SessionEndRequest(BaseModel):
    session_id: str


class CaptureSubmitRequest(BaseModel):
    session_id: str
    pose_id: str
    timestamp: Optional[str]
    metadata: Optional[dict]

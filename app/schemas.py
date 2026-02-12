from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr

# Generic response model for API endpoints
class GenericResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

# User registration and authentication models
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None

# User login and token response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Token response model for authentication
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# User profile update and retrieval models
class ProfileUpdate(BaseModel):
    name: Optional[str]
    bio: Optional[str]
    profile_image: Optional[str] = None

# User profile response model
class UserProfile(BaseModel):
    id: int
    email: EmailStr
    name: Optional[str]
    profile_image: Optional[str]
    bio: Optional[str]

# Password change request model
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

# Image upload and classification models
class UploadResponse(BaseModel):
    filename: str
    content_type: str

# Classification result models
class ClassificationTag(BaseModel):
    tag: str
    confidence: float

# Classification result response model
class ClassificationResult(BaseModel):
    tags: List[ClassificationTag]

# Pose suggestion request and response models
class PoseSuggestionRequest(BaseModel):
    tags: List[str]

# Pose data model for suggestions
class PoseData(BaseModel):
    id: str
    name: str
    keypoints: Optional[Any]
    thumbnail_url: Optional[str]

# Pose suggestion response model containing a list of pose data
class PoseSuggestionResponse(BaseModel):
    poses: List[PoseData]

# Session management models for starting and ending sessions, and submitting captures
class SessionStartRequest(BaseModel):
    user_id: Optional[str]

# Session end request model containing session ID
class SessionEndRequest(BaseModel):
    session_id: str

# Capture submission request model containing session ID, pose ID, timestamp, and optional metadata
class CaptureSubmitRequest(BaseModel):
    session_id: str
    pose_id: str
    timestamp: Optional[str]
    metadata: Optional[dict]

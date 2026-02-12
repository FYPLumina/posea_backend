from fastapi import APIRouter, Body, Depends
from app.schemas import SessionStartRequest, SessionEndRequest, CaptureSubmitRequest, GenericResponse
from app.middleware.auth_middleware import get_current_user
from datetime import datetime

router = APIRouter()

# Session management endpoints
@router.post("/start", response_model=GenericResponse)
def start_session(payload: SessionStartRequest = Body(None), current_user: dict = Depends(get_current_user)):
    # In a real implementation, create session in DB and return session id
    session = {"session_id": "mock-session-123", "started_at": datetime.utcnow().isoformat()}
    return {"success": True, "data": session, "error": None}

#end session endpoint
@router.post("/end", response_model=GenericResponse)
def end_session(payload: SessionEndRequest = Body(...), current_user: dict = Depends(get_current_user)):
    # In a real implementation, update session in DB to mark it as ended
    session = {"session_id": payload.session_id, "ended_at": datetime.utcnow().isoformat()}
    return {"success": True, "data": session, "error": None}

# Capture submission endpoint
@router.post("/capture", response_model=GenericResponse)
def submit_capture(payload: CaptureSubmitRequest = Body(...), current_user: dict = Depends(get_current_user)):
    # Real implementation would persist capture metadata
    record = {"session_id": payload.session_id, "pose_id": payload.pose_id, "timestamp": payload.timestamp or datetime.utcnow().isoformat(), "metadata": payload.metadata}
    return {"success": True, "data": record, "error": None}

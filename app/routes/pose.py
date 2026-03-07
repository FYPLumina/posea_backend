

from fastapi import Form
import base64
from app.utils.db import get_db_connection
from datetime import datetime
from pydantic import BaseModel





from fastapi import APIRouter, Body, Depends, Query, HTTPException, status
from app.schemas import PoseSuggestionRequest, GenericResponse
from app.services.pose_service import pose_service
from app.middleware.auth_middleware import get_current_user
from app.utils.db import get_db_connection
from datetime import datetime

router = APIRouter()

# Endpoint to record pose selection
from pydantic import BaseModel

class PoseSelectRequest(BaseModel):
    pose_id: str

@router.post("/select", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
def select_pose(
    payload: PoseSelectRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    pose_id = payload.pose_id
    user_id = current_user.get("sub")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT pose_id, skeleton_data FROM pose_library WHERE pose_id = %s",
            (pose_id,),
        )
        pose_row = cursor.fetchone()
        if not pose_row:
            raise HTTPException(status_code=404, detail="Pose not found")

        sql = "INSERT INTO pose_selection (user_id, pose_id, selected_at) VALUES (%s, %s, %s)"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(sql, (user_id, pose_id, now))
        conn.commit()
        return {
            "success": True,
            "data": {
                "user_id": user_id,
                "pose_id": pose_row["pose_id"],
                "selected_at": now,
                "skeleton_data": pose_row.get("skeleton_data"),
            },
            "error": None,
        }
    finally:
        cursor.close()
        conn.close()


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
    poses = pose_service.get_suggestions(
        payload.tags,
        user_id=current_user.get("sub"),
        gender=payload.gender,
    )
    return {"success": True, "data": {"poses": poses}, "error": None}


# Endpoint to get pose_image_base64 by image id
@router.get("/image_base64/{pose_id}", response_model=GenericResponse)
def get_pose_image_base64(pose_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT pose_image_base64 FROM pose_library WHERE pose_id = %s", (pose_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pose not found")
        return {"success": True, "data": {"pose_image_base64": row["pose_image_base64"]}, "error": None}
    finally:
        cursor.close()
        conn.close()


# Endpoint to get the most used pose of the day
@router.get("/pose_of_the_day", response_model=GenericResponse)
def pose_of_the_day():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = '''
            SELECT p.* FROM pose_library p
            JOIN (
                SELECT pose_id, COUNT(*) as cnt
                FROM pose_selection
                WHERE DATE(selected_at) = CURDATE()
                GROUP BY pose_id
                ORDER BY cnt DESC
                LIMIT 1
            ) t ON p.pose_id = t.pose_id
        '''
        cursor.execute(sql)
        pose = cursor.fetchone()
        if not pose:
            return {"success": True, "data": None, "error": "No pose selected today"}
        return {"success": True, "data": pose, "error": None}
    finally:
        cursor.close()
        conn.close()


# Model for captured image upload
class CaptureImageRequest(BaseModel):
    captured_image_base64: str
    pose_id: str
    is_favourite: bool = False

# Endpoint to save captured image
@router.post("/capture_image", response_model=GenericResponse)
def capture_image(
    payload: CaptureImageRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("sub")
    captured_image_base64 = payload.captured_image_base64
    pose_id = payload.pose_id
    is_favourite = payload.is_favourite
    captured_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = "INSERT INTO captured_image (captured_image_base64, user_id, is_favourite, captured_time, pose_id) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (captured_image_base64, user_id, is_favourite, captured_time, pose_id))
        conn.commit()
        return {"success": True, "data": {"user_id": user_id, "pose_id": pose_id, "captured_time": captured_time, "is_favourite": is_favourite}, "error": None}
    finally:
        cursor.close()
        conn.close()

# Endpoint to get all captured images for the current user
@router.get("/captured_images", response_model=GenericResponse)
def get_captured_images(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        sql = "SELECT cap_image_id, captured_image_base64, user_id, is_favourite, captured_time, pose_id FROM captured_image WHERE user_id = %s ORDER BY captured_time DESC"
        cursor.execute(sql, (user_id,))
        images = cursor.fetchall()
        return {"success": True, "data": images, "error": None}
    finally:
        cursor.close()
        conn.close()

# Endpoint to set a captured image as favourite


class SetFavouriteRequest(BaseModel):
    cap_image_id: int
    is_favourite: bool


class DeleteCapturedImageRequest(BaseModel):
    cap_image_id: int


def _delete_captured_image_for_user(user_id: str, cap_image_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        sql = "DELETE FROM captured_image WHERE cap_image_id = %s AND user_id = %s"
        cursor.execute(sql, (cap_image_id, user_id))
        conn.commit()

        if cursor.rowcount == 0:
            return {
                "success": False,
                "data": None,
                "error": "Image not found or not owned by user",
            }

        return {
            "success": True,
            "data": {"cap_image_id": cap_image_id},
            "error": None,
        }
    finally:
        cursor.close()
        conn.close()

@router.post("/set_favourite", response_model=GenericResponse)
def set_captured_image_favourite(
    payload: SetFavouriteRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user.get("sub")
    cap_image_id = payload.cap_image_id
    is_favourite = payload.is_favourite
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Only allow user to update their own images
        sql = "UPDATE captured_image SET is_favourite = %s WHERE cap_image_id = %s AND user_id = %s"
        cursor.execute(sql, (is_favourite, cap_image_id, user_id))
        conn.commit()
        if cursor.rowcount == 0:
            return {"success": False, "data": None, "error": "Image not found or not owned by user"}
        return {"success": True, "data": {"cap_image_id": cap_image_id, "is_favourite": is_favourite}, "error": None}
    finally:
        cursor.close()
        conn.close()


@router.delete("/captured_images/{cap_image_id}", response_model=GenericResponse)
def delete_captured_image_by_id(
    cap_image_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return _delete_captured_image_for_user(user_id, cap_image_id)


@router.delete("/delete_captured_image", response_model=GenericResponse)
def delete_captured_image_with_query(
    cap_image_id: int = Query(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return _delete_captured_image_for_user(user_id, cap_image_id)


@router.post("/delete_captured_image", response_model=GenericResponse)
@router.post("/delete_captured_images", response_model=GenericResponse)
@router.post("/remove_captured_image", response_model=GenericResponse)
def delete_captured_image_with_post(
    payload: DeleteCapturedImageRequest = Body(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("sub")
    return _delete_captured_image_for_user(user_id, payload.cap_image_id)
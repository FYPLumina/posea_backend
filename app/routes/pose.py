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

# Endpoint to record pose selection by user
@router.post("/select", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
def select_pose(
    payload: PoseSelectRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    pose_id = payload.pose_id
    user_id = current_user.get("sub")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        #sql query to insert a new record into pose_selection table with user_id, pose_id, and current timestamp
        sql = "INSERT INTO pose_selection (user_id, pose_id, selected_at) VALUES (%s, %s, %s)"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(sql, (user_id, pose_id, now))
        conn.commit()
        return {"success": True, "data": {"user_id": user_id, "pose_id": pose_id, "selected_at": now}, "error": None}
    finally:
        cursor.close()
        conn.close()

# Endpoint to list poses with optional filtering(male,female,unisex) and pagination(limit 20)
@router.get("/list", response_model=GenericResponse)
def list_poses(
    gender: str = Query(None, description="male, female, or unisex"),
    limit: int = Query(20, description="Number of poses per page"),
    offset: int = Query(0, description="Offset for pagination")
):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        #sql query to select pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, gender from pose_library table with optional filtering.
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

# Endpoint to suggest poses based on tags (scene_tag, lighting, gender) provided by the user. 
# The tags will be passed as a list of strings in the request body. The response will include a list of suggested poses that match any of the provided tags. 
# If no poses match the tags, return a default fallback pose.
@router.post("/suggest", response_model=GenericResponse)
def suggest_pose(payload: PoseSuggestionRequest = Body(...), current_user: dict = Depends(get_current_user)):
    poses = pose_service.get_suggestions(payload.tags)
    if not poses:

        # If no poses match the tags, return a default fallback pose. 
        # The default pose can be a predefined pose in the database with a specific pose_id, for example "default-001". 
        # You can hardcode this fallback pose in the code or fetch it from the database.
        poses = [{"id": "default-001", "name": "Neutral Pose", "keypoints": None, "thumbnail_url": None}]
    return {"success": True, "data": {"poses": poses}, "error": None}


# Endpoint to get pose image in base64 format by pose_id. This will be used by the frontend to display the pose image without needing a separate image hosting solution.
@router.get("/image_base64/{pose_id}", response_model=GenericResponse)
def get_pose_image_base64(pose_id: int):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        #sql query to select pose_image_base64 from pose_library table by pose_id.
        cursor.execute("SELECT pose_image_base64 FROM pose_library WHERE pose_id = %s", (pose_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pose not found")
        return {"success": True, "data": {"pose_image_base64": row["pose_image_base64"]}, "error": None}
    finally:
        cursor.close()
        conn.close()


# Endpoint to get pose of the day based on the most selected pose by users for the current day. 
# This will allow the app to feature a popular pose each day and encourage users to try it out.
@router.get("/pose_of_the_day", response_model=GenericResponse)
def pose_of_the_day():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        #sql query to get the most selected pose for the current day from pose_selection table and join with pose_library to get pose details. 
        # The query will count the number of times each pose_id was selected today, order by count desc, and limit to 1 to get the most selected pose.
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

# Endpoint to capture user image for a specific pose. 
# The frontend will send the captured image in base64 format along with the pose_id and whether the user marked it as favourite. 
# The backend will store this information in a new table called captured_image with columns: cap_image_id (primary key), captured_image_base64, user_id, is_favourite, captured_time, pose_id. 
# This will allow users to keep a history of their captured images and mark their favourites.
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
        #sql query to insert a new record into captured_image table with captured_image_base64, user_id, is_favourite, captured_time, and pose_id.
        sql = "INSERT INTO captured_image (captured_image_base64, user_id, is_favourite, captured_time, pose_id) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(sql, (captured_image_base64, user_id, is_favourite, captured_time, pose_id))
        conn.commit()
        return {"success": True, "data": {"user_id": user_id, "pose_id": pose_id, "captured_time": captured_time, "is_favourite": is_favourite}, "error": None}
    finally:
        cursor.close()
        conn.close()

# Endpoint to get captured images of the user with optional filtering for favourites. 
# The frontend can use this endpoint to display the user's captured images in a gallery format and allow them to view their favourites easily.
@router.get("/captured_images", response_model=GenericResponse)
def get_captured_images(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("sub")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        #sql query to select cap_image_id, captured_image_base64, user_id, is_favourite, captured_time, pose_id from captured_image table by user_id and order by captured_time desc.
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

# Endpoint to set a captured image as favourite. 
# The user can mark or unmark their captured images as favourites, and this information will be updated in the captured_image table.
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
       #sql query to update is_favourite column in captured_image table by cap_image_id and user_id. This will ensure that users can only mark their own images as favourites.
        sql = "UPDATE captured_image SET is_favourite = %s WHERE cap_image_id = %s AND user_id = %s"
        cursor.execute(sql, (is_favourite, cap_image_id, user_id))
        conn.commit()
        if cursor.rowcount == 0:
            return {"success": False, "data": None, "error": "Image not found or not owned by user"}
        return {"success": True, "data": {"cap_image_id": cap_image_id, "is_favourite": is_favourite}, "error": None}
    finally:
        cursor.close()
        conn.close()
from typing import List, Dict
import logging
from app.utils.db import get_db_connection

logger = logging.getLogger(__name__)

class PoseService:
    """Fetch pose suggestions from pose_library table."""
    def get_suggestions(self, tags: List[str]) -> List[Dict]:
        logger.info(f"Fetching poses for tags: {tags}")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            #sql quary to fetch poses matching any of the provided tags (scene_tag or lighting_tag)
            sql = "SELECT pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, created_at, gender, pose_image_base64 FROM pose_library"
            params = []
            if tags:
                sql += " WHERE " + " OR ".join(["scene_tag = %s", "lighting_tag = %s"] * len(tags))
                params = []
                for tag in tags:
                    params.extend([tag, tag])
            sql += " LIMIT 20"
            cursor.execute(sql, tuple(params))
            poses = cursor.fetchall()
            return poses
        finally:
            cursor.close()
            conn.close()

    def get_random_poses(self, n: int) -> List[Dict]:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            #sql quary to fetch n random poses from pose_library
            sql = "SELECT pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, created_at, gender, pose_image_base64 FROM pose_library ORDER BY RAND() LIMIT %s"
            cursor.execute(sql, (n,))
            poses = cursor.fetchall()
            return poses
        finally:
            cursor.close()
            conn.close()


pose_service = PoseService()

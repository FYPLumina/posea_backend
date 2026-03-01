from typing import List, Dict
import logging
from app.utils.db import get_db_connection

logger = logging.getLogger(__name__)


def _summarize_poses(poses: List[Dict], max_items: int = 20) -> List[Dict]:
    summary = []
    for pose in poses[:max_items]:
        summary.append(
            {
                "pose_id": pose.get("pose_id"),
                "pose_image": pose.get("pose_image"),
                "scene_tag": pose.get("scene_tag"),
                "lighting_tag": pose.get("lighting_tag"),
            }
        )
    return summary

class PoseService:
    """Fetch pose suggestions from pose_library table."""
    @staticmethod
    def _tag_match_clause(column_name: str, tag: str):
        clause = f"({column_name} = %s OR FIND_IN_SET(%s, REPLACE(COALESCE({column_name}, ''), ' ', '')) > 0)"
        params = [tag, tag]
        return clause, params

    def get_suggestions_by_context(
        self,
        scene_tags: List[str],
        lighting_tags: List[str],
        genders: List[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        logger.info(
            "Fetching contextual poses for scene_tags=%s lighting_tags=%s genders=%s",
            scene_tags,
            lighting_tags,
            genders,
        )
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            select_cols = (
                "pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, "
                "created_at, gender, pose_image_base64"
            )

            score_parts = []
            score_params = []
            for tag in scene_tags or []:
                clause, params = self._tag_match_clause("scene_tag", tag)
                score_parts.append(f"CASE WHEN {clause} THEN 1 ELSE 0 END")
                score_params.extend(params)
            for tag in lighting_tags or []:
                clause, params = self._tag_match_clause("lighting_tag", tag)
                score_parts.append(f"CASE WHEN {clause} THEN 1 ELSE 0 END")
                score_params.extend(params)

            score_expr = " + ".join(score_parts) if score_parts else "0"
            sql = f"SELECT {select_cols}, ({score_expr}) AS match_score FROM pose_library"

            where_clauses = []
            where_params = []

            if scene_tags:
                scene_match_clauses = []
                for tag in scene_tags:
                    clause, params = self._tag_match_clause("scene_tag", tag)
                    scene_match_clauses.append(clause)
                    where_params.extend(params)
                where_clauses.append("(" + " OR ".join(scene_match_clauses) + ")")

            if lighting_tags:
                lighting_match_clauses = []
                for tag in lighting_tags:
                    clause, params = self._tag_match_clause("lighting_tag", tag)
                    lighting_match_clauses.append(clause)
                    where_params.extend(params)
                where_clauses.append("(" + " OR ".join(lighting_match_clauses) + ")")

            if genders:
                normalized = [g.strip().lower() for g in genders if str(g).strip()]
                if normalized:
                    placeholders = ", ".join(["%s"] * len(normalized))
                    where_clauses.append(f"LOWER(COALESCE(gender, '')) IN ({placeholders})")
                    where_params.extend(normalized)

            params = score_params
            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)
                params.extend(where_params)

            sql += " ORDER BY match_score DESC, RAND() LIMIT %s"
            params.append(limit)

            cursor.execute(sql, tuple(params))
            poses = cursor.fetchall()
            logger.info(
                "Contextual suggested poses fetched count=%s details=%s",
                len(poses),
                _summarize_poses(poses),
            )
            return poses
        finally:
            cursor.close()
            conn.close()

    def get_suggestions(self, tags: List[str]) -> List[Dict]:
        logger.info(f"Fetching poses for tags: {tags}")
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Build SQL for scene_tag and lighting_tag
            sql = "SELECT pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, created_at, gender, pose_image_base64 FROM pose_library"
            params = []
            if tags:
                tag_clauses = []
                for tag in tags:
                    tag_clauses.append("scene_tag = %s")
                    params.append(tag)
                    tag_clauses.append("lighting_tag = %s")
                    params.append(tag)
                    tag_clauses.append("FIND_IN_SET(%s, REPLACE(COALESCE(scene_tag, ''), ' ', '')) > 0")
                    params.append(tag)
                    tag_clauses.append("FIND_IN_SET(%s, REPLACE(COALESCE(lighting_tag, ''), ' ', '')) > 0")
                    params.append(tag)
                sql += " WHERE " + " OR ".join(tag_clauses)
            sql += " LIMIT 20"
            cursor.execute(sql, tuple(params))
            poses = cursor.fetchall()
            logger.info(
                "Suggested poses fetched count=%s details=%s",
                len(poses),
                _summarize_poses(poses),
            )
            return poses
        finally:
            cursor.close()
            conn.close()

    def get_random_poses(self, n: int, genders: List[str] = None) -> List[Dict]:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = "SELECT pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, created_at, gender, pose_image_base64 FROM pose_library"
            params = []
            if genders:
                normalized = [g.strip().lower() for g in genders if str(g).strip()]
                if normalized:
                    placeholders = ", ".join(["%s"] * len(normalized))
                    sql += f" WHERE LOWER(COALESCE(gender, '')) IN ({placeholders})"
                    params.extend(normalized)
            sql += " ORDER BY RAND() LIMIT %s"
            params.append(n)
            cursor.execute(sql, tuple(params))
            poses = cursor.fetchall()
            logger.info(
                "Random fallback poses fetched count=%s details=%s",
                len(poses),
                _summarize_poses(poses),
            )
            return poses
        finally:
            cursor.close()
            conn.close()


pose_service = PoseService()

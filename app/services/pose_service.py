from typing import List, Dict
import logging
from app.utils.db import get_db_connection

logger = logging.getLogger(__name__)

TAG_ALIASES = {
    "goldenhour": "golden_hour",
    "golden-hour": "golden_hour",
    "golden hour": "golden_hour",
    "well_lit": "midday",
    "well-lit": "midday",
}

class PoseService:
    """Fetch pose suggestions from pose_library table."""

    def _normalize_tags(self, tags: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()

        for raw_tag in tags or []:
            tag = str(raw_tag or "").strip().lower().replace("-", "_").replace(" ", "_")
            if not tag:
                continue
            tag = TAG_ALIASES.get(tag, tag)
            if tag in seen:
                continue
            seen.add(tag)
            normalized.append(tag)

        return normalized

    def _normalize_gender(self, value: str) -> str:
        return str(value or "").strip().lower()

    def _fetch_fillers_for_gender(self, cursor, gender: str, exclude_pose_ids: set, limit: int = 10) -> List[Dict]:
        if limit <= 0:
            return []

        sql = """
            SELECT
                pose_id,
                pose_image,
                description,
                skeleton_data,
                scene_tag,
                lighting_tag,
                created_at,
                gender,
                pose_image_base64,
                0 AS match_score
            FROM pose_library
            WHERE LOWER(gender) = %s
        """
        params: List = [gender]

        if exclude_pose_ids:
            placeholders = ", ".join(["%s"] * len(exclude_pose_ids))
            sql += f" AND pose_id NOT IN ({placeholders})"
            params.extend(list(exclude_pose_ids))

        sql += " ORDER BY RAND() LIMIT %s"
        params.append(limit)

        cursor.execute(sql, tuple(params))
        return cursor.fetchall()

    def _balance_genders(self, poses: List[Dict], cursor) -> List[Dict]:
        if not poses:
            return poses

        pose_ids = {row.get("pose_id") for row in poses if row.get("pose_id") is not None}
        females = [row for row in poses if self._normalize_gender(row.get("gender")) == "female"]
        males = [row for row in poses if self._normalize_gender(row.get("gender")) == "male"]
        others = [
            row
            for row in poses
            if self._normalize_gender(row.get("gender")) not in {"female", "male"}
        ]

        if not males:
            male_fillers = self._fetch_fillers_for_gender(cursor, "male", pose_ids, limit=10)
            males.extend(male_fillers)
            pose_ids.update({row.get("pose_id") for row in male_fillers if row.get("pose_id") is not None})

        if not females:
            female_fillers = self._fetch_fillers_for_gender(cursor, "female", pose_ids, limit=10)
            females.extend(female_fillers)

        balanced: List[Dict] = []
        max_len = max(len(females), len(males))
        for index in range(max_len):
            if index < len(females):
                balanced.append(females[index])
            if index < len(males):
                balanced.append(males[index])

        balanced.extend(others)
        return balanced

    def get_suggestions(self, tags: List[str]) -> List[Dict]:
        normalized_tags = self._normalize_tags(tags)
        logger.info(f"Fetching poses for tags: {tags} normalized={normalized_tags}")

        if not normalized_tags:
            return self.get_random_poses(20)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            score_terms = []
            where_terms = []
            score_params = []
            where_params = []

            for tag in normalized_tags:
                score_terms.extend([
                    "CASE WHEN scene_tag = %s THEN 3 ELSE 0 END",
                    "CASE WHEN lighting_tag = %s THEN 3 ELSE 0 END",
                    "CASE WHEN FIND_IN_SET(%s, scene_tag) > 0 THEN 2 ELSE 0 END",
                    "CASE WHEN FIND_IN_SET(%s, lighting_tag) > 0 THEN 2 ELSE 0 END",
                ])
                where_terms.extend([
                    "scene_tag = %s",
                    "lighting_tag = %s",
                    "FIND_IN_SET(%s, scene_tag) > 0",
                    "FIND_IN_SET(%s, lighting_tag) > 0",
                ])
                score_params.extend([tag, tag, tag, tag])
                where_params.extend([tag, tag, tag, tag])

            sql = f"""
                SELECT
                    pose_id,
                    pose_image,
                    description,
                    skeleton_data,
                    scene_tag,
                    lighting_tag,
                    created_at,
                    gender,
                    pose_image_base64,
                    ({" + ".join(score_terms)}) AS match_score
                FROM pose_library
                WHERE {" OR ".join(where_terms)}
                ORDER BY match_score DESC, created_at DESC
            """
            params = score_params + where_params
            cursor.execute(sql, tuple(params))
            poses = cursor.fetchall()
            if poses:
                return self._balance_genders(poses, cursor)

            return self._balance_genders(self.get_random_poses(20), cursor)
        finally:
            cursor.close()
            conn.close()

    def get_random_poses(self, n: int) -> List[Dict]:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = "SELECT pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, created_at, gender, pose_image_base64 FROM pose_library ORDER BY RAND() LIMIT %s"
            cursor.execute(sql, (n,))
            poses = cursor.fetchall()
            return poses
        finally:
            cursor.close()
            conn.close()


pose_service = PoseService()

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

    def _normalize_requested_gender(self, value: str) -> str:
        gender = str(value or "").strip().lower()
        if gender in {"male", "female", "unisex"}:
            return gender
        return ""

    def _get_recent_pose_ids(self, cursor, user_id: str, limit: int) -> set:
        if not user_id or limit <= 0:
            return set()

        cursor.execute(
            """
            SELECT pose_id
            FROM pose_selection
            WHERE user_id = %s
            ORDER BY selected_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        )
        rows = cursor.fetchall() or []
        return {row.get("pose_id") for row in rows if row.get("pose_id") is not None}

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

    def _balance_genders(self, poses: List[Dict], cursor, exclude_pose_ids: set = None) -> List[Dict]:
        if not poses:
            return poses

        pose_ids = set(exclude_pose_ids or set())
        pose_ids.update({row.get("pose_id") for row in poses if row.get("pose_id") is not None})
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

    def get_suggestions(
        self,
        tags: List[str],
        user_id: str = None,
        avoid_recent_limit: int = 20,
        gender: str = None,
    ) -> List[Dict]:
        normalized_tags = self._normalize_tags(tags)
        normalized_gender = self._normalize_requested_gender(gender)
        logger.info(
            f"Fetching poses for tags: {tags} normalized={normalized_tags} gender={normalized_gender or 'any'}"
        )

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            excluded_pose_ids = self._get_recent_pose_ids(cursor, user_id, avoid_recent_limit)

            if not normalized_tags:
                return self.get_random_poses(
                    20,
                    exclude_pose_ids=excluded_pose_ids,
                    gender=normalized_gender,
                )

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
            """
            params = score_params + where_params

            if normalized_gender:
                if normalized_gender == "unisex":
                    sql += " AND LOWER(gender) = %s"
                    params.append("unisex")
                else:
                    sql += " AND LOWER(gender) IN (%s, %s)"
                    params.extend([normalized_gender, "unisex"])

            if excluded_pose_ids:
                placeholders = ", ".join(["%s"] * len(excluded_pose_ids))
                sql += f" AND pose_id NOT IN ({placeholders})"
                params.extend(list(excluded_pose_ids))

            sql += " ORDER BY match_score DESC, RAND(), created_at DESC"

            cursor.execute(sql, tuple(params))
            poses = cursor.fetchall()
            if poses:
                if normalized_gender:
                    return poses
                return self._balance_genders(poses, cursor, exclude_pose_ids=excluded_pose_ids)

            random_poses = self.get_random_poses(
                20,
                exclude_pose_ids=excluded_pose_ids,
                gender=normalized_gender,
            )
            if normalized_gender:
                return random_poses

            return self._balance_genders(random_poses, cursor, exclude_pose_ids=excluded_pose_ids)
        finally:
            cursor.close()
            conn.close()

    def get_suggestions_by_pose_labels(
        self,
        pose_labels: List[str],
        user_id: str = None,
        avoid_recent_limit: int = 20,
        gender: str = None,
        limit: int = 20,
    ) -> List[Dict]:
        normalized_labels = self._normalize_tags(pose_labels)
        normalized_gender = self._normalize_requested_gender(gender)
        if not normalized_labels:
            return []

        logger.info(
            f"Fetching poses for pose-label predictions: {pose_labels} "
            f"normalized={normalized_labels} gender={normalized_gender or 'any'}"
        )

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            excluded_pose_ids = self._get_recent_pose_ids(cursor, user_id, avoid_recent_limit)

            score_terms = []
            where_terms = []
            score_params = []
            where_params = []

            for label in normalized_labels:
                like_raw = f"%{label}%"
                like_spaced = f"%{label.replace('_', ' ')}%"
                like_image = f"%{label.replace('_', '')}%"

                score_terms.extend([
                    "CASE WHEN REPLACE(LOWER(description), '-', '_') LIKE %s THEN 6 ELSE 0 END",
                    "CASE WHEN REPLACE(LOWER(description), ' ', '_') LIKE %s THEN 5 ELSE 0 END",
                    "CASE WHEN LOWER(description) LIKE %s THEN 4 ELSE 0 END",
                    "CASE WHEN LOWER(pose_image) LIKE %s THEN 2 ELSE 0 END",
                ])
                where_terms.extend([
                    "REPLACE(LOWER(description), '-', '_') LIKE %s",
                    "REPLACE(LOWER(description), ' ', '_') LIKE %s",
                    "LOWER(description) LIKE %s",
                    "LOWER(pose_image) LIKE %s",
                ])

                score_params.extend([like_raw, like_raw, like_spaced, like_image])
                where_params.extend([like_raw, like_raw, like_spaced, like_image])

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
            """
            params = score_params + where_params

            if normalized_gender:
                if normalized_gender == "unisex":
                    sql += " AND LOWER(gender) = %s"
                    params.append("unisex")
                else:
                    sql += " AND LOWER(gender) IN (%s, %s)"
                    params.extend([normalized_gender, "unisex"])

            if excluded_pose_ids:
                placeholders = ", ".join(["%s"] * len(excluded_pose_ids))
                sql += f" AND pose_id NOT IN ({placeholders})"
                params.extend(list(excluded_pose_ids))

            sql += " ORDER BY match_score DESC, RAND(), created_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(sql, tuple(params))
            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def get_random_poses(self, n: int, exclude_pose_ids: set = None, gender: str = None) -> List[Dict]:
        normalized_gender = self._normalize_requested_gender(gender)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            sql = "SELECT pose_id, pose_image, description, skeleton_data, scene_tag, lighting_tag, created_at, gender, pose_image_base64 FROM pose_library"
            params: List = []
            where_clauses: List[str] = []

            if normalized_gender:
                if normalized_gender == "unisex":
                    where_clauses.append("LOWER(gender) = %s")
                    params.append("unisex")
                else:
                    where_clauses.append("LOWER(gender) IN (%s, %s)")
                    params.extend([normalized_gender, "unisex"])

            if exclude_pose_ids:
                placeholders = ", ".join(["%s"] * len(exclude_pose_ids))
                where_clauses.append(f"pose_id NOT IN ({placeholders})")
                params.extend(list(exclude_pose_ids))

            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)

            sql += " ORDER BY RAND() LIMIT %s"
            params.append(n)

            cursor.execute(sql, tuple(params))
            poses = cursor.fetchall()
            return poses
        finally:
            cursor.close()
            conn.close()


pose_service = PoseService()

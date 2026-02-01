from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class PoseService:
    """Interface to fetch pose suggestions. Should be implemented with persistence or external service."""

    def get_suggestions(self, tags: List[str]) -> List[Dict]:
        # Mocked mapping from tags to poses
        logger.info(f"Fetching poses for tags: {tags}")
        if not tags:
            return []
        # Example mocked poses
        poses = [
            {"id": "pose-001", "name": "Classic Pose", "keypoints": None, "thumbnail_url": None},
            {"id": "pose-002", "name": "Side Angle", "keypoints": None, "thumbnail_url": None},
        ]
        return poses


pose_service = PoseService()

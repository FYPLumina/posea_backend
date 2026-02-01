from typing import List, Dict
import numpy as np
import logging

logger = logging.getLogger(__name__)


class AIService:
    """Interface to a pre-trained TensorFlow model. Model loading is assumed to be implemented separately."""

    def __init__(self, model_path: str = None):
        self.model_path = model_path
        # In production, load model here. Keep lazy or via separate util.

    def classify(self, image_array: np.ndarray) -> List[Dict]:
        """Perform classification and return list of {tag, confidence}.

        This is a placeholder — integrate real TensorFlow inference in `classify`.
        """
        try:
            # Mocked classification for demonstration
            h, w, _ = image_array.shape
            logger.info(f"Received image for classification: {w}x{h}")
            return [
                {"tag": "well_lit", "confidence": 0.87},
                {"tag": "indoor", "confidence": 0.64},
            ]
        except Exception as e:
            logger.exception("AI classification failed")
            raise


ai_service = AIService()

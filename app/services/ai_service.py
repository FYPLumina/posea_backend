import os
from pathlib import Path
import threading
from typing import List, Dict, Optional
import numpy as np
import logging
import cv2

logger = logging.getLogger(__name__)


class AIService:
    """Interface to background classification model inference."""

    def __init__(self, model_path: str = None):
        base_dir = Path(__file__).resolve().parents[2]
        default_model_path = base_dir / "model" / "Background_classification_model03.h5"
        self.model_path = model_path or str(default_model_path)
        self._model = None
        self._tf = None
        self._load_lock = threading.Lock()

    def _load_model(self):
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model

            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"Background model file not found: {self.model_path}")

            try:
                import tensorflow as tf
            except Exception as exc:
                raise RuntimeError(
                    "TensorFlow is required for background classification but is not installed."
                ) from exc

            self._tf = tf
            self._model = tf.keras.models.load_model(self.model_path, compile=False)
            logger.info("Loaded background classification model from %s", self.model_path)
            return self._model

    @staticmethod
    def _normalize_to_01(batch: np.ndarray) -> np.ndarray:
        if batch.max() > 1.5:
            batch = batch / 255.0
        return np.clip(batch, 0.0, 1.0).astype("float32")

    def _prepare_input(self, image_array: np.ndarray, input_shape) -> np.ndarray:
        arr = np.asarray(image_array, dtype="float32")
        if arr.ndim == 3:
            arr = np.expand_dims(arr, axis=0)
        elif arr.ndim != 4:
            raise ValueError("Expected image with shape (H, W, C) or (N, H, W, C)")

        if isinstance(input_shape, list):
            input_shape = input_shape[0]

        if len(input_shape) >= 4:
            target_h = input_shape[1]
            target_w = input_shape[2]
            if target_h and target_w:
                resized = [cv2.resize(img, (int(target_w), int(target_h))) for img in arr]
                arr = np.stack(resized, axis=0)

        arr = self._normalize_to_01(arr)
        return arr

    @staticmethod
    def _get_labels(output_dim: int) -> List[str]:
        raw_map = os.getenv("BG_MODEL_LABEL_MAP", "").strip()
        if raw_map:
            labels = [f"class_{idx}" for idx in range(output_dim)]
            parsed_count = 0
            for part in raw_map.split(","):
                item = part.strip()
                if not item or ":" not in item:
                    continue
                idx_text, label = item.split(":", 1)
                idx_text = idx_text.strip().replace("class_", "")
                label = label.strip()
                if not idx_text.isdigit() or not label:
                    continue
                idx = int(idx_text)
                if 0 <= idx < output_dim:
                    labels[idx] = label
                    parsed_count += 1

            if parsed_count > 0:
                logger.info(
                    "Using BG_MODEL_LABEL_MAP for %s/%s classes",
                    parsed_count,
                    output_dim,
                )
                return labels

            logger.warning(
                "BG_MODEL_LABEL_MAP is set but no valid mappings were parsed. Falling back to BG_MODEL_LABELS/defaults."
            )

        raw = os.getenv("BG_MODEL_LABELS", "").strip()
        if raw:
            labels = [item.strip() for item in raw.split(",") if item.strip()]
            if len(labels) == output_dim:
                return labels
            logger.warning(
                "BG_MODEL_LABELS count (%s) does not match model output_dim (%s). Falling back to defaults.",
                len(labels),
                output_dim,
            )

        if output_dim == 2:
            return ["indoor", "outdoor"]
        if output_dim == 4:
            return ["indoor", "outdoor", "well_lit", "low_light"]
        if output_dim == 8:
            return [
                "beach",
                "sea",
                "horizon",
                "vegetation",
                "golden_hour",
                "midday",
                "overcast",
                "other_negative",
            ]
        logger.warning(
            "Model output has %s classes but BG_MODEL_LABELS is not configured. Using generic class labels.",
            output_dim,
        )
        return [f"class_{idx}" for idx in range(output_dim)]

    def classify(self, image_array: np.ndarray) -> List[Dict]:
        """Perform model inference and return list of {tag, confidence}."""
        try:
            model = self._load_model()
            batch = self._prepare_input(image_array, model.input_shape)

            preds = model.predict(batch, verbose=0)
            if isinstance(preds, list):
                preds = preds[0]

            sample = np.asarray(preds[0]).reshape(-1)
            if sample.size == 1:
                positive = float(np.clip(sample[0], 0.0, 1.0))
                return [
                    {"tag": "outdoor", "confidence": positive},
                    {"tag": "indoor", "confidence": 1.0 - positive},
                ]

            labels = self._get_labels(sample.size)
            raw_threshold = os.getenv("BG_MODEL_PRED_THRESHOLD", "0.5").strip()
            try:
                threshold = float(raw_threshold)
            except (TypeError, ValueError):
                threshold = 0.5

            threshold = max(0.0, min(1.0, threshold))

            results = []
            for idx, score in enumerate(sample):
                confidence = float(score)
                if confidence >= threshold:
                    results.append(
                        {
                            "tag": labels[int(idx)],
                            "confidence": confidence,
                        }
                    )

            results.sort(key=lambda item: item["confidence"], reverse=True)

            if not results:
                best_idx = int(np.argmax(sample))
                results = [
                    {
                        "tag": labels[best_idx],
                        "confidence": float(sample[best_idx]),
                    }
                ]

            logger.info(
                "Background multi-label classification produced %d tags with threshold=%s",
                len(results),
                threshold,
            )
            return results
        except Exception:
            logger.exception("AI classification failed")
            raise


ai_service = AIService()

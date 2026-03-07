from typing import List, Dict, Optional
from pathlib import Path
import os
import numpy as np
import cv2
import logging

logger = logging.getLogger(__name__)


class AIService:
    """TensorFlow-backed classifier for background tags."""

    def __init__(self, model_path: str = None, pose_model_path: str = None):
        default_background_model_path = Path(__file__).resolve().parents[1] / "models" / "Background_classification_model03.h5"
        env_background_model_path = os.getenv("BACKGROUND_MODEL_PATH")

        default_pose_model_path = Path(__file__).resolve().parents[1] / "models" / "pose_suggestion_model_with_10Poses.h5"
        env_pose_model_path = os.getenv("POSE_SUGGESTION_MODEL_PATH")

        self.model_path = Path(model_path or env_background_model_path or default_background_model_path)
        self.pose_model_path = Path(pose_model_path or env_pose_model_path or default_pose_model_path)

        self.class_names = self._load_class_names(self.model_path, "BACKGROUND_MODEL_LABELS")
        self.pose_class_names = self._load_class_names(self.pose_model_path, "POSE_SUGGESTION_MODEL_LABELS")

        self.model = None
        self.pose_model = None
        self.input_size = (512, 512)
        self.pose_input_size = (512, 512)

        self._load_background_model()
        self._load_pose_model()

    def _load_class_names(self, model_path: Path, env_var_name: str) -> Optional[List[str]]:
        labels_from_env = os.getenv(env_var_name, "").strip()
        if labels_from_env:
            labels = [x.strip() for x in labels_from_env.split(",") if x.strip()]
            if labels:
                return labels

        labels_file = model_path.with_suffix(".labels.txt")
        if labels_file.exists():
            labels = [line.strip() for line in labels_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if labels:
                return labels

        return None

    def _extract_input_size(self, model, fallback_size: tuple[int, int]) -> tuple[int, int]:
        input_shape = getattr(model, "input_shape", None)
        if isinstance(input_shape, (list, tuple)) and input_shape:
            if isinstance(input_shape[0], (list, tuple)):
                input_shape = input_shape[0]
            if len(input_shape) >= 3 and input_shape[-1] in (1, 3, 4):
                h, w = input_shape[1], input_shape[2]
                if isinstance(h, int) and isinstance(w, int):
                    return (h, w)

        return fallback_size

    def _load_background_model(self) -> None:
        if not self.model_path.exists():
            logger.warning(f"Model file not found at {self.model_path}. Falling back to default tags.")
            return

        try:
            import tensorflow as tf

            self.model = tf.keras.models.load_model(str(self.model_path), compile=False)
            self.input_size = self._extract_input_size(self.model, self.input_size)

            logger.info(f"Loaded background model from {self.model_path} with input size {self.input_size}")
        except Exception:
            logger.exception("Failed to load TensorFlow model. Falling back to default tags.")
            self.model = None

    def _load_pose_model(self) -> None:
        if not self.pose_model_path.exists():
            logger.warning(f"Pose suggestion model file not found at {self.pose_model_path}.")
            return

        try:
            import tensorflow as tf

            self.pose_model = tf.keras.models.load_model(str(self.pose_model_path), compile=False)
            self.pose_input_size = self._extract_input_size(self.pose_model, self.pose_input_size)

            logger.info(
                f"Loaded pose suggestion model from {self.pose_model_path} "
                f"with input size {self.pose_input_size}"
            )
        except Exception:
            logger.exception("Failed to load pose suggestion model.")
            self.pose_model = None

    def _prepare_input(self, image_array: np.ndarray, input_size: tuple[int, int]) -> np.ndarray:
        if image_array is None or image_array.ndim != 3:
            raise ValueError("Expected image_array with shape [H, W, C]")

        img = image_array.astype("float32")
        if img.max() > 1.0:
            img = img / 255.0

        target_h, target_w = input_size
        if img.shape[0] != target_h or img.shape[1] != target_w:
            img = cv2.resize(img, (target_w, target_h))

        return np.expand_dims(img, axis=0)

    def _to_probabilities(self, raw_output: np.ndarray) -> np.ndarray:
        probs = np.asarray(raw_output, dtype="float32").squeeze()
        if probs.ndim == 0:
            probs = np.array([float(probs)], dtype="float32")
        if probs.ndim > 1:
            probs = probs.reshape(-1)

        if probs.size > 1:
            probs_sum = float(np.sum(probs))
            if float(np.min(probs)) < 0.0 or float(np.max(probs)) > 1.0 or abs(probs_sum - 1.0) > 0.15:
                exps = np.exp(probs - np.max(probs))
                probs = exps / np.sum(exps)

        return probs

    def classify(self, image_array: np.ndarray) -> List[Dict]:
        """Perform classification and return list of {tag, confidence}."""
        try:
            h, w, _ = image_array.shape
            logger.info(f"Received image for classification: {w}x{h}")

            if self.model is None:
                logger.info("Model unavailable. Returning fallback classification tags.")
                return [
                    {"tag": "well_lit", "confidence": 0.87},
                    {"tag": "indoor", "confidence": 0.64},
                ]

            batch = self._prepare_input(image_array, self.input_size)
            logger.info(f"Prepared input batch with shape={batch.shape}, dtype={batch.dtype}")
            raw = self.model.predict(batch, verbose=0)
            probs = self._to_probabilities(raw)

            raw_np = np.asarray(raw)
            logger.info(
                "Model raw output summary: "
                f"shape={raw_np.shape}, min={float(np.min(raw_np)):.6f}, max={float(np.max(raw_np)):.6f}"
            )
            logger.info(
                "Probability summary: "
                f"count={len(probs)}, sum={float(np.sum(probs)):.6f}, "
                f"min={float(np.min(probs)):.6f}, max={float(np.max(probs)):.6f}"
            )

            if self.class_names and len(self.class_names) == len(probs):
                labels = self.class_names
            else:
                labels = [f"class_{idx}" for idx in range(len(probs))]

            top_k = min(5, len(probs))
            top_indices = np.argsort(probs)[::-1][:top_k]
            predictions = [
                {"tag": labels[int(idx)], "confidence": float(round(float(probs[int(idx)]), 6))}
                for idx in top_indices
            ]
            logger.info(f"Top predictions: {predictions}")
            return predictions
        except Exception:
            logger.exception("AI classification failed")
            raise

    def suggest_poses(self, image_array: np.ndarray, top_k: int = 10) -> List[Dict]:
        """Predict pose labels from the uploaded background image."""
        try:
            if self.pose_model is None:
                logger.info("Pose suggestion model unavailable. Returning empty pose predictions.")
                return []

            batch = self._prepare_input(image_array, self.pose_input_size)
            raw = self.pose_model.predict(batch, verbose=0)
            probs = self._to_probabilities(raw)

            if self.pose_class_names and len(self.pose_class_names) == len(probs):
                labels = self.pose_class_names
            else:
                labels = [f"pose_class_{idx}" for idx in range(len(probs))]

            top_k = max(1, min(top_k, len(probs)))
            top_indices = np.argsort(probs)[::-1][:top_k]
            predictions = [
                {
                    "tag": labels[int(idx)],
                    "confidence": float(round(float(probs[int(idx)]), 6)),
                }
                for idx in top_indices
            ]

            logger.info(f"Pose model top predictions: {predictions}")
            return predictions
        except Exception:
            logger.exception("Pose suggestion inference failed")
            raise


ai_service = AIService()

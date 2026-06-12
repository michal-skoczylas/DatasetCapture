import os
import sys
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
from mediapipe import Image as MpImage
from mediapipe import ImageFormat
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import HandLandmarker
from mediapipe.tasks.python.vision import HandLandmarkerOptions
from mediapipe.tasks.python.vision import RunningMode


MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)

CACHE_DIR = Path.home() / ".dataset_capture" / "models"


def _ensure_model(path=None):
    if path is None:
        path = CACHE_DIR / "hand_landmarker.task"
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            urlretrieve(MODEL_URL, path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to download hand detection model.\n"
                f"Download it manually from:\n{MODEL_URL}\n"
                f"and save as:\n{path}\n\n"
                f"Error: {e}"
            ) from e
    return str(path)


class HandDetector:
    def __init__(self, min_detection_confidence=0.5, max_num_hands=2):
        model_path = _ensure_model()
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.IMAGE,
            num_hands=max_num_hands,
            min_hand_detection_confidence=min_detection_confidence,
        )
        self._detector = HandLandmarker.create_from_options(options)

    def detect(self, pil_image):
        rgb = pil_image.convert("RGB")
        rgb_np = np.array(rgb)
        mp_image = MpImage(image_format=ImageFormat.SRGB, data=rgb_np)
        result = self._detector.detect(mp_image)

        bboxes = []
        if result.hand_landmarks:
            for landmarks in result.hand_landmarks:
                xs = [lm.x for lm in landmarks]
                ys = [lm.y for lm in landmarks]

                x_min = max(0.0, min(xs))
                x_max = min(1.0, max(xs))
                y_min = max(0.0, min(ys))
                y_max = min(1.0, max(ys))

                pad_x = (x_max - x_min) * 0.10
                pad_y = (y_max - y_min) * 0.10

                bboxes.append({
                    "x1": max(0.0, x_min - pad_x),
                    "y1": max(0.0, y_min - pad_y),
                    "x2": min(1.0, x_max + pad_x),
                    "y2": min(1.0, y_max + pad_y),
                    "confidence": 1.0,
                })

        return bboxes

    def close(self):
        self._detector.close()

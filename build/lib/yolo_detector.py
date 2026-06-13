import os
import warnings

os.environ["ULTRALYTICS_NO_AUTO_UPDATE"] = "1"
os.environ["ULTRALYTICS_ALLOW_REQUIREMENTS"] = "0"

warnings.filterwarnings("ignore", category=UserWarning, module="ultralytics")

from ultralytics import YOLO


class YoloDetector:
    def __init__(self, model_path, confidence=0.3, iou_threshold=0.5, imgsz=640):
        self._model = YOLO(model_path, verbose=False)
        self._conf = confidence
        self._iou = iou_threshold
        self._imgsz = imgsz
        self._class_names = ["OpenHand", "ClosedHand"]

    @property
    def class_names(self):
        return self._class_names

    def detect(self, pil_image):
        img = pil_image.convert("RGB") if pil_image.mode == "L" else pil_image
        results = self._model(
            img, conf=self._conf, iou=self._iou,
            imgsz=self._imgsz, verbose=False
        )

        bboxes = []
        boxes = results[0].boxes
        if boxes is not None and len(boxes) > 0:
            img_w, img_h = img.size
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                bboxes.append({
                    "x1": x1 / img_w,
                    "y1": y1 / img_h,
                    "x2": x2 / img_w,
                    "y2": y2 / img_h,
                    "confidence": float(box.conf[0].item()),
                    "class_id": int(box.cls[0].item()),
                })

        return bboxes

    def close(self):
        pass

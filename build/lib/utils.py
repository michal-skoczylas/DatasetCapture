import json
import os
from pathlib import Path

from protocol import DEFAULT_BAUD, DEFAULT_DURATION, DEFAULT_RESOLUTION, RESOLUTIONS

CONFIG_FILE = Path.home() / ".dataset_capture" / "config.json"

DEFAULT_CONFIG = {
    "last_port": "",
    "last_baud": DEFAULT_BAUD,
    "last_directory": str(Path.home() / "dataset"),
    "last_resolution": DEFAULT_RESOLUTION,
    "auto_resize": False,
    "last_duration": DEFAULT_DURATION,
    "class_history": [],
    "hand_detection_enabled": False,
    "min_detection_confidence": 0.2,
    "detector_type": "mediapipe",
    "yolo_model_path": "",
    "yolo_confidence": 0.3,
    "yolo_iou_threshold": 0.5,
}


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(saved)
                return cfg
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        os.makedirs(CONFIG_FILE.parent, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except IOError:
        pass


def get_next_index(directory):
    if not os.path.isdir(directory):
        return 1
    max_idx = 0
    for fname in os.listdir(directory):
        if fname.endswith(".jpg"):
            try:
                idx = int(os.path.splitext(fname)[0])
                max_idx = max(max_idx, idx)
            except ValueError:
                pass
    return max_idx + 1


def sanitize_class_name(name):
    keep = {"_", "-"}
    cleaned = "".join(c if c.isalnum() or c in keep else "_" for c in name)
    return cleaned.strip("_") or "unknown"


def parse_resolution(text):
    text = text.strip()
    if text in RESOLUTIONS:
        return RESOLUTIONS[text]

    import re
    m = re.match(r'^\s*(\d{1,5})\s*[×xX,\s]\s*(\d{1,5})\s*$', text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w < 1 or h < 1:
            raise ValueError(f"Invalid resolution: {text}")
        return w, h

    raise ValueError(f"Unrecognized resolution format: {text}")


def count_images(directory):
    if not os.path.isdir(directory):
        return 0
    return sum(1 for f in os.listdir(directory) if f.endswith(".jpg"))


def renumber_images(directory, start=0):
    if not os.path.isdir(directory):
        return 0

    files = [f for f in os.listdir(directory) if f.endswith(".jpg")]
    n = len(files)
    if n == 0:
        return 0

    def sort_key(fname):
        try:
            return (0, int(os.path.splitext(fname)[0]))
        except ValueError:
            return (1, fname)

    files.sort(key=sort_key)

    tmp_prefix = "_rn_tmp_"
    for i, old_name in enumerate(files):
        old_path = os.path.join(directory, old_name)
        tmp_path = os.path.join(directory, f"{tmp_prefix}{i}.tmp")
        os.rename(old_path, tmp_path)

    for i in range(n):
        tmp_path = os.path.join(directory, f"{tmp_prefix}{i}.tmp")
        new_path = os.path.join(directory, f"{start + i:04d}.jpg")
        os.rename(tmp_path, new_path)

    for fname in os.listdir(directory):
        if fname.startswith(tmp_prefix) and fname.endswith(".tmp"):
            try:
                os.remove(os.path.join(directory, fname))
            except OSError:
                pass

    return n


def save_yolo_label(image_path, bboxes, class_id):
    label_path = os.path.splitext(image_path)[0] + ".txt"

    lines = []
    for bbox in bboxes:
        cx = (bbox["x1"] + bbox["x2"]) / 2.0
        cy = (bbox["y1"] + bbox["y2"]) / 2.0
        bw = bbox["x2"] - bbox["x1"]
        bh = bbox["y2"] - bbox["y1"]
        lines.append(f"{class_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

    with open(label_path, "w") as f:
        f.write("\n".join(lines) + "\n")


def save_classes_txt(base_dir, class_names):
    classes_path = os.path.join(base_dir, "classes.txt")
    existing = []
    if os.path.isfile(classes_path):
        with open(classes_path) as f:
            existing = [line.strip() for line in f if line.strip()]
    class_set = set(class_names)
    result = [name for name in existing if name in class_set]
    seen = set(result)
    for name in class_names:
        if name not in seen:
            result.append(name)
            seen.add(name)
    with open(classes_path, "w") as f:
        f.write("\n".join(result) + "\n")


def get_class_id(base_dir, class_name):
    classes_path = os.path.join(base_dir, "classes.txt")
    if os.path.isfile(classes_path):
        with open(classes_path) as f:
            classes = [line.strip() for line in f if line.strip()]
        if class_name in classes:
            return classes.index(class_name)

    try:
        subdirs = sorted(
            [
                e
                for e in os.listdir(base_dir)
                if not e.startswith(".") and os.path.isdir(os.path.join(base_dir, e))
            ],
            key=str.lower,
        )
    except OSError:
        subdirs = []

    if class_name in subdirs:
        return subdirs.index(class_name)

    return 0


def load_yolo_labels(txt_path):
    if not os.path.isfile(txt_path):
        return []
    labels = []
    with open(txt_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 5:
                try:
                    labels.append({
                        "class_id": int(parts[0]),
                        "cx": float(parts[1]),
                        "cy": float(parts[2]),
                        "bw": float(parts[3]),
                        "bh": float(parts[4]),
                    })
                except ValueError:
                    continue
    return labels


def load_classes_txt(base_dir):
    classes_path = os.path.join(base_dir, "classes.txt")
    if not os.path.isfile(classes_path):
        return []
    with open(classes_path) as f:
        return [line.strip() for line in f if line.strip()]

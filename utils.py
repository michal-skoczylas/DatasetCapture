import json
import os
from pathlib import Path

from protocol import DEFAULT_BAUD, DEFAULT_DURATION, DEFAULT_RESOLUTION, MAX_CLASS_HISTORY, RESOLUTIONS

CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "last_port": "",
    "last_baud": DEFAULT_BAUD,
    "last_directory": str(Path.home() / "dataset"),
    "last_resolution": DEFAULT_RESOLUTION,
    "auto_resize": False,
    "last_duration": DEFAULT_DURATION,
    "class_history": [],
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


def update_class_history(history, class_name):
    if class_name in history:
        history.remove(class_name)
    history.insert(0, class_name)
    return history[:MAX_CLASS_HISTORY]


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

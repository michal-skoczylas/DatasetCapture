import json
import os
from pathlib import Path

from protocol import DEFAULT_BAUD, DEFAULT_DURATION, DEFAULT_RESOLUTION, RESOLUTIONS

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

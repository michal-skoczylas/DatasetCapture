import os
import queue
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

import tkinter as tk
from PIL import Image, ImageTk

from detection_worker import DetectionWorker
from hand_detector import HandDetector
from yolo_detector import YoloDetector
from review_window import ReviewWindow
from protocol import (
    BAUD_RATES,
    DEFAULT_BAUD,
    DEFAULT_DURATION,
    DEFAULT_RESOLUTION,
    FRAME_HEIGHT,
    FRAME_SIZE,
    FRAME_WIDTH,
    JPEG_QUALITY,
    PREVIEW_SIZE,
    RESOLUTIONS,
    POLL_INTERVAL_MS,
)
from serial_handler import SerialHandler
from utils import (
    count_images,
    get_class_id,
    get_next_index,
    load_classes_txt,
    load_config,
    parse_resolution,
    renumber_images,
    sanitize_class_name,
    save_classes_txt,
    save_config,
    save_yolo_label,
)


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Dataset Capture Tool")
        self.root.geometry("800x680")
        self.root.minsize(720, 560)
        self.root.configure(bg="#f0f0f0")

        self.config = load_config()
        self.serial = SerialHandler()

        self.capturing = False
        self.capture_start_time = 0.0
        self.capture_count = 0
        self.capture_duration = 0.0
        self.capture_next_idx = 1
        self.capture_save_dir = ""
        self.capture_w = 324
        self.capture_h = 244
        self.auto_resize = False
        self._capture_timer_id = None
        self._countdown_after_id = None
        self._preview_photo = None
        self._renumbered_dirs = set()

        self._hand_detector = None
        self._detection_worker = None
        self._detection_enabled = False
        self._detection_confidence = 0.2
        self._detection_class_id = 0
        self._review_window = None
        self._redetect_after_id = None
        self._detection_progress_after_id = None
        self._pending_detection = []

        self._detector_type = "mediapipe"
        self._yolo_model_path = ""
        self._yolo_confidence = 0.3
        self._yolo_iou = 0.5

        self._build_ui()
        self._setup_listbox_hover()
        self._restore_config()
        self._poll_frames()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self.stop_capture_or_disconnect())

    def _build_ui(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TLabelframe.Label", font=("Helvetica", 11, "bold"))

        main = ttk.Frame(self.root, padding=(12, 10))
        main.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(main)
        top.pack(fill=tk.X, pady=(0, 10))

        self._build_settings(top)
        self._build_preview(top)
        self._build_capture(main)
        self._build_log(main)

    def _build_settings(self, parent):
        frame = ttk.LabelFrame(parent, text=" Settings ", padding=10)
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        r = ttk.Frame(frame)
        r.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(r, text="Port:", width=5).pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(r, textvariable=self.port_var, width=18, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.port_combo.bind("<Button-1>", lambda e: self._refresh_ports())
        ttk.Label(r, text="Baud:", width=5).pack(side=tk.LEFT)
        self.baud_var = tk.StringVar(value=str(DEFAULT_BAUD))
        self.baud_combo = ttk.Combobox(
            r, textvariable=self.baud_var, width=10,
            state="readonly", values=[str(b) for b in BAUD_RATES]
        )
        self.baud_combo.pack(side=tk.LEFT)
        ttk.Button(r, text="↻", width=3, command=self._refresh_ports).pack(side=tk.LEFT, padx=(5, 0))

        r2 = ttk.Frame(frame)
        r2.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(r2, text="Res:", width=5).pack(side=tk.LEFT)
        self.res_var = tk.StringVar(value=DEFAULT_RESOLUTION)
        self.res_combo = ttk.Combobox(
            r2, textvariable=self.res_var, width=18,
            values=list(RESOLUTIONS.keys())
        )
        self.res_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.auto_resize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(r2, text="Auto-resize", variable=self.auto_resize_var).pack(side=tk.LEFT)

        r3 = ttk.Frame(frame)
        r3.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(r3, text="Dir:", width=5).pack(side=tk.LEFT)
        self.dir_var = tk.StringVar()
        self.dir_entry = ttk.Entry(r3, textvariable=self.dir_var)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        ttk.Button(r3, text="Browse", command=self._browse_directory).pack(side=tk.LEFT)

        r4 = ttk.Frame(frame)
        r4.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(r4, text="Class:", width=5).pack(side=tk.LEFT)
        self.class_var = tk.StringVar()
        self.class_combo = ttk.Combobox(r4, textvariable=self.class_var, width=30)
        self.class_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.class_combo.bind("<KeyRelease>", self._on_class_change)
        self.class_combo.bind("<<ComboboxSelected>>", self._on_class_change)

        self.fix_txt_btn = ttk.Button(r4, text="Fix TXT Classes", command=self._fix_txt_classes, state=tk.DISABLED)
        self.fix_txt_btn.pack(side=tk.LEFT, padx=(5, 0))

        r5 = ttk.Frame(frame)
        r5.pack(fill=tk.X, pady=(0, 8))
        self.path_preview_var = tk.StringVar(value="→ (select directory and class)")
        ttk.Label(r5, textvariable=self.path_preview_var, foreground="#555").pack(side=tk.LEFT)
        self.class_count_var = tk.StringVar(value="")
        ttk.Label(r5, textvariable=self.class_count_var, foreground="#007bff", font=("Helvetica", 10, "bold")).pack(side=tk.RIGHT)

        r6 = ttk.Frame(frame)
        r6.pack(fill=tk.X)
        self.connect_btn = ttk.Button(r6, text="Connect", command=self._toggle_connect)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.status_var = tk.StringVar(value="● Disconnected")
        self.status_label = ttk.Label(r6, textvariable=self.status_var, foreground="#d00")
        self.status_label.pack(side=tk.LEFT)

    def _build_preview(self, parent):
        frame = ttk.LabelFrame(parent, text=" Live Preview ", padding=6)
        frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(10, 0))

        pw, ph = PREVIEW_SIZE
        self.preview_canvas = tk.Canvas(
            frame, width=pw, height=ph,
            bg="#1e1e1e", highlightthickness=0
        )
        self.preview_canvas.pack()
        self._preview_placeholder(pw, ph)

    def _preview_placeholder(self, w, h):
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(
            w / 2, h / 2, text="No image",
            fill="#555", font=("Helvetica", 14)
        )

    def _build_capture(self, parent):
        frame = ttk.LabelFrame(parent, text=" Capture ", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        r0 = ttk.Frame(frame)
        r0.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(r0, text="Duration:").pack(side=tk.LEFT)
        self.duration_var = tk.StringVar(value=str(DEFAULT_DURATION))
        self.duration_spin = ttk.Spinbox(
            r0, textvariable=self.duration_var,
            from_=1, to=300, width=5
        )
        self.duration_spin.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Label(r0, text="s").pack(side=tk.LEFT, padx=(0, 18))

        self.start_btn = ttk.Button(r0, text="▶ START CAPTURE", command=self.start_capture)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.stop_btn = ttk.Button(r0, text="■ STOP", command=self.stop_capture, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT)
        self.review_btn = ttk.Button(r0, text="Review", command=self._open_review, state=tk.DISABLED)
        self.review_btn.pack(side=tk.LEFT, padx=(8, 0))

        r_det = ttk.Frame(frame)
        r_det.pack(fill=tk.X, pady=(6, 4))
        self.detect_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            r_det, text="Enable hand detection",
            variable=self.detect_var, command=self._on_detection_toggle
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(r_det, text="Detector:").pack(side=tk.LEFT)
        self.detector_type_var = tk.StringVar(value="mediapipe")
        self.detector_combo = ttk.Combobox(
            r_det, textvariable=self.detector_type_var, width=14,
            values=["MediaPipe", "Custom YOLO"], state="readonly"
        )
        self.detector_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.detector_combo.bind("<<ComboboxSelected>>", self._on_detector_change)

        self.r_mp_ctrl = ttk.Frame(frame)
        self.r_mp_ctrl.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(self.r_mp_ctrl, text="Min conf:").pack(side=tk.LEFT)
        self.detect_conf_var = tk.StringVar(value="0.2")
        ttk.Combobox(
            self.r_mp_ctrl, textvariable=self.detect_conf_var, width=4,
            values=["0.1", "0.2", "0.3", "0.5", "0.7"], state="readonly"
        ).pack(side=tk.LEFT)
        self.clahe_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            self.r_mp_ctrl, text="CLAHE enhance", variable=self.clahe_var
        ).pack(side=tk.LEFT, padx=(12, 0))

        self.r_yolo_ctrl = ttk.Frame(frame)

        r_y1 = ttk.Frame(self.r_yolo_ctrl)
        r_y1.pack(fill=tk.X)
        ttk.Label(r_y1, text="Model:").pack(side=tk.LEFT)
        self.yolo_model_var = tk.StringVar()
        self.yolo_model_entry = ttk.Entry(r_y1, textvariable=self.yolo_model_var)
        self.yolo_model_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        ttk.Button(r_y1, text="Browse", command=self._browse_yolo_model).pack(side=tk.LEFT)

        r_y2 = ttk.Frame(self.r_yolo_ctrl)
        r_y2.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(r_y2, text="Conf:").pack(side=tk.LEFT)
        self.yolo_conf_var = tk.DoubleVar(value=0.3)
        ttk.Scale(
            r_y2, from_=0.1, to=0.9, variable=self.yolo_conf_var,
            orient=tk.HORIZONTAL, length=100
        ).pack(side=tk.LEFT, padx=4)
        self.yolo_conf_label = ttk.Label(r_y2, text="0.3", width=4)
        self.yolo_conf_label.pack(side=tk.LEFT)
        self.yolo_conf_var.trace_add("write", lambda *a: self.yolo_conf_label.config(
            text=f"{self.yolo_conf_var.get():.1f}"))
        ttk.Label(r_y2, text="  IOU:").pack(side=tk.LEFT, padx=(12, 0))
        self.yolo_iou_var = tk.DoubleVar(value=0.5)
        ttk.Scale(
            r_y2, from_=0.1, to=0.9, variable=self.yolo_iou_var,
            orient=tk.HORIZONTAL, length=100
        ).pack(side=tk.LEFT, padx=4)
        self.yolo_iou_label = ttk.Label(r_y2, text="0.5", width=4)
        self.yolo_iou_label.pack(side=tk.LEFT)
        self.yolo_iou_var.trace_add("write", lambda *a: self.yolo_iou_label.config(
            text=f"{self.yolo_iou_var.get():.1f}"))

        self.r_redetect = ttk.Frame(frame)
        self.r_redetect.pack(fill=tk.X, pady=(4, 0))
        self.redetect_btn = ttk.Button(
            self.r_redetect, text="Re-detect All",
            command=self._redetect_all, state=tk.DISABLED
        )
        self.redetect_btn.pack(side=tk.LEFT)
        self.redetect_status_var = tk.StringVar(value="")
        ttk.Label(self.r_redetect, textvariable=self.redetect_status_var, foreground="#555").pack(
            side=tk.LEFT, padx=10
        )

        self.countdown_var = tk.StringVar(value="")
        self.countdown_label = ttk.Label(
            frame, textvariable=self.countdown_var,
            font=("Helvetica", 52, "bold"), foreground="#1a73e8"
        )
        self.countdown_label.pack(pady=(8, 2))

        r1 = ttk.Frame(frame)
        r1.pack(fill=tk.X, pady=(6, 0))
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            r1, variable=self.progress_var, length=280, mode="determinate"
        )
        self.progress_bar.pack(side=tk.LEFT, padx=(0, 8))
        self.time_var = tk.StringVar(value="0.0s / 10s")
        ttk.Label(r1, textvariable=self.time_var).pack(side=tk.LEFT, padx=(0, 18))
        self.saved_var = tk.StringVar(value="Images: 0")
        ttk.Label(r1, textvariable=self.saved_var, font=("Helvetica", 10, "bold")).pack(side=tk.LEFT)
        self.last_saved_var = tk.StringVar(value="")
        ttk.Label(r1, textvariable=self.last_saved_var, foreground="#555").pack(side=tk.RIGHT)

    def _build_log(self, parent):
        frame = ttk.LabelFrame(parent, text=" Log ", padding=5)
        frame.pack(fill=tk.BOTH, expand=True)

        container = ttk.Frame(frame)
        container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(
            container, height=8, wrap=tk.WORD, state=tk.DISABLED,
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
            font=("Courier", 10), borderwidth=0
        )
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _setup_listbox_hover(self):
        def _on_listbox_motion(event):
            try:
                lb = event.widget
                idx = lb.nearest(event.y)
                if idx >= 0:
                    lb.selection_clear(0, 'end')
                    lb.selection_set(idx)
                    lb.activate(idx)
            except Exception:
                pass
        self.root.bind_class('Listbox', '<Motion>', _on_listbox_motion)

    def _restore_config(self):
        cfg = self.config
        self.dir_var.set(cfg.get("last_directory", ""))
        if cfg.get("last_port") in self.serial.list_ports():
            self.port_var.set(cfg["last_port"])
        self.baud_var.set(str(cfg.get("last_baud", DEFAULT_BAUD)))
        self.res_var.set(cfg.get("last_resolution", DEFAULT_RESOLUTION))
        self.auto_resize_var.set(cfg.get("auto_resize", False))
        self.duration_var.set(str(cfg.get("last_duration", DEFAULT_DURATION)))
        self.detect_var.set(cfg.get("hand_detection_enabled", False))
        self.detect_conf_var.set(str(cfg.get("min_detection_confidence", 0.2)))
        self._detection_enabled = cfg.get("hand_detection_enabled", False)
        try:
            self._detection_confidence = float(cfg.get("min_detection_confidence", 0.2))
        except (ValueError, TypeError):
            self._detection_confidence = 0.2

        self._detector_type = cfg.get("detector_type", "mediapipe")
        if self._detector_type == "yolo":
            self.detector_type_var.set("Custom YOLO")
            self._on_detector_change()
        self.yolo_model_var.set(cfg.get("yolo_model_path", ""))
        self._yolo_confidence = float(cfg.get("yolo_confidence", 0.3))
        self.yolo_conf_var.set(self._yolo_confidence)
        self._yolo_iou = float(cfg.get("yolo_iou_threshold", 0.5))
        self.yolo_iou_var.set(self._yolo_iou)

        self._refresh_ports()
        self._update_full_path()

    def _refresh_ports(self):
        ports = self.serial.list_ports()
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _scan_subdirectories(self, directory):
        try:
            entries = os.listdir(directory)
        except OSError:
            return

        subdirs = [
            e for e in entries
            if not e.startswith(".") and os.path.isdir(os.path.join(directory, e))
        ]
        subdirs.sort(key=str.lower)
        self.class_combo["values"] = subdirs

    def _check_renumber(self, dir_path, class_name):
        if self.capturing:
            return
        if not dir_path or not class_name:
            return

        full_path = os.path.join(dir_path, class_name)
        if full_path in self._renumbered_dirs:
            return
        self._renumbered_dirs.add(full_path)

        count = count_images(full_path)
        if count == 0:
            return

        ok = messagebox.askyesno(
            "Renumber Images",
            f"Found {count} images in:\n{full_path}\n\n"
            f"Renumber them from 0000_{class_name}.jpg to {count - 1:04d}_{class_name}.jpg?"
        )
        if ok:
            renumber_images(full_path, start=0)
            self._log(f"Renumbered {count} images in {full_path} (0000_{class_name}\u2013{count - 1:04d}_{class_name})")

    def _on_detection_toggle(self):
        self._detection_enabled = self.detect_var.get()
        if self._detection_enabled:
            try:
                self._detection_confidence = float(self.detect_conf_var.get())
            except ValueError:
                self._detection_confidence = 0.2

    def _on_detector_change(self, event=None):
        self._detector_type = "yolo" if "YOLO" in self.detector_type_var.get() else "mediapipe"
        if self._detector_type == "yolo":
            self.r_mp_ctrl.pack_forget()
            self.r_yolo_ctrl.pack(fill=tk.X, pady=(4, 0), before=self.r_redetect)
        else:
            self.r_yolo_ctrl.pack_forget()
            self.r_mp_ctrl.pack(fill=tk.X, pady=(4, 0), before=self.r_redetect)

    def _browse_yolo_model(self):
        path = filedialog.askopenfilename(
            title="Select YOLO model",
            initialdir=self.yolo_model_var.get() or str(Path.home()),
            filetypes=[("PyTorch model", "*.pt"), ("All files", "*.*")]
        )
        if path:
            self.yolo_model_var.set(path)

    def _init_detection(self):
        if self._detection_worker is not None:
            return True

        try:
            if self._detector_type == "yolo":
                model_path = self.yolo_model_var.get().strip()
                if not model_path or not os.path.isfile(model_path):
                    messagebox.showerror(
                        "Model Error",
                        "YOLO model not found.\nPlease select a valid .pt file."
                    )
                    return False

                self._yolo_confidence = self.yolo_conf_var.get()
                self._yolo_iou = self.yolo_iou_var.get()
                self._hand_detector = YoloDetector(
                    model_path=model_path,
                    confidence=self._yolo_confidence,
                    iou_threshold=self._yolo_iou,
                )
            else:
                self._detection_confidence = float(self.detect_conf_var.get())
                self._hand_detector = HandDetector(
                    min_detection_confidence=self._detection_confidence,
                    max_num_hands=2,
                    enhance_contrast=self.clahe_var.get(),
                )

            self._detection_worker = DetectionWorker(
                hand_detector=self._hand_detector,
                save_callback=save_yolo_label,
                log_callback=self._log,
            )
            self._detection_worker.start()
            dtype = "YOLO" if self._detector_type == "yolo" else "MediaPipe"
            self._log(f"Hand detection worker started ({dtype})")
            return True
        except Exception as e:
            self._log(f"Failed to init hand detection: {e}")
            messagebox.showerror("Detection Error", f"Cannot initialize detector:\n{e}")
            self._detection_enabled = False
            self.detect_var.set(False)
            return False

    def _browse_directory(self):
        path = filedialog.askdirectory(
            title="Select save directory",
            initialdir=self.dir_var.get() or str(Path.home())
        )
        if path:
            self.dir_var.set(path)
            self._update_full_path()
            self._scan_subdirectories(path)
            c = self.class_var.get().strip()
            if c:
                self._check_renumber(path, c)
            self._update_review_btn()

    def _on_class_change(self, *args):
        self._update_full_path()
        d = self.dir_var.get().strip()
        c = self.class_var.get().strip()
        if d and c:
            self._check_renumber(d, c)
        self._update_review_btn()

    def _update_full_path(self):
        d = self.dir_var.get().strip()
        c = self.class_var.get().strip()
        if d and c:
            full = os.path.join(d, c)
            self.path_preview_var.set(f"→ {full}/")
            if hasattr(self, 'class_count_var'):
                self.class_count_var.set(f"Total images: {count_images(full)}")
        elif d:
            self.path_preview_var.set(f"→ {d}/[class]")
            if hasattr(self, 'class_count_var'):
                self.class_count_var.set("")
        else:
            self.path_preview_var.set("→ (select directory and class)")
            if hasattr(self, 'class_count_var'):
                self.class_count_var.set("")

    def _update_review_btn(self):
        d = self.dir_var.get().strip()
        if not d or not os.path.isdir(d):
            if hasattr(self, 'review_btn'):
                self.review_btn.config(state=tk.DISABLED)
            if hasattr(self, 'redetect_btn'):
                self.redetect_btn.config(state=tk.DISABLED)
            if hasattr(self, 'fix_txt_btn'):
                self.fix_txt_btn.config(state=tk.DISABLED)
            return
        has_images = False
        c = self.class_var.get().strip()
        if c:
            path = os.path.join(d, c)
            has_images = os.path.isdir(path) and any(
                f.endswith(".jpg") for f in os.listdir(path)
            )
            if hasattr(self, 'fix_txt_btn'):
                self.fix_txt_btn.config(state=tk.NORMAL if os.path.isdir(path) else tk.DISABLED)
        else:
            if hasattr(self, 'fix_txt_btn'):
                self.fix_txt_btn.config(state=tk.DISABLED)
            try:
                for entry in os.listdir(d):
                    entry_path = os.path.join(d, entry)
                    if not entry.startswith(".") and os.path.isdir(entry_path):
                        if any(f.endswith(".jpg") for f in os.listdir(entry_path)):
                            has_images = True
                            break
            except OSError:
                pass
        if hasattr(self, 'review_btn'):
            self.review_btn.config(state=tk.NORMAL if has_images else tk.DISABLED)
        if hasattr(self, 'redetect_btn'):
            self.redetect_btn.config(state=tk.NORMAL if has_images else tk.DISABLED)

    def _fix_txt_classes(self):
        d = self.dir_var.get().strip()
        c = self.class_var.get().strip()
        if not d or not c:
            return
        
        target_dir = os.path.join(d, c)
        if not os.path.isdir(target_dir):
            messagebox.showwarning("Warning", f"Directory {target_dir} does not exist.")
            return

        class_id = get_class_id(d, c)
        if class_id is None:
            messagebox.showwarning("Warning", f"Could not determine class ID for '{c}'. Ensure it exists in classes.txt.")
            return

        updated_count = 0
        try:
            for fname in os.listdir(target_dir):
                if fname.endswith(".txt") and fname != "classes.txt":
                    filepath = os.path.join(target_dir, fname)
                    with open(filepath, "r") as f:
                        lines = f.readlines()
                    
                    new_lines = []
                    modified = False
                    for line in lines:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            old_id = parts[0]
                            if old_id != str(class_id):
                                parts[0] = str(class_id)
                                modified = True
                            new_lines.append(" ".join(parts) + "\n")
                        else:
                            new_lines.append(line)
                            
                    if modified:
                        with open(filepath, "w") as f:
                            f.writelines(new_lines)
                        updated_count += 1
                        
            messagebox.showinfo("Success", f"Updated class ID to {class_id} in {updated_count} TXT files.")
            self._log(f"Fixed TXT classes to ID {class_id} for {updated_count} files in {target_dir}")
        except Exception as e:
            self._log(f"Error fixing TXT classes: {e}")
            messagebox.showerror("Error", f"Failed to update TXT files: {e}")

    def _scan_unannotated(self, base_dir):
        items = []
        try:
            entries = os.listdir(base_dir)
        except OSError:
            return items

        for entry in entries:
            if entry.startswith("."):
                continue
            subdir = os.path.join(base_dir, entry)
            if not os.path.isdir(subdir):
                continue

            class_id = get_class_id(base_dir, entry)

            try:
                files = os.listdir(subdir)
            except OSError:
                continue

            for fname in files:
                if not fname.endswith(".jpg"):
                    continue
                txt_name = os.path.splitext(fname)[0] + ".txt"
                txt_path = os.path.join(subdir, txt_name)
                if not os.path.isfile(txt_path):
                    items.append((os.path.join(subdir, fname), class_id))

        return items

    def _redetect_all(self):
        base_dir = self.dir_var.get().strip()
        if not base_dir or not os.path.isdir(base_dir):
            return

        items = self._scan_unannotated(base_dir)
        if not items:
            messagebox.showinfo("Re-detect", "All images already annotated.")
            return

        if not self._init_detection():
            return

        self.redetect_status_var.set(f"Re-detect: 0/{len(items)}")
        self.redetect_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.time_var.set(f"Detecting: 0/{len(items)}")

        for filepath, class_id in items:
            try:
                img = Image.open(filepath).copy()
                self._detection_worker.enqueue(img, filepath, class_id)
            except Exception as e:
                self._log(f"Re-detect: failed to load {os.path.basename(filepath)}: {e}")

        self._log(f"Re-detect: queued {len(items)} images")
        self._redetect_after_id = self.root.after(
            500, self._poll_redetect_progress, len(items)
        )

    def _poll_redetect_progress(self, total):
        remaining = self._detection_worker.queue_size if self._detection_worker else 0
        if not self._detection_worker:
            self.redetect_status_var.set("Re-detect: worker stopped")
            self._update_review_btn()
            return

        processed = total - remaining
        self.progress_var.set((processed / total) * 100 if total > 0 else 0)
        self.time_var.set(f"Detecting: {processed}/{total}")
        if remaining > 0:
            self.redetect_status_var.set(f"Re-detect: {processed}/{total}")
            self._redetect_after_id = self.root.after(
                500, self._poll_redetect_progress, total
            )
        else:
            self.redetect_status_var.set(
                f"Re-detect done ({processed} images, {self._detection_worker.failed} failed)"
            )
            self.progress_var.set(100)
            self.time_var.set(f"Detection done ({processed})")
            self._redetect_after_id = None
            self._update_review_btn()
            self._log(
                f"Re-detect finished: {self._detection_worker.processed} annotated, "
                f"{self._detection_worker.failed} failed"
            )

    def _cancel_detection_polling(self):
        if self._detection_progress_after_id:
            self.root.after_cancel(self._detection_progress_after_id)
            self._detection_progress_after_id = None
        if self._redetect_after_id:
            self.root.after_cancel(self._redetect_after_id)
            self._redetect_after_id = None

    def _start_post_capture_detection(self):
        if not self._pending_detection:
            return
        if not self._init_detection():
            return

        total = len(self._pending_detection)
        self._log(f"Post-capture detection: {total} images queued")

        for filepath, class_id in self._pending_detection:
            try:
                img = Image.open(filepath).copy()
                self._detection_worker.enqueue(img, filepath, class_id)
            except Exception as e:
                self._log(f"Detection: failed to load {os.path.basename(filepath)}: {e}")

        self._pending_detection = []
        self.progress_var.set(0)
        self.time_var.set(f"Detecting: 0/{total}")
        self._detection_progress_after_id = self.root.after(
            500, self._poll_detection_progress, total
        )

    def _poll_detection_progress(self, total):
        if not self._detection_worker:
            self._detection_progress_after_id = None
            self.time_var.set("Detection: worker stopped")
            return

        remaining = self._detection_worker.queue_size
        processed = total - remaining
        self.progress_var.set((processed / total) * 100 if total > 0 else 0)
        self.time_var.set(f"Detecting: {processed}/{total}")

        if remaining > 0 and self._detection_worker:
            self._detection_progress_after_id = self.root.after(
                500, self._poll_detection_progress, total
            )
        else:
            self._detection_progress_after_id = None
            self.time_var.set(f"Detection done ({processed})")
            self._update_review_btn()
            self._log(
                f"Post-capture detection finished: "
                f"{self._detection_worker.processed} annotated, "
                f"{self._detection_worker.failed} failed"
            )

    def _toggle_connect(self):
        if self.serial.connected:
            self.serial.disconnect()
            self.connect_btn.config(text="Connect")
            self.status_var.set("● Disconnected")
            self.status_label.config(foreground="#d00")
            self._log("Disconnected")
        else:
            port = self.port_var.get()
            baud = int(self.baud_var.get())
            if not port:
                messagebox.showerror("Error", "No serial port selected")
                return
            try:
                self.serial.connect(port, baud)
                self.connect_btn.config(text="Disconnect")
                self.status_var.set("● Connected")
                self.status_label.config(foreground="#0a0")
                self._log(f"Connected {port} @ {baud} baud")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to connect:\n{e}")

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def start_capture(self):
        if self.capturing:
            return

        self._cancel_detection_polling()

        d = self.dir_var.get().strip()
        raw_class = self.class_var.get().strip()
        c = sanitize_class_name(raw_class)

        if not d:
            messagebox.showerror("Error", "Select a save directory first")
            return
        if not c:
            messagebox.showerror("Error", "Enter a class name")
            return

        save_dir = os.path.join(d, c)
        try:
            os.makedirs(save_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Error", f"Cannot create directory:\n{e}")
            return

        try:
            duration = float(self.duration_var.get())
            duration = max(1.0, min(300.0, duration))
        except ValueError:
            duration = float(DEFAULT_DURATION)

        try:
            w, h = parse_resolution(self.res_var.get())
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return

        self.capture_save_dir = save_dir
        self.capture_w = w
        self.capture_h = h
        self.capture_duration = duration
        self.auto_resize = self.auto_resize_var.get()
        self.capture_next_idx = get_next_index(save_dir)

        self._pending_detection = []

        if self._detection_enabled:
            entries = os.listdir(d) if os.path.isdir(d) else []
            subdirs = sorted(
                [e for e in entries if not e.startswith(".") and os.path.isdir(os.path.join(d, e))],
                key=str.lower,
            )
            save_classes_txt(d, subdirs)
            self._detection_class_id = get_class_id(d, c)

        self.config["last_directory"] = d
        self.config["last_duration"] = duration
        self.config["last_resolution"] = self.res_var.get()
        self.config["auto_resize"] = self.auto_resize
        self.config["last_baud"] = int(self.baud_var.get())
        self.config["last_port"] = self.port_var.get()
        self.config["hand_detection_enabled"] = self._detection_enabled
        self.config["min_detection_confidence"] = self._detection_confidence
        self.config["detector_type"] = self._detector_type
        self._yolo_model_path = self.yolo_model_var.get().strip()
        self.config["yolo_model_path"] = self._yolo_model_path
        self.config["yolo_confidence"] = self.yolo_conf_var.get()
        self.config["yolo_iou_threshold"] = self.yolo_iou_var.get()
        save_config(self.config)

        self._log(f'Capture session – class: "{c}", {duration}s, {w}×{h}')

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.duration_spin.config(state=tk.DISABLED)
        self.redetect_btn.config(state=tk.DISABLED)

        self._do_countdown(3)

    def _do_countdown(self, remaining):
        if remaining > 0:
            self.countdown_var.set(str(remaining))
            self._countdown_after_id = self.root.after(1000, self._do_countdown, remaining - 1)
        else:
            self.countdown_var.set("GO!")
            self.root.after(400, self._clear_countdown_and_begin)

    def _clear_countdown_and_begin(self):
        self._countdown_after_id = None
        self.countdown_var.set("")
        self.capturing = True
        self.capture_start_time = time.time()
        self.capture_count = 0

        delay_ms = int(self.capture_duration * 1000)
        self._capture_timer_id = self.root.after(delay_ms, self._auto_stop)

        self._update_progress_ui()
        self._log("Capture active – receiving frames...")

    def _update_progress_ui(self):
        if not self.capturing:
            return

        elapsed = time.time() - self.capture_start_time
        remaining = max(0.0, self.capture_duration - elapsed)
        progress = min(100.0, (elapsed / self.capture_duration) * 100.0)

        self.progress_var.set(progress)
        self.time_var.set(f"{remaining:.1f}s / {self.capture_duration:.0f}s")
        self.saved_var.set(f"Images: {self.capture_count}")

        if remaining <= 0:
            self._auto_stop()
            return

        self.root.after(100, self._update_progress_ui)

    def _auto_stop(self):
        if self.capturing:
            self._log("Time elapsed – stopping capture")
            self.stop_capture()

    def _reset_capture_ui(self):
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.duration_spin.config(state=tk.NORMAL)
        self.countdown_var.set("")
        self.last_saved_var.set("")
        self._update_review_btn()

    def _open_review(self):
        d = self.dir_var.get().strip()
        if not d or not os.path.isdir(d):
            return
        initial_class = self.class_var.get().strip()
        classes = load_classes_txt(d)
        if self._review_window is not None:
            try:
                self._review_window.destroy()
            except Exception:
                pass
        self._review_window = ReviewWindow(self.root, d, classes, initial_class=initial_class)

    def stop_capture(self):
        if self._countdown_after_id:
            self.root.after_cancel(self._countdown_after_id)
            self._countdown_after_id = None
            self._log("Capture cancelled during countdown")

        if not self.capturing:
            self._reset_capture_ui()
            return

        self.capturing = False

        if self._capture_timer_id:
            self.root.after_cancel(self._capture_timer_id)
            self._capture_timer_id = None

        elapsed = time.time() - self.capture_start_time
        self._reset_capture_ui()
        self.progress_var.set(100)
        self.time_var.set(f"Done ({elapsed:.1f}s)")

        total = count_images(self.capture_save_dir)
        msg = f"Capture finished \u2013 {self.capture_count} saved ({total} total) in {self.capture_save_dir}"
        self._log(msg)
        
        self._update_full_path()

        if self._pending_detection:
            self._start_post_capture_detection()

    def stop_capture_or_disconnect(self):
        if self._countdown_after_id or self.capturing:
            self._log("Stopped by user (Esc)")
            self.stop_capture()
        elif self.serial.connected:
            self._toggle_connect()

    def _poll_frames(self):
        try:
            while True:
                raw = self.serial.frame_queue.get_nowait()
                if self.capturing:
                    self._process_frame(raw)
                else:
                    self._preview_frame(raw)
        except queue.Empty:
            pass

        self.root.after(POLL_INTERVAL_MS, self._poll_frames)

    def _process_frame(self, raw):
        if len(raw) != FRAME_SIZE:
            self._log(f"⚠ Unexpected frame size: {len(raw)} bytes (expected {FRAME_SIZE}), skipped")
            return

        try:
            img = Image.frombytes("L", (FRAME_WIDTH, FRAME_HEIGHT), raw)

            saved = img
            if self.capture_w != FRAME_WIDTH or self.capture_h != FRAME_HEIGHT:
                if self.auto_resize:
                    saved = img.resize((self.capture_w, self.capture_h), Image.LANCZOS)
                else:
                    self._log(f"⚠ Frame {self.capture_w}×{self.capture_h} ≠ sensor {FRAME_WIDTH}×{FRAME_HEIGHT}")

            class_name = os.path.basename(os.path.normpath(self.capture_save_dir))
            filename = f"{self.capture_next_idx:04d}_{class_name}.jpg"
            filepath = os.path.join(self.capture_save_dir, filename)

            saved.save(filepath, "JPEG", quality=JPEG_QUALITY)

            if self._detection_enabled:
                self._pending_detection.append((filepath, self._detection_class_id))

            self.capture_next_idx += 1
            self.capture_count += 1
            self.last_saved_var.set(f"Last: {filename}")

            if self.capture_count <= 3 or self.capture_count % 3 == 0:
                self._update_preview(img)

        except Exception as e:
            self._log(f"⚠ Frame error: {e}")

    def _preview_frame(self, raw):
        if len(raw) != FRAME_SIZE:
            return
        try:
            img = Image.frombytes("L", (FRAME_WIDTH, FRAME_HEIGHT), raw)
            self._update_preview(img)
        except Exception:
            pass

    def _update_preview(self, img):
        try:
            preview = img.copy()
            preview.thumbnail(PREVIEW_SIZE, Image.LANCZOS)
            self._preview_photo = ImageTk.PhotoImage(preview)

            self.preview_canvas.delete("all")
            pw, ph = PREVIEW_SIZE
            ppw = self._preview_photo.width()
            pph = self._preview_photo.height()
            self.preview_canvas.create_image(pw // 2, ph // 2, image=self._preview_photo)
        except Exception:
            pass

    def _on_close(self):
        self.stop_capture()
        self.serial.disconnect()

        self.config["last_port"] = self.port_var.get()
        try:
            self.config["last_baud"] = int(self.baud_var.get())
        except ValueError:
            pass
        self.config["last_directory"] = self.dir_var.get()
        self.config["last_resolution"] = self.res_var.get()
        self.config["auto_resize"] = self.auto_resize_var.get()
        try:
            self.config["last_duration"] = float(self.duration_var.get())
        except ValueError:
            pass
        self.config["hand_detection_enabled"] = self._detection_enabled
        self.config["min_detection_confidence"] = self._detection_confidence
        self.config["detector_type"] = self._detector_type
        self._yolo_model_path = self.yolo_model_var.get().strip()
        self.config["yolo_model_path"] = self._yolo_model_path
        self.config["yolo_confidence"] = self.yolo_conf_var.get()
        self.config["yolo_iou_threshold"] = self.yolo_iou_var.get()
        save_config(self.config)

        if self._detection_worker:
            self._detection_worker.stop()
        if self._hand_detector:
            self._hand_detector.close()

        self.root.destroy()

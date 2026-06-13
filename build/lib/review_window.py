import os

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from utils import load_yolo_labels

CANVAS_SIZE = (640, 480)
BBOX_COLORS = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF"]


class ReviewWindow(tk.Toplevel):
    def __init__(self, parent, base_dir, classes, initial_class=""):
        super().__init__(parent)
        self.title("Review Captured Images")
        self.geometry(f"{CANVAS_SIZE[0] + 40}x{CANVAS_SIZE[1] + 180}")
        self.resizable(False, False)

        self._base_dir = base_dir
        self._classes = classes
        self._dir_classes = []
        self._all_images = []
        self._images = []
        self._current_idx = 0
        self._photo = None
        self._padding = 10
        self._filter_annotated = "all"
        self._filter_class = -1
        self._initial_class = initial_class

        self._cached_photo = None
        self._cached_labels = []
        self._cached_disp_size = (0, 0)
        self._cached_offsets = (0, 0)

        self._scan_images()

        if not self._images:
            self._show_empty()
            return

        self._build_ui()
        self._show_image(0)

        if self._initial_class:
            self._apply_initial_filter()

        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())
        self.bind("<Escape>", lambda e: self.destroy())

    def _apply_initial_filter(self):
        if self._initial_class in self._dir_classes:
            self.class_filter_combo.set(self._initial_class)
            self._on_filter_change()

    def _scan_images(self):
        if not os.path.isdir(self._base_dir):
            return

        dir_classes_set = set()
        all_items = []

        try:
            entries = sorted(os.listdir(self._base_dir))
        except OSError:
            return

        def sort_key(fname):
            try:
                return (0, int(os.path.splitext(fname)[0]))
            except ValueError:
                return (1, fname)

        for entry in entries:
            if entry.startswith("."):
                continue
            subdir = os.path.join(self._base_dir, entry)
            if not os.path.isdir(subdir):
                continue

            jpgs = [f for f in os.listdir(subdir) if f.endswith(".jpg")]
            if not jpgs:
                continue

            dir_classes_set.add(entry)
            jpgs.sort(key=sort_key)

            for fname in jpgs:
                filepath = os.path.join(subdir, fname)
                txt_path = os.path.splitext(filepath)[0] + ".txt"
                labels = load_yolo_labels(txt_path)
                annotated = len(labels) > 0
                class_ids = set(label["class_id"] for label in labels)
                all_items.append({
                    "filepath": filepath,
                    "filename": fname,
                    "class_name": entry,
                    "annotated": annotated,
                    "class_ids": class_ids,
                })

        self._dir_classes = sorted(dir_classes_set, key=str.lower)
        self._all_images = all_items
        self._apply_filters()

    def _apply_filters(self):
        self._images = []
        for item in self._all_images:
            if self._filter_annotated == "annotated" and not item["annotated"]:
                continue
            if self._filter_annotated == "unannotated" and item["annotated"]:
                continue
            if self._filter_class >= 0:
                cls_name = (
                    self._dir_classes[self._filter_class]
                    if self._filter_class < len(self._dir_classes)
                    else ""
                )
                if item["class_name"] != cls_name:
                    continue
            self._images.append(item)

    def _show_empty(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(expand=True)
        ttk.Label(
            frame, text="No images to review",
            font=("Helvetica", 14)
        ).pack()
        ttk.Button(frame, text="Close", command=self.destroy).pack(pady=10)

    def _on_slider_move(self, value):
        idx = int(float(value)) - 1
        if idx != self._current_idx:
            self._show_image(idx)

    def _update_slider(self):
        self.image_slider.config(state=tk.NORMAL, to=max(1, len(self._images)))
        self.image_slider.set(self._current_idx + 1)

    def _on_filter_change(self, event=None):
        selected = self.filter_combo.get()
        if selected == "Annotated":
            self._filter_annotated = "annotated"
        elif selected == "Unannotated":
            self._filter_annotated = "unannotated"
        else:
            self._filter_annotated = "all"

        cls = self.class_filter_combo.get()
        if cls == "All classes":
            self._filter_class = -1
        else:
            try:
                self._filter_class = self._dir_classes.index(cls)
            except ValueError:
                self._filter_class = -1

        self._apply_filters()

        if not self._images:
            self._show_filtered_empty()
        else:
            self._current_idx = 0
            self._show_image(0)

    def _show_filtered_empty(self):
        self.canvas.delete("all")
        self.canvas.create_text(
            CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] // 2,
            text="No images matching filter", fill="#888888",
            font=("Helvetica", 14)
        )
        self.counter_var.set("No images matching filter")
        self.prev_btn.config(state=tk.DISABLED)
        self.next_btn.config(state=tk.DISABLED)
        self.image_slider.config(state=tk.DISABLED)

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        filter_frame = ttk.Frame(main)
        filter_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self.filter_combo = ttk.Combobox(
            filter_frame, values=["All", "Annotated", "Unannotated"],
            state="readonly", width=14
        )
        self.filter_combo.set("All")
        self.filter_combo.pack(side=tk.LEFT, padx=(8, 4))
        self.filter_combo.bind("<<ComboboxSelected>>", self._on_filter_change)

        class_values = ["All classes"] + self._dir_classes
        self.class_filter_combo = ttk.Combobox(
            filter_frame, values=class_values,
            state="readonly", width=16
        )
        self.class_filter_combo.set("All classes")
        self.class_filter_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.class_filter_combo.bind("<<ComboboxSelected>>", self._on_filter_change)
        if not self._dir_classes:
            self.class_filter_combo.config(state=tk.DISABLED)

        self.canvas = tk.Canvas(
            main, width=CANVAS_SIZE[0], height=CANVAS_SIZE[1],
            bg="#1e1e1e", highlightthickness=0
        )
        self.canvas.pack()

        slider_frame = ttk.Frame(main)
        slider_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(slider_frame, text="Image:").pack(side=tk.LEFT)
        self.image_slider = ttk.Scale(
            slider_frame, from_=1, to=max(1, len(self._images)),
            orient=tk.HORIZONTAL,
            command=self._on_slider_move
        )
        self.image_slider.set(1)
        self.image_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        nav = ttk.Frame(main)
        nav.pack(fill=tk.X, pady=(10, 0))

        self.prev_btn = ttk.Button(nav, text="← Prev", command=self._prev)
        self.prev_btn.pack(side=tk.LEFT)

        self.counter_var = tk.StringVar()
        ttk.Label(nav, textvariable=self.counter_var, font=("Helvetica", 11)).pack(
            side=tk.LEFT, padx=20
        )

        self.next_btn = ttk.Button(nav, text="Next →", command=self._next)
        self.next_btn.pack(side=tk.LEFT)

        ttk.Button(nav, text="Close", command=self.destroy).pack(side=tk.RIGHT)

        pad_row = ttk.Frame(main)
        pad_row.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(pad_row, text="Padding:").pack(side=tk.LEFT)
        self.pad_scale = ttk.Scale(
            pad_row, from_=0, to=50, orient=tk.HORIZONTAL,
            command=self._on_padding_change
        )
        self.pad_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.pad_label_var = tk.StringVar(value=f"{self._padding} px")
        self.pad_scale.set(self._padding)
        ttk.Label(pad_row, textvariable=self.pad_label_var, width=8).pack(side=tk.LEFT)

    def _show_image(self, idx):
        if not self._images:
            return

        self._current_idx = idx
        item = self._images[idx]
        filepath = item["filepath"]
        filename = item["filename"]

        try:
            img = Image.open(filepath)
        except Exception:
            self.canvas.delete("all")
            self.canvas.create_text(
                CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] // 2,
                text="Error loading image", fill="#FF0000",
                font=("Helvetica", 14)
            )
            return

        display_img = img.copy()
        display_img.thumbnail(CANVAS_SIZE, Image.LANCZOS)
        disp_w, disp_h = display_img.size

        self._cached_photo = ImageTk.PhotoImage(display_img)
        self._cached_disp_size = (disp_w, disp_h)
        self._cached_offsets = (
            (CANVAS_SIZE[0] - disp_w) // 2,
            (CANVAS_SIZE[1] - disp_h) // 2
        )

        txt_path = os.path.splitext(filepath)[0] + ".txt"
        self._cached_labels = load_yolo_labels(txt_path)

        self._redraw_bboxes()

        self.counter_var.set(f"Image {idx + 1} / {len(self._images)}  ({filename})")
        self.prev_btn.config(state=tk.NORMAL if idx > 0 else tk.DISABLED)
        self.next_btn.config(state=tk.NORMAL if idx < len(self._images) - 1 else tk.DISABLED)
        self._update_slider()

    def _redraw_bboxes(self):
        if self._cached_photo is None:
            return

        self.canvas.delete("all")
        offset_x, offset_y = self._cached_offsets
        self.canvas.create_image(offset_x, offset_y, anchor=tk.NW, image=self._cached_photo)

        disp_w, disp_h = self._cached_disp_size
        pad = self._padding

        for label in self._cached_labels:
            cx = label["cx"]
            cy = label["cy"]
            bw = label["bw"]
            bh = label["bh"]
            class_id = label["class_id"]

            x1 = (cx - bw / 2) * disp_w + offset_x - pad
            y1 = (cy - bh / 2) * disp_h + offset_y - pad
            x2 = (cx + bw / 2) * disp_w + offset_x + pad
            y2 = (cy + bh / 2) * disp_h + offset_y + pad

            color = BBOX_COLORS[class_id % len(BBOX_COLORS)]
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2)

            if 0 <= class_id < len(self._classes):
                class_name = self._classes[class_id]
            else:
                class_name = f"class_{class_id}"

            self.canvas.create_text(
                x1, y1 - 5, anchor=tk.SW,
                text=class_name, fill=color,
                font=("Helvetica", 10, "bold")
            )

    def _on_padding_change(self, value):
        self._padding = int(float(value))
        self.pad_label_var.set(f"{self._padding} px")
        self._redraw_bboxes()

    def _prev(self):
        if self._current_idx > 0:
            self._show_image(self._current_idx - 1)

    def _next(self):
        if self._current_idx < len(self._images) - 1:
            self._show_image(self._current_idx + 1)

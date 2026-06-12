import os

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

from utils import load_yolo_labels

CANVAS_SIZE = (640, 480)
BBOX_COLORS = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF", "#00FFFF"]


class ReviewWindow(tk.Toplevel):
    def __init__(self, parent, save_dir, classes):
        super().__init__(parent)
        self.title("Review Captured Images")
        self.geometry(f"{CANVAS_SIZE[0] + 40}x{CANVAS_SIZE[1] + 140}")
        self.resizable(False, False)

        self._save_dir = save_dir
        self._classes = classes
        self._images = []
        self._current_idx = 0
        self._photo = None
        self._padding = 10

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

        self.bind("<Left>", lambda e: self._prev())
        self.bind("<Right>", lambda e: self._next())
        self.bind("<Escape>", lambda e: self.destroy())

    def _scan_images(self):
        if not os.path.isdir(self._save_dir):
            return

        files = [f for f in os.listdir(self._save_dir) if f.endswith(".jpg")]

        def sort_key(fname):
            try:
                return (0, int(os.path.splitext(fname)[0]))
            except ValueError:
                return (1, fname)

        files.sort(key=sort_key)
        self._images = files

    def _show_empty(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(expand=True)
        ttk.Label(
            frame, text="No images to review",
            font=("Helvetica", 14)
        ).pack()
        ttk.Button(frame, text="Close", command=self.destroy).pack(pady=10)

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            main, width=CANVAS_SIZE[0], height=CANVAS_SIZE[1],
            bg="#1e1e1e", highlightthickness=0
        )
        self.canvas.pack()

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
        self.pad_scale.set(self._padding)
        self.pad_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        self.pad_label_var = tk.StringVar(value=f"{self._padding} px")
        ttk.Label(pad_row, textvariable=self.pad_label_var, width=8).pack(side=tk.LEFT)

    def _show_image(self, idx):
        if not self._images:
            return

        self._current_idx = idx
        filename = self._images[idx]
        filepath = os.path.join(self._save_dir, filename)

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

import math
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

from protocol import (
    BAUD_RATES,
    DEFAULT_BAUD,
    DEFAULT_DURATION,
    DEFAULT_RESOLUTION,
    JPEG_QUALITY,
    PREVIEW_SIZE,
    RESOLUTIONS,
    POLL_INTERVAL_MS,
)
from serial_handler import SerialHandler
from utils import (
    get_next_index,
    load_config,
    parse_resolution,
    sanitize_class_name,
    save_config,
    update_class_history,
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
        self.capture_h = 324
        self.auto_resize = False
        self._capture_timer_id = None
        self._countdown_after_id = None
        self._preview_photo = None

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

        r5 = ttk.Frame(frame)
        r5.pack(fill=tk.X, pady=(0, 8))
        self.path_preview_var = tk.StringVar(value="→ (select directory and class)")
        ttk.Label(r5, textvariable=self.path_preview_var, foreground="#555").pack(anchor=tk.W)

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
        self.class_combo["values"] = cfg.get("class_history", [])
        self._refresh_ports()
        self._update_full_path()

    def _refresh_ports(self):
        ports = self.serial.list_ports()
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _browse_directory(self):
        path = filedialog.askdirectory(
            title="Select save directory",
            initialdir=self.dir_var.get() or str(Path.home())
        )
        if path:
            self.dir_var.set(path)
            self._update_full_path()

    def _on_class_change(self, *args):
        self._update_full_path()

    def _update_full_path(self):
        d = self.dir_var.get().strip()
        c = self.class_var.get().strip()
        if d and c:
            full = os.path.join(d, c)
            self.path_preview_var.set(f"→ {full}/")
        elif d:
            self.path_preview_var.set(f"→ {d}/[class]")
        else:
            self.path_preview_var.set("→ (select directory and class)")

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

        self.config["last_directory"] = d
        self.config["last_duration"] = duration
        self.config["last_resolution"] = self.res_var.get()
        self.config["auto_resize"] = self.auto_resize
        self.config["last_baud"] = int(self.baud_var.get())
        self.config["last_port"] = self.port_var.get()
        self.config["class_history"] = update_class_history(
            self.config.get("class_history", []), c
        )
        save_config(self.config)
        self.class_combo["values"] = self.config["class_history"]

        self._log(f'Capture session – class: "{c}", {duration}s, {w}×{h}')

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.duration_spin.config(state=tk.DISABLED)

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

        self._log(f"Capture finished – {self.capture_count} images in {self.capture_save_dir}")

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
        except queue.Empty:
            pass

        if not self.capturing:
            while True:
                try:
                    self.serial.frame_queue.get_nowait()
                except queue.Empty:
                    break

        self.root.after(POLL_INTERVAL_MS, self._poll_frames)

    def _process_frame(self, raw):
        total = len(raw)
        side = int(math.isqrt(total))

        if side * side != total:
            self._log(f"⚠ Non-square frame: {total} bytes, skipped")
            return

        try:
            img = Image.frombytes("L", (side, side), raw)

            if self.auto_resize and (side != self.capture_w or side != self.capture_h):
                img = img.resize((self.capture_w, self.capture_h), Image.LANCZOS)
            elif side != self.capture_w or side != self.capture_h:
                self._log(f"⚠ Frame {side}×{side} ≠ target {self.capture_w}×{self.capture_h}")

            filename = f"{self.capture_next_idx:04d}.jpg"
            filepath = os.path.join(self.capture_save_dir, filename)
            img.save(filepath, "JPEG", quality=JPEG_QUALITY)

            self.capture_next_idx += 1
            self.capture_count += 1
            self.last_saved_var.set(f"Last: {filename}")

            if self.capture_count <= 3 or self.capture_count % 3 == 0:
                self._update_preview(img)

        except Exception as e:
            self._log(f"⚠ Frame error: {e}")

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
        save_config(self.config)

        self.root.destroy()

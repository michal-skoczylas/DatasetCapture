# Session changes — 2026-06-03

## Review window — podgląd zdjęć z bounding boxami

### Nowy plik `review_window.py`
- Klasa `ReviewWindow(tk.Toplevel)` — okno podglądu otwierane po zakończeniu capture
- Canvas 640×480 px wyświetlający zdjęcia z narysowanymi bounding boxami
- Nawigacja Prev/Next (przyciski + strzałki ← →) + przycisk Close
- Konwersja etykiet YOLO (cx, cy, bw, bh) na współrzędne pikseli wyświetlanego obrazu
- Różne kolory bbox dla różnych class_id (6 kolorów cyklicznie)
- Etykieta z nazwą klasy nad prostokątem
- Obsługa braku pliku `.txt` (zdjęcie bez detekcji) i pustego katalogu

### Zmiany w `utils.py`
- Dodano `load_yolo_labels(txt_path)` — wczytuje plik `.txt` w formacie YOLO, zwraca listę słowników z class_id, cx, cy, bw, bh
- Dodano `load_classes_txt(base_dir)` — wczytuje `classes.txt`, zwraca listę nazw klas

### Zmiany w `app.py`
- Import `ReviewWindow` z `review_window` i `load_classes_txt` z `utils`
- Dodano atrybut `self._review_window = None`
- Dodano przycisk "Review" w sekcji Capture (domyślnie `state=DISABLED`)
- Metoda `_open_review()` — tworzy `ReviewWindow` z `capture_save_dir` i załadowanymi klasami
- `stop_capture()` — enable przycisku Review po zakończeniu capture (jeśli `capture_count > 0`)
- `_reset_capture_ui()` — disable przycisku Review przy resetowaniu UI


# Session changes — 2026-05-03

## Image renumbering + total counter + class subdirectory scanning

### Changes to `utils.py`
- Added `count_images(directory)` — counts `.jpg` files in a directory (returns 0 if not exists)
- Added `renumber_images(directory, start=0)` — renames all `.jpg` files sequentially from `start` (format `0000.jpg`), sorted by existing numeric prefix, two-phase rename via temporary names to avoid conflicts
- Removed `update_class_history()` function (class history feature removed)
- Removed `MAX_CLASS_HISTORY` from imports

### Changes to `app.py`
- Added `count_images`, `renumber_images` to imports; removed `update_class_history`
- Added `_renumbered_dirs` set attribute — tracks which `dir/class` paths have already been checked for renumbering (prevents repeat dialogs)
- Added `_scan_subdirectories(directory)` method — lists non-hidden subdirectories of the base save folder, sorts alphabetically, sets them as `class_combo` values (detected classes first)
- Added `_check_renumber(dir_path, class_name)` method — counts `.jpg` in `dir/class/`, shows `askyesno` dialog offering renumbering from `0000.jpg` up, executes `renumber_images()` if user confirms
- `_browse_directory()` now calls `_scan_subdirectories()` and `_check_renumber()` after selecting a path
- `_on_class_change()` now calls `_check_renumber()` when both directory and class are set
- `stop_capture()` log extended: `"Capture finished – X saved (Y total) in /path/"` (includes total image count in the folder)
- Removed class history saving from `start_capture()` — no longer saves to config or updates combo values
- Removed `class_combo["values"]` restoration from `_restore_config()` (combo now populated by `_scan_subdirectories` only)


# Session changes — 2026-05-02

## Protocol updated for Pico HM01B0 firmware

### Changes to `protocol.py`
- `SYNC_BYTES` changed from `[0xAA, 0xBB, 0xCC, 0xDD]` to `[0x55, 0xAA]` (matches firmware `header[]`)
- `HEADER_SIZE` changed from 8 to 2 (only sync bytes, no payload-size field)
- Added `FRAME_WIDTH = 324`, `FRAME_HEIGHT = 244`, `FRAME_SIZE = 79056`
- Removed `STOP_BYTE`, `FOOTER_SIZE`, `FRAME_OVERHEAD` (firmware sends fixed-size frames only)
- Default resolution: `324×244`, default baud: `115200` (matches firmware)

### Changes to `serial_handler.py`
- Removed old protocol imports (`STOP_BYTE`, `FOOTER_SIZE`) — no longer needed
- Rewrote `_extract_frame()`: finds 2-byte sync, then extracts fixed 79056-byte payload
- Protocol is now stateless: no variable-length parsing, no stop-byte validation

### Changes to `app.py`
- Removed `import math` (no longer needed)
- `_process_frame()` uses `self.capture_w × self.capture_h` instead of `math.isqrt()` — supports non-square frames
- Default frame dimensions: `324×244` (was `324×324`)
- Frame size mismatch logged as `Unexpected frame size` instead of `Non-square frame`

## Frame processing fixes — 2026-05-02 (second session)

### Changes to `app.py`
- Imported `FRAME_WIDTH`, `FRAME_HEIGHT`, `FRAME_SIZE` from `protocol.py`
- `_process_frame()` validates raw size against `FRAME_SIZE` (firmware's fixed frame size) instead of `capture_w * capture_h` (user-requested resolution) — fixes "expected 104976" errors when config has square resolution saved
- `_process_frame()` creates image from native `(FRAME_WIDTH, FRAME_HEIGHT)` = `(324, 244)`, then optionally resizes to user's `(capture_w, capture_h)` — previously tried to create image at user resolution from native-sized data
- Auto-resize logic fixed: `img.resize((capture_w, capture_h))` now correctly resizes FROM native TO desired (was a no-op resize to same size)
- Added `_preview_frame()` — shows live preview immediately after connect, before any capture starts
- `_poll_frames()` routes frames to `_process_frame()` when capturing, or `_preview_frame()` when idle (previously discarded all frames when not capturing)

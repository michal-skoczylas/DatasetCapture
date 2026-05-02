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

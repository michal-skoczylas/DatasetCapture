# DatasetCapture

![Python](https://img.shields.io/badge/Python-3.7+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

Desktop GUI tool for capturing image datasets from a **Raspberry Pi Pico** with an **HM01B0 grayscale camera sensor** over USB/Serial. Designed for collecting labeled training data for machine learning — with optional automatic hand detection and YOLO-format label generation.

## Features

- **Live preview** — real-time image stream from the sensor while connected
- **Countdown capture** — 3-2-1-GO timer before recording begins
- **Auto hand detection** — MediaPipe Hand Landmarker generates YOLO bounding boxes automatically
- **Review window** — post-capture image viewer with overlaid bounding boxes and adjustable padding
- **Class-based organization** — images saved into named subdirectories (e.g., `OpenHand/`, `ClosedHand/`)
- **Image management** — sequential numbering, renumbering, total count tracking
- **Configurable** — resolution, capture duration, baud rate, detection confidence threshold
- **Cross-platform** — works on macOS, Windows, and Linux

## Hardware Requirements

| Component | Description |
|-----------|-------------|
| Raspberry Pi Pico | Microcontroller running custom camera firmware |
| Himax HM01B0 | Monochrome CMOS sensor, 324x244 pixels, 8-bit grayscale |
| USB cable | Connects the Pico to the host computer |

The Pico firmware transmits frames as raw pixel data: **2-byte sync header** (`0x55 0xAA`) followed by **79,056 bytes** of grayscale pixels per frame.

## Installation

```bash
git clone https://github.com/michal-skoczylas/DatasetCapture.git
cd DatasetCapture
pip install -r requirements.txt
```

Dependencies:
- `pyserial` — serial communication with the Pico
- `Pillow` — image processing and JPEG encoding
- `mediapipe` — hand landmark detection (model auto-downloads on first use)

## Usage

```bash
python main.py
```

1. **Connect** — select the serial port from the dropdown and click Connect
2. **Set class** — choose a save directory and enter a class name (e.g., `OpenHand`)
3. **Capture** — click START CAPTURE, wait for the countdown, collect images
4. **Review** — click Review to inspect captured images with bounding boxes

Press **Escape** to stop capture early or disconnect.

## Project Structure

| File | Description |
|------|-------------|
| `main.py` | Entry point — creates the tkinter window |
| `app.py` | Main application class — GUI, capture logic, frame processing |
| `serial_handler.py` | Threaded serial reader with buffer-based frame extraction |
| `protocol.py` | Protocol constants: sync bytes, frame dimensions, baud rates |
| `utils.py` | Config persistence, file utilities, YOLO label handling |
| `review_window.py` | Post-capture image viewer with bounding box overlay |
| `hand_detector.py` | MediaPipe hand detection wrapper |
| `detection_worker.py` | Background thread for async hand detection |

## Output Format

Captured images are organized into class subdirectories:

```
dataset/
  OpenHand/
    0000.jpg
    0000.txt        # YOLO label (if detection enabled)
    0001.jpg
    ...
  ClosedHand/
    0000.jpg
    ...
  classes.txt        # class index → name mapping
```

YOLO label format (one line per detected hand):
```
<class_id> <center_x> <center_y> <width> <height>
```
All values are normalized to 0.0–1.0 relative to image dimensions.

## Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| [architecture.md](docs/architecture.md) | Module dependency diagram and relationships |
| [image-capture.md](docs/image-capture.md) | End-to-end capture pipeline walkthrough |
| [protocol.md](docs/protocol.md) | Frame format specification |
| [serial-handler.md](docs/serial-handler.md) | Serial threading model and buffer management |
| [gui-reference.md](docs/gui-reference.md) | Full GUI layout and control reference |
| [configuration.md](docs/configuration.md) | Config file format and persistence logic |

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

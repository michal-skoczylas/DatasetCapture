# Architektura projektu

## Diagram zależności

```
main.py
  └─ import app.MainWindow
       │
       ├─ import protocol.*         (stałe: FRAME_SIZE, SYNC_BYTES, RESOLUTIONS, ...)
       ├─ import serial_handler.*   (klasa SerialHandler)
       ├─ import utils.*            (load_config, save_config, parse_resolution, ...)
       │
       └─ korzysta z:
            ├─ tkinter              (GUI)
            ├─ PIL.Image            (przetwarzanie obrazu)
            ├─ serial (pośrednio)   (przez SerialHandler)
            └─ queue, threading     (pośrednio, przez SerialHandler)
```

## Opis modułów

### `main.py` — Punkt wejścia

Tworzy instancję `tk.Tk()` i przekazuje ją do konstruktora `MainWindow`. Uruchamia główną pętlę zdarzeń tkinter (`root.mainloop()`). Nie zawiera żadnej logiki biznesowej.

### `protocol.py` — Definicje protokołu

Zawiera wszystkie stałe definiujące format komunikacji między Pico a Pythonem:

- **`SYNC_BYTES`** = `bytes([0x55, 0xAA])` — 2-bajtowy nagłówek każdej ramki
- **`HEADER_SIZE`** = 2 — rozmiar nagłówka w bajtach
- **`FRAME_WIDTH`** = 324, **`FRAME_HEIGHT`** = 244 — natywne wymiary sensora
- **`FRAME_SIZE`** = 324 × 244 = 79 056 — rozmiar payloadu jednej ramki
- **`RESOLUTIONS`** — słownik dostępnych rozdzielczości docelowych
- **`BAUD_RATES`** — lista obsługiwanych prędkości transmisji
- **`JPEG_QUALITY`** = 95 — jakość kompresji JPEG
- **`PREVIEW_SIZE`** = (200, 200) — wymiary podglądu w GUI
- **`FRAME_QUEUE_MAXSIZE`** = 100 — maksymalna liczba ramek w kolejce
- **`POLL_INTERVAL_MS`** = 50 — interwał odpytywania kolejki ramek w GUI

### `serial_handler.py` — Obsługa portu szeregowego

Klasa `SerialHandler` zarządza połączeniem szeregowym w osobnym wątku. Główne elementy:

- **`connect(port, baud)`** — otwiera `serial.Serial`, uruchamia wątek odczytu
- **`disconnect()`** — zatrzymuje wątek, zamyka port, czyści kolejkę
- **`_read_loop()`** — pętla wątku: czyta dane z portu do bufora, wywołuje `_extract_frame()`, wrzuca ramki do `frame_queue`
- **`_extract_frame(buf)`** — szuka sync bytes w buforze, wycina 79 056-bajtowy payload
- **`frame_queue`** — `queue.Queue(maxsize=100)` — thread-safe kolejka ramek

Szczegółowy opis w [serial-handler.md](serial-handler.md).

### `app.py` — GUI i logika aplikacji

Klasa `MainWindow` zawiera całą logikę aplikacji. Główne sekcje:

| Metoda / Grupa | Odpowiedzialność |
|----------------|------------------|
| `_build_ui()` | Konstrukcja interfejsu (settings, preview, capture, log) |
| `_build_settings()` | Panel ustawień: port, baud, rozdzielczość, katalog, klasa |
| `_build_preview()` | Panel podglądu na żywo (200×200 canvas) |
| `_build_capture()` | Panel przechwytywania: duration, przyciski, progress bar |
| `_build_log()` | Panel logów (scrolled text widget) |
| `_restore_config()` | Odtwarzanie zapisanych ustawień z `config.json` |
| `start_capture()` | Rozpoczyna sesję (walidacja, odliczanie 3-2-1) |
| `stop_capture()` | Kończy sesję (zatrzymuje timer, loguje statystyki) |
| `_poll_frames()` | Co 50ms opróżnia `frame_queue`, deleguje do `_process_frame()` lub `_preview_frame()` |
| `_process_frame(raw)` | Rekonstruuje obraz z surowych bajtów → resize → JPEG |
| `_preview_frame(raw)` | Aktualizuje podgląd na żywo (bez zapisu) |
| `_scan_subdirectories()` | Skanuje podkatalogi w wybranym folderze (lista klas) |
| `_check_renumber()` | Oferuje przenumerowanie istniejących obrazów |

### `utils.py` — Narzędzia pomocnicze

| Funkcja | Opis |
|---------|------|
| `load_config()` | Wczytuje `config.json`, scala z domyślnymi wartościami |
| `save_config(config)` | Zapisuje konfigurację do `config.json` |
| `get_next_index(directory)` | Znajduje następny wolny indeks dla nazwy pliku JPEG |
| `sanitize_class_name(name)` | Czyści nazwę klasy (usuwa niedozwolone znaki) |
| `parse_resolution(text)` | Parsuje tekst rozdzielczości (np. `"324×244"`) na krotkę `(w, h)` |
| `count_images(directory)` | Zlicza pliki `.jpg` w katalogu |
| `renumber_images(directory, start=0)` | Przenumerowuje pliki `.jpg` sekwencyjnie od `start` |

## Przepływ sterowania

```
[Użytkownik klika Connect]
  → _toggle_connect()
  → SerialHandler.connect(port, baud)
  → Uruchomienie wątku _read_loop()
  → _poll_frames() zaczyna odbierać ramki

[Wątek SerialHandler._read_loop()]
  → serial.read() → buf.extend(chunk)
  → _extract_frame(buf) → payload (79056 bajtów)
  → frame_queue.put(payload)

[GUI _poll_frames() co 50ms]
  → frame_queue.get_nowait()
  → jeśli capturing: _process_frame(raw)
  → jeśli idle: _preview_frame(raw)

[Użytkownik klika START CAPTURE]
  → start_capture() → walidacja → odliczanie 3-2-1-GO!
  → capturing = True
  → Każda ramka z _poll_frames() → _process_frame()
  → Po upływie duration → _auto_stop() → stop_capture()
```

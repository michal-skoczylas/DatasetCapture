# Pipeline przechwytywania obrazu — krok po kroku

Ten dokument opisuje szczegółowo całą ścieżkę, jaką pokonuje pojedyncza klatka obrazu — od sensora kamery, przez transmisję szeregową, aż po zapis pliku JPEG na dysku.

---

## Przegląd pipeline'u

```
 ┌──────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌──────────────┐
 │  HM01B0      │    │  Raspberry Pi   │    │  Python         │    │  Dysk        │
 │  Sensor      │───▶│  Pico (firmware)│───▶│  serial_handler │───▶│  0000.jpg    │
 │  324×244 px  │    │  USB/Serial     │    │  → Image→JPEG   │    │              │
 └──────────────┘    └─────────────────┘    └─────────────────┘    └──────────────┘
```

---

## Etap 1: Sensor HM01B0

**Kamera**: Himax HM01B0 — monochromatyczny sensor CMOS o niskim poborze mocy.

Parametry natywne:
- Rozdzielczość: **324 × 244 pikseli**
- Głębia koloru: **8 bitów na piksel** (odcienie szarości, 0-255)
- Format danych: każdy bajt = 1 piksel, wartość 0 (czarny) do 255 (biały)
- Rozmiar surowej klatki: **324 × 244 = 79 056 bajtów**

Sensor jest podłączony bezpośrednio do Raspberry Pi Pico przez dedykowany interfejs równoległy (8-bitowy VPIO). Pico odczytuje klatki z sensora w czasie rzeczywistym i przesyła je dalej przez USB.

---

## Etap 2: Firmware Raspberry Pi Pico

Firmware na Pico implementuje prosty protokół ramkowy dla transmisji USB/Serial.

### Struktura ramki

Każda ramka składa się z dokładnie **79 058 bajtów**:

| Offset | Rozmiar | Pole | Wartość | Opis |
|--------|---------|------|---------|------|
| 0 | 2 bajty | Sync header | `0x55 0xAA` | Znacznik początku ramki |
| 2 | 79 056 bajtów | Payload | dane pikseli | Surowa klatka 324×244, raster-scan order |

**Ważne cechy protokołu:**
- Ramka ma **stały rozmiar** — nie ma pola długości, nie ma stop bajta
- Protokół jest **bezstanowy** — każda ramka jest niezależna, początek wyznaczają wyłącznie sync bytes
- Piksele przesyłane są w naturalnej kolejności: od lewej do prawej, od góry do dołu (raster-scan)
- Brak kompresji po stronie Pico — przesyłane są surowe dane pikseli

### Dlaczego akurat 0x55 0xAA?

Sekwencja `0x55 0xAA` ma korzystne właściwości na poziomie elektrycznym:
- `0x55` = `01010101` — maksymalnie częste przejścia między stanami, ułatwia synchronizację zegara UART
- `0xAA` = `10101010` — dopełnienie bitowe 0x55, minimalizuje ryzyko fałszywego wykrycia

---

## Etap 3: Odczyt danych z portu szeregowego

### Połączenie

```python
import serial
ser = serial.Serial(port, baud, timeout=0.5)
```

- **Port**: np. `/dev/cu.usbmodem11101` (macOS) lub `COM3` (Windows)
- **Baud**: domyślnie 115200, opcjonalnie 230400 / 460800 / 921600
- **Timeout**: 0.5s — zapobiega blokowaniu wątku gdy brak danych

### Architektura wątkowa

Odczyt z portu szeregowego odbywa się w **osobnym wątku** (`threading.Thread`), co zapobiega blokowaniu głównego wątku GUI. Komunikacja między wątkiem a GUI odbywa się przez **thread-safe kolejkę** `queue.Queue`.

```
┌─────────────────────────┐     frame_queue (Queue)     ┌──────────────────────┐
│  Wątek odczytu          │                             │  Główny wątek GUI     │
│  _read_loop()           │  ──── put(payload) ───▶    │  _poll_frames()       │
│                         │                             │  co 50ms              │
│  serial.read()          │                             │  get_nowait()         │
│  _extract_frame()       │                             │  _process_frame()     │
└─────────────────────────┘                             └──────────────────────┘
```

### Pętla odczytu (`_read_loop()`)

```python
buf = bytearray()
while self._running:
    if self.ser.in_waiting:
        chunk = self.ser.read(self.ser.in_waiting)  # odczytaj wszystkie dostępne bajty
        buf.extend(chunk)                            # dołącz do bufora

    while True:
        frame, consumed = self._extract_frame(buf)   # próbuj wyciąć ramkę
        if frame is None:
            if consumed > 0:
                buf = buf[consumed:]                 # usuń niepotrzebne bajty z początku
            break                                     # za mało danych — czekaj na więcej
        self.frame_queue.put_nowait(frame)            # wrzuć ramkę do kolejki
        buf = buf[consumed:]                          # usuń przetworzone bajty z bufora
```

**Kluczowe decyzje projektowe:**

1. **Odczyt wszystkich dostępnych bajtów na raz** — `ser.in_waiting` zwraca liczbę bajtów czekających w buforze systemowym; odczyt wszystkich minimalizuje liczbę wywołań systemowych.

2. **Bufor `bytearray`** — akumuluje dane między wywołaniami `serial.read()`. Może zawierać fragmenty wielu ramek lub niekompletne ramki.

3. **Pętla wewnętrzna `while True`** — wielokrotnie próbuje wyciąć ramki z bufora, dopóki `_extract_frame()` zwraca dane. Pozwala to obsłużyć wiele ramek odebranych w jednym chunku.

4. **Kolejka z limitem** — `queue.Queue(maxsize=100)` zapobiega niekontrolowanemu wzrostowi pamięci gdy GUI nie nadąża z przetwarzaniem. Gdy kolejka jest pełna, najstarsza ramka jest usuwana (drop-oldest policy).

---

## Etap 4: Ekstrakcja ramki z ciągu bajtów (`_extract_frame()`)

To najważniejsza funkcja w całym pipeline. Jej zadaniem jest znalezienie kompletnej ramki w ciągłym strumieniu bajtów.

### Algorytm

```python
def _extract_frame(self, buf):
    # Krok 1: Znajdź sekwencję sync
    sync_idx = buf.find(SYNC_BYTES)           # szukaj 0x55 0xAA
    if sync_idx == -1:
        # Nie znaleziono sync — zachowaj tylko ostatnie HEADER_SIZE-1 bajtów
        # (na wypadek gdyby sync było rozdzielone między chunki)
        keep = min(HEADER_SIZE - 1, len(buf))
        discard = len(buf) - keep
        return None, discard

    # Krok 2: Sprawdź czy bufor zawiera kompletną ramkę
    frame_total = HEADER_SIZE + FRAME_SIZE    # 2 + 79056 = 79058
    if len(buf) - sync_idx < frame_total:
        # Za mało danych po sync — czekaj na więcej
        # Usuń wszystko przed sync (to śmieci)
        return None, sync_idx

    # Krok 3: Wytnij payload
    payload_start = sync_idx + HEADER_SIZE    # pomiń 2 bajty sync
    payload = bytes(buf[payload_start:payload_start + FRAME_SIZE])

    # Krok 4: Zwróć payload i pozycję końca ramki
    return payload, sync_idx + frame_total
```

### Ilustracja działania

Załóżmy, że bufor zawiera dane:

```
[ ...śmieci... | 0x55 0xAA | PIXEL_0 PIXEL_1 ... PIXEL_79055 | 0x55 0xAA | PIXEL_0 ... ]
                ↑                                              ↑
                sync_idx                                       sync_idx + 79058
                └─────────── frame_total = 79058 ─────────────┘
```

Funkcja zwraca:
- `frame` = `bytes([PIXEL_0, PIXEL_1, ..., PIXEL_79055])` — surowy payload 79 056 bajtów
- `consumed` = `sync_idx + 79058` — liczba bajtów do usunięcia z bufora

### Obsługa przypadków brzegowych

| Sytuacja | Zachowanie |
|----------|------------|
| Brak sync bytes w buforze | Zachowaj ostatnie 1 bajt (może być częścią sync 0x55 0xAA rozbitego między chunki), resztę wyrzuć |
| Sync znalezione, ale za mało danych | Usuń dane przed sync (śmieci), zachowaj sync + wszystko za nim |
| Sync znalezione, wystarczająco danych | Wytnij payload, zwróć go, usuń całą ramkę z bufora |

---

## Etap 5: Rekonstrukcja obrazu (`_process_frame()`)

Główny wątek GUI odbiera surowy payload z kolejki i tworzy z niego obiekt obrazu PIL.

### Walidacja rozmiaru

```python
def _process_frame(self, raw):
    if len(raw) != FRAME_SIZE:           # FRAME_SIZE = 79056
        self._log(f"Unexpected frame size: {len(raw)} bytes")
        return                            # odrzuć nieprawidłową ramkę
```

Sprawdzanie odbywa się zawsze wobec **stałej `FRAME_SIZE` (79 056)**, nie wobec `capture_w * capture_h`. To ważne — rozdzielczość wybrana przez użytkownika (np. 324×324) nie zmienia tego, co wysyła firmware. Rozmiar ramki zależy wyłącznie od sprzętu.

### Tworzenie obrazu PIL

```python
img = Image.frombytes("L", (FRAME_WIDTH, FRAME_HEIGHT), raw)
```

- **Tryb `"L"`** — 8-bitowy grayscale (Luminance). Każdy bajt payloadu staje się wartością jasności piksela.
- **Wymiary** — zawsze `(324, 244)`, czyli natywna rozdzielczość sensora.

Wewnętrznie PIL alokuje bufor 324×244 bajtów i kopiuje do niego dane z `raw`. Kolejność danych (raster-scan) jest naturalnie zgodna z oczekiwaniami PIL — pierwsze 324 bajty to pierwszy wiersz, kolejne 324 to drugi wiersz, itd.

**Dlaczego `"L"` a nie `"RGB"`?**
- Sensor HM01B0 jest monochromatyczny — każdy piksel to pojedyncza wartość 0-255
- Tryb `"L"` przechowuje 1 bajt na piksel, podczas gdy `"RGB"` wymagałby 3 bajtów
- Mniejszy rozmiar w pamięci, szybsze przetwarzanie, naturalne dopasowanie do danych z sensora

---

## Etap 6: Opcjonalna zmiana rozdzielczości (resize)

Użytkownik może wybrać docelową rozdzielczość różną od natywnej (np. 162×162, 81×81, 324×324).

```python
saved = img                                              # domyślnie: obraz natywny

if self.capture_w != FRAME_WIDTH or self.capture_h != FRAME_HEIGHT:
    if self.auto_resize:
        saved = img.resize((self.capture_w, self.capture_h), Image.LANCZOS)
    else:
        self._log(f"Frame {self.capture_w}×{self.capture_h} ≠ sensor {FRAME_WIDTH}×{FRAME_HEIGHT}")
```

**Dwie strategie:**

1. **Auto-resize włączony**: obraz jest skalowany do wybranej rozdzielczości przy użyciu filtra Lanczos (wysokiej jakości resampling). PIL woła `img.resize()` — skalowanie FROM natywne (324×244) TO docelowe (np. 162×162).

2. **Auto-resize wyłączony**: obraz jest zapisywany w natywnej rozdzielczości, ale w logu pojawia się ostrzeżenie o niezgodności. Użytkownik wie, że wybrana rozdzielczość nie została zastosowana.

---

## Etap 7: Zapis do pliku JPEG

```python
filename = f"{self.capture_next_idx:04d}.jpg"    # np. "0042.jpg"
filepath = os.path.join(self.capture_save_dir, filename)
saved.save(filepath, "JPEG", quality=JPEG_QUALITY)  # quality = 95
```

- **Nazewnictwo**: pliki nazywane są sekwencyjnie od `0000.jpg`, `0001.jpg`, ... — indeks pobierany z `get_next_index()` na początku sesji
- **Format**: JPEG z jakością 95 (wysoka jakość, niska kompresja — priorytet dla zachowania detali w zbiorze danych)
- **Ścieżka**: `{katalog}/{klasa}/XXXX.jpg` — struktura katalogów umożliwia proste ładowanie datasetu (folder = etykieta klasy)

### Co dzieje się wewnątrz `Image.save()`?

PIL wykonuje następujące operacje:
1. Jeśli obraz jest w trybie `"L"` (grayscale), konwertuje dane do 8-bitowego JPEG
2. Stosuje kompresję JPEG z zadaną jakością (95 = minimalna kompresja stratna)
3. Zapisuje nagłówek JPEG (SOI, DQT, SOF, SOS, dane skompresowane, EOI)
4. Zapisuje całość do pliku na dysku

---

## Etap 8: Aktualizacja stanu i UI

```python
self.capture_next_idx += 1       # następny indeks pliku
self.capture_count += 1          # licznik zapisanych w tej sesji
self.last_saved_var.set(f"Last: {filename}")

# Podgląd co trzecią klatkę (oszczędność CPU)
if self.capture_count <= 3 or self.capture_count % 3 == 0:
    self._update_preview(img)
```

---

## Podsumowanie: pełna ścieżka danych

```
Sensor HM01B0                         Python PIL                    Dysk
┌──────────┐   ┌─────────────┐   ┌──────────────┐   ┌─────────┐   ┌──────────┐
│ 324×244  │   │ Pico UART   │   │ serial.read()│   │ Image.  │   │ plik     │
│ pikseli  │──▶│ USB/Serial  │──▶│ buf + extract│──▶│ frombytes│──▶│ JPEG     │
│ 8-bit    │   │ 115200 baud │   │ → frame_queue│   │ → resize │   │ quality95│
│ grayscale│   │ 79056 B/ramka│   │   (Queue)    │   │ → save() │   │          │
└──────────┘   └─────────────┘   └──────────────┘   └─────────┘   └──────────┘
     │              │                   │                  │              │
     │   sprzęt     │   firmware        │   Python         │   Python     │   system plików
     │              │                   │                  │              │
   ~30 FPS      każda ramka          wątek daemon      główny wątek    XXXX.jpg
               z headerem           kolejka FIFO        PIL + JPEG
               0x55 0xAA           max 100 ramek
```

---

## Wzorzec do wykorzystania w przyszłych projektach

Powyższy pipeline można zaadaptować do dowolnej kamery szeregowej zmieniając tylko:

| Element | Co zmienić | Gdzie |
|---------|-----------|------|
| Sync bytes | `SYNC_BYTES` w `protocol.py` | Inny firmware → inna sekwencja startowa |
| Rozmiar ramki | `FRAME_WIDTH`, `FRAME_HEIGHT`, `FRAME_SIZE` | Inny sensor → inne wymiary |
| Tryb obrazu | `Image.frombytes("L", ...)` → `"RGB"`, `"RGBA"`, itd. | Kamera kolorowa → 3 bajty na piksel |
| Format zapisu | `saved.save(..., "JPEG")` → `"PNG"`, `"BMP"` | Potrzeba bezstratnej kompresji |
| Kolejność pikseli | Jeśli inna niż raster-scan → transpozycja w `_process_frame()` | Niestandardowy firmware |

**Najważniejsze lekcje architektoniczne:**

1. **Oddziel wątek I/O od GUI** — serial.read() w osobnym wątku + `queue.Queue` jako bufor
2. **Protokół bezstanowy** — każda ramka samodzielna, bez zależności od poprzednich
3. **Waligracja rozmiaru** — zawsze sprawdzaj `len(raw)` przed tworzeniem obrazu
4. **Fixed-size frames** — prostsze niż variable-length z polem rozmiaru
5. **Drop-oldest w kolejce** — gdy GUI nie nadąża, odrzucaj stare klatki zamiast blokować

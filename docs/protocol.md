# Specyfikacja protokołu komunikacji

Protokół definiuje format danych przesyłanych między Raspberry Pi Pico (firmware HM01B0) a aplikacją Python przez USB/Serial.

## Definicje w `protocol.py`

```python
SYNC_BYTES = bytes([0x55, 0xAA])
HEADER_SIZE = 2

FRAME_WIDTH = 324
FRAME_HEIGHT = 244
FRAME_SIZE = FRAME_WIDTH * FRAME_HEIGHT   # = 79056

RESOLUTIONS = {
    "324×244": (324, 244),
    "324×324": (324, 324),
    "162×162": (162, 162),
    "81×81":   (81, 81),
}

BAUD_RATES = [115200, 230400, 460800, 921600]
DEFAULT_BAUD = 115200
DEFAULT_RESOLUTION = "324×244"
DEFAULT_DURATION = 10
JPEG_QUALITY = 95
MAX_CLASS_HISTORY = 10
PREVIEW_SIZE = (200, 200)
FRAME_QUEUE_MAXSIZE = 100
POLL_INTERVAL_MS = 50
```

## Format ramki

```
┌────────────┬──────────────────────────────────┐
│  Bajty 0-1 │  Bajty 2-79057                   │
│  2 bajty   │  79056 bajtów                    │
├────────────┼──────────────────────────────────┤
│  SYNC      │  PAYLOAD (surowa klatka)          │
│  0x55 0xAA │  324×244 pikseli, 8-bit grayscale │
└────────────┴──────────────────────────────────┘
   HEADER_SIZE          FRAME_SIZE
   = 2                  = 79056

   Całkowity rozmiar ramki = HEADER_SIZE + FRAME_SIZE = 79058 bajtów
```

## Szczegóły

### Sync Bytes (0x55, 0xAA)

- Pełnią rolę znacznika początku ramki (frame delimiter)
- Sekwencja 2-bajtowa, wybrana ze względu na korzystne właściwości elektryczne przy transmisji UART
- `0x55` = `01010101` — naprzemienne bity ułatwiają synchronizację zegara
- `0xAA` = `10101010` — dopełnienie 0x55, minimalizuje ryzyko fałszywego wykrycia w danych
- Wyszukiwane przez `buf.find(SYNC_BYTES)` w buforze bajtów

### Payload (79056 bajtów)

- Reprezentuje kompletną klatkę obrazu z sensora HM01B0
- Każdy bajt to jeden piksel w formacie 8-bit grayscale (0 = czarny, 255 = biały)
- Piksele w kolejności raster-scan: od lewej do prawej, od góry do dołu
- Brak kompresji — surowe dane z sensora
- Brak paddingu — dokładnie 324×244 = 79056 bajtów

### Cechy protokołu

| Cecha | Opis |
|-------|------|
| Typ ramki | Fixed-size (stały rozmiar) |
| Nagłówek | 2 bajty sync, bez pola długości |
| Stopka | Brak |
| Stanowość | Bezstanowy — każda ramka jest niezależna |
| Kompresja | Brak — surowe dane pikseli |
| Kontrola błędów | Brak na poziomie protokołu (UART zapewnia podstawową integralność) |

## Dostępne rozdzielczości docelowe

Rozdzielczości w `RESOLUTIONS` definiują, do jakich wymiarów użytkownik może chcieć skalować obraz. Sensor zawsze dostarcza 324×244 — resize odbywa się po stronie Pythona.

| Etykieta | Wymiary | Uwagi |
|----------|---------|-------|
| 324×244 | 324 × 244 | Natywna rozdzielczość sensora — bez resize |
| 324×324 | 324 × 324 | Kwadratowy kadr (rozciągnięcie w pionie) |
| 162×162 | 162 × 162 | Połowa natywnej (¼ pikseli) |
| 81×81 | 81 × 81 | Ćwierć natywnej (1/16 pikseli) |

Użytkownik może też wpisać własną rozdzielczość — funkcja `parse_resolution()` w `utils.py` obsługuje formaty `WxH`, `W×H`, `W H`.

## Prędkości transmisji

Zdefiniowane w `BAUD_RATES`, domyślnie `115200`.

| Baud | Bajtów/sekundę | Ramek/sekundę (teoretycznie) | Uwagi |
|------|----------------|------------------------------|-------|
| 115200 | ~11 520 | ~0.15 | Domyślna, stabilna |
| 230400 | ~23 040 | ~0.29 | |
| 460800 | ~46 080 | ~0.58 | |
| 921600 | ~92 160 | ~1.16 | Maksymalna, może być niestabilna |

Przy 115200 baud, pełna ramka (79 058 bajtów) zajmuje ~6.9 sekundy transmisji. W praktyce firmware Pico wysyła ramki z prędkością ok. 30 FPS, ale ograniczeniem jest przepustowość UART — im wyższy baud, tym więcej ramek na sekundę może być przesłanych.

## Stałe pomocnicze

| Stała | Wartość | Zastosowanie |
|-------|---------|--------------|
| `JPEG_QUALITY` | 95 | Parametr kompresji JPEG (1-100, 95 = wysoka jakość) |
| `PREVIEW_SIZE` | (200, 200) | Wymiary podglądu live w GUI |
| `FRAME_QUEUE_MAXSIZE` | 100 | Limit kolejki ramek (zapobiega wyciekom pamięci) |
| `POLL_INTERVAL_MS` | 50 | Jak często GUI sprawdza kolejkę ramek (20 razy/s) |
| `DEFAULT_DURATION` | 10 | Domyślny czas przechwytywania w sekundach |
| `MAX_CLASS_HISTORY` | 10 | Historyczny limit (nieużywany w aktualnej wersji) |

## Ewolucja protokołu

Protokół ewoluował z bardziej złożonej wersji z 4-bajtowym sync (`0xAA 0xBB 0xCC 0xDD`), polem długości i stop bajtem. Został uproszczony do 2-bajtowego sync i stałego rozmiaru ramki, co:
- Zmniejszyło złożoność parsowania
- Wyeliminowało potrzebę maszyny stanów w parserze
- Uprościło firmware po stronie Pico
- Zmniejszyło narzut na ramkę z ~10 do 2 bajtów

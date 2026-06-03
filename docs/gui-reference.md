# Interfejs użytkownika (GUI)

Aplikacja wykorzystuje **tkinter** (standardowa biblioteka GUI Pythona) ze stylowaniem **ttk clam theme**.

## Układ okna

```
┌──────────────────────────────────────────────────────┐
│  Dataset Capture Tool                          _ □ ✕ │
├───────────────────────┬──────────────────────────────┤
│  ╔ Settings ═══════  │  ╔ Live Preview ═══════════  │
│  Port: [COM3 ▼]      │  ┌────────────────────┐      │
│  Baud: [115200 ▼] [↻]│  │                    │      │
│  Res:  [324×244 ▼]   │  │    (200×200 px)    │      │
│  [ ] Auto-resize     │  │    podgląd live     │      │
│  Dir:  [____] [Browse]│  │                    │      │
│  Class:[____▼]        │  └────────────────────┘      │
│  → /path/class/       │                              │
│  [Connect] ● Disconnected                            │
├───────────────────────┴──────────────────────────────┤
│  ╔ Capture ═══════════════════════════════════════  │
│  Duration: [10] s  [▶ START CAPTURE] [■ STOP]       │
│                                                      │
│                    GO!                               │
│  [████████████░░░░░░░░░░] 5.2s / 10s  Images: 42    │
│                                         Last: 0041   │
├──────────────────────────────────────────────────────┤
│  ╔ Log ═══════════════════════════════════════════  │
│  [12:00:01] Connected COM3 @ 115200 baud            │
│  [12:00:05] Capture session – class: "OpenHand"     │
│  [12:00:15] Capture finished – 42 saved (142 total) │
└──────────────────────────────────────────────────────┘
```

## Sekcje UI

### 1. Settings (lewy górny panel)

| Kontrolka | Typ | Zmienna | Opis |
|-----------|-----|---------|------|
| Port | `Combobox` (readonly) | `port_var` | Wybór portu szeregowego; lista odświeżana przy kliknięciu |
| Baud | `Combobox` (readonly) | `baud_var` | Prędkość transmisji: 115200, 230400, 460800, 921600 |
| ↻ | `Button` | — | Ręczne odświeżenie listy portów |
| Res | `Combobox` | `res_var` | Rozdzielczość docelowa (można wpisać własną) |
| Auto-resize | `Checkbutton` | `auto_resize_var` | Czy skalować do wybranej rozdzielczości |
| Dir | `Entry` + `Button` | `dir_var` | Katalog zapisu (podgląd: `→ /path/[class]`) |
| Class | `Combobox` (editable) | `class_var` | Nazwa klasy/podkatalogu; lista wypełniana z podkatalogów |
| → path | `Label` | `path_preview_var` | Podgląd pełnej ścieżki `dir/class/` |
| Connect | `Button` | — | Connect / Disconnect (toggle) |
| Status | `Label` | `status_var` | ● Disconnected (czerwony) / ● Connected (zielony) |

### 2. Live Preview (prawy górny panel)

- `Canvas` 200×200 px z ciemnym tłem (`#1e1e1e`)
- Pokazuje podgląd ostatniej odebranej klatki na żywo (gdy połączony, ale nie przechwytuje)
- Podczas capture — podgląd aktualizowany co trzecią klatkę
- Placeholder "No image" gdy brak połączenia

### 3. Capture (środkowy panel)

| Kontrolka | Opis |
|-----------|------|
| Duration `Spinbox` | Czas przechwytywania 1-300 sekund |
| ▶ START CAPTURE | Rozpoczyna odliczanie 3-2-1-GO!, potem przechwytywanie |
| ■ STOP | Zatrzymuje przechwytywanie przed czasem |
| Review | Otwiera okno podglądu z bounding boxami (aktywny po zakończeniu capture) |
| Countdown label | Duży tekst 3, 2, 1, GO! podczas odliczania |
| `Progressbar` | Pasek postępu (0-100%) |
| `time_var` | Pozostały czas (np. "5.2s / 10s") |
| `saved_var` | Liczba zapisanych obrazów (np. "Images: 42") |
| `last_saved_var` | Nazwa ostatniego pliku (np. "Last: 0041.jpg") |

### 5. Review Window (osobne okno)

Otwierane przyciskiem **Review** po zakończeniu sesji capture.

```
┌────────────────────────────────────────────────────────┐
│  Review Captured Images                          _ □ ✕ │
├────────────────────────────────────────────────────────┤
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │                                                  │  │
│  │              (640×480 px)                        │  │
│  │         zdjęcie z bbox i etykietami              │  │
│  │                                                  │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  [← Prev]     Image 5 / 42  (0004.jpg)     [Next →]   │
│                                                 [Close]│
│                                                        │
│  Padding: ═══════════●══════════════  10 px            │
└────────────────────────────────────────────────────────┘
```

| Element | Opis |
|---------|------|
| Canvas | 640×480 px, ciemne tło, wyświetla zdjęcie z bbox |
| Bounding box | Prostokąt w kolorze zależnym od class_id + nazwa klasy |
| ← Prev / Next → | Nawigacja między zdjęciami (również strzałki ← →) |
| Counter | "Image X / N (filename)" |
| Padding slider | Suwak 0–50 px, domyślnie 10 px — bufor wokół bbox |
| Close | Zamyka okno (również Escape) |

**Kolory bbox**: czerwony, zielony, niebieski, żółty, magenta, cyan — cyklicznie dla różnych class_id.

**Padding bbox**: Suwak pozwala regulować odstęp między prostokątem bbox a wykrytym obiektem. Wartość 0 px = bbox dokładnie przylega, wyższe wartości dodają bufor w pikselach.

### 4. Log (dolny panel)

- `Text` widget (read-only) z ciemnym tłem i jasnym tekstem
- Każda linia z timestampem `[HH:MM:SS]`
- Automatycznie przewijany do końca (`see(END)`)
- Zdarzenia: połączenie, początek/koniec capture, błędy, ostrzeżenia

---

## Flow użytkownika

### Ścieżka 1: Szybki start (pierwsze użycie)

1. Uruchom `python main.py`
2. Wybierz port z listy (kliknij dropdown — lista odświeży się automatycznie)
3. Kliknij **Connect**
4. Podgląd live pojawi się automatycznie (jeśli Pico wysyła ramki)
5. Kliknij **Browse** → wybierz katalog zapisu
6. Wpisz nazwę klasy (lub wybierz z dropdowna — lista wypełni się podkatalogami)
7. Ustaw czas trwania (domyślnie 10s)
8. Kliknij **START CAPTURE** → odliczanie 3-2-1-GO! → przechwytywanie
9. Po zakończeniu: log pokaże statystyki

### Ścieżka 2: Ponowne użycie

1. Aplikacja automatycznie przywraca: ostatni port, baud, katalog, rozdzielczość, duration
2. Kliknij **Connect** → **START CAPTURE** → gotowe

### Ścieżka 3: Zmiana klasy z istniejącymi danymi

1. Wybierz katalog i wpisz/kliknij nazwę klasy, dla której już istnieją pliki JPEG
2. Pojawi się okno dialogowe: "Found N images... Renumber them?"
3. Jeśli potwierdzisz: pliki zostaną przenumerowane od `0000.jpg`
4. Nowe obrazy będą zapisywane z kolejnymi indeksami

---

## Skróty klawiaturowe

| Klawisz | Działanie |
|---------|-----------|
| `Escape` | Stop capture (jeśli trwa) LUB Disconnect (jeśli połączony) LUB Close review window |
| `←` / `→` | W Review Window: nawigacja między zdjęciami |

---

## Stany interfejsu

### Stan: Disconnected

- Przycisk Connect: "Connect"
- Status: ● Disconnected (czerwony)
- Preview: "No image"
- START CAPTURE: aktywny (ale walidacja i tak wymaga połączenia)

### Stan: Connected (idle)

- Przycisk Connect: "Disconnect"
- Status: ● Connected (zielony)
- Preview: podgląd live z kamery
- START CAPTURE: aktywny

### Stan: Countdown (3-2-1)

- Duży tekst odliczania w panelu capture
- START CAPTURE: nieaktywny
- STOP: nieaktywny (dopiero po rozpoczęciu capture)
- Duration: zablokowany

### Stan: Capturing

- Pasek postępu aktywny
- Licznik czasu i obrazów aktualizowany
- START CAPTURE: nieaktywny
- STOP: aktywny
- Duration: zablokowany

### Stan: Po zakończeniu

- Pasek postępu: 100%
- Czas: "Done (X.Xs)"
- START CAPTURE: aktywny
- STOP: nieaktywny
- Review: aktywny (jeśli zapisano co najmniej 1 obraz)
- Duration: odblokowany

---

## Walidacje i komunikaty błędów

| Warunek | Komunikat |
|---------|-----------|
| Brak wybranego portu przy Connect | "No serial port selected" |
| Błąd połączenia z portem | "Failed to connect:\n{error}" |
| Brak katalogu przy START | "Select a save directory first" |
| Brak klasy przy START | "Enter a class name" |
| Nieprawidłowa rozdzielczość | "Unrecognized resolution format: {text}" |
| Błąd tworzenia katalogu | "Cannot create directory:\n{error}" |
| Nieprawidłowy rozmiar ramki | "Unexpected frame size: {n} bytes (expected 79056), skipped" |
| Błąd przetwarzania ramki | "Frame error: {error}" |

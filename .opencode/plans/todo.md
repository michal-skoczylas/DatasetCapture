# TODO: Podgląd zdjęć z bounding boxami po zakończeniu serii

## Opis
Dodać okno podglądu otwierane przyciskiem "Review" po zakończeniu capture, wyświetlające zapisane zdjęcia z narysowanymi bounding boxami i nazwami klas (z etykiet YOLO).

---

## Zadania

### 1. Nowe funkcje w `utils.py`
- [ ] `load_yolo_labels(txt_path)` — wczytuje plik `.txt` w formacie YOLO (`class_id cx cy bw bh`), zwraca listę słowników `{"class_id": int, "cx": float, "cy": float, "bw": float, "bh": float}`
- [ ] `load_classes_txt(base_dir)` — wczytuje `classes.txt` z katalogu bazowego, zwraca listę nazw klas (indeks = class_id); zwraca pustą listę jeśli plik nie istnieje

### 2. Nowy plik `review_window.py` — klasa `ReviewWindow(tk.Toplevel)`
- [ ] Konstruktor: przyjmuje `parent`, `save_dir` (katalog z ostatniej serii), `classes` (lista nazw klas)
- [ ] Skanuje `save_dir` — zbiera listę plików `.jpg` posortowanych numerycznie
- [ ] UI: Canvas (duży, np. 640×480) + pasek nawigacji (Prev / "Image X/N" / Next) + przycisk Close
- [ ] Ładuje aktualne zdjęcie (`PIL.Image.open`) i skaluje do rozmiaru canvas z zachowaniem proporcji
- [ ] Dla odpowiadającego pliku `.txt` rysuje prostokąty bbox na canvas:
  - Konwersja YOLO (cx, cy, bw, bh) → (x1, y1, x2, y2) w pikselach wyświetlanego obrazu
  - Kolorowy prostokąt (`create_rectangle`) + tekst z nazwą klasy (`create_text`)
  - Różne kolory dla różnych class_id
- [ ] Nawigacja: przyciski Prev/Next + bind na strzałki ← →
- [ ] Obsługa braku pliku `.txt` (zdjęcie bez bbox — brak detekcji)
- [ ] Obsługa pustego katalogu (komunikat "No images to review")

### 3. Zmiany w `app.py`
- [ ] Import `ReviewWindow` z `review_window`
- [ ] Dodanie atrybutu `self._review_window = None`
- [ ] Dodanie przycisku "Review" w sekcji Capture (`_build_capture`), domyślnie `state=DISABLED`
- [ ] Metoda `_open_review()` — tworzy `ReviewWindow` z `self.capture_save_dir` i załadowanymi klasami
- [ ] `stop_capture()` — enable przycisku Review po zakończeniu capture (jeśli `capture_count > 0`)
- [ ] `_reset_capture_ui()` — disable przycisku Review przy resetowaniu UI

### 4. Aktualizacja dokumentacji
- [ ] `AGENTS.md` — dodanie wpisu z sesji
- [ ] `docs/gui-reference.md` — dodanie sekcji Review Window

---

## Szczegóły implementacyjne

### Format YOLO → piksele
```
cx, cy, bw, bh (znormalizowane 0.0–1.0)
img_w, img_h = wymiary wyświetlanego obrazu na canvas

x1 = (cx - bw/2) * img_w
y1 = (cy - bh/2) * img_h
x2 = (cx + bw/2) * img_w
y2 = (cy + bh/2) * img_h
```

### Kolory bbox
- Lista kolorów (np. `["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"]`)
- `color = colors[class_id % len(colors)]`

### Skalowanie z zachowaniem proporcji
- Obraz skalowany do max rozmiaru canvas (np. 640×480) z `Image.thumbnail()`
- Bbox rysowany w坐标系 wyświetlanego obrazu (uwzględniając offset centrowania na canvas)

### Struktura plików w `save_dir`
```
save_dir/
  0000.jpg
  0000.txt    ← etykiety YOLO (opcjonalny)
  0001.jpg
  0001.txt
  ...
```
Plik `classes.txt` znajduje się w katalogu bazowym (`os.path.dirname(save_dir)`).

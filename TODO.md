# TODO — Review Window: slider & filters

## Steps

### [x] Step 1 — Enhance `_scan_images()` + `_apply_filters()`
- `_scan_images()` czyta pliki `.txt`, buduje listę `_all_images` z metadanymi (`filename`, `annotated`, `class_ids`)
- Nowa metoda `_apply_filters()` filtruje `_all_images` → `_images` wg `_filter_annotated` i `_filter_class`
- Domyślnie oba filtry = `"all"` / `-1`, więc zachowanie identyczne jak przed zmianą

### [ ] Step 2 — Slider nawigacji
- Dodać `ttk.Scale` między canvas a padding slider
- `from_=1`, `to=len(self._images)`, `command=self._on_slider_move`
- `_on_slider_move(value)` → `int(float(value)) - 1` → `_show_image(idx)` (tylko jeśli indeks się zmienił)
- `_show_image()` na końcu aktualizuje pozycję slidera: `self.slider.set(idx + 1)`
- Nowa metoda `_update_slider()`: `config(to=...)` + `set(current_idx + 1)`

### [ ] Step 3 — Filtry UI (annotation + class)
- Nowy `ttk.Frame` nad canvas z dwoma `ttk.Combobox` (readonly):
  - **Annotation**: `["All", "Annotated", "Unannotated"]`, domyślnie `"All"`
  - **Class**: `["All classes"] + self._classes`, domyślnie `"All classes"`
- Gdy `self._classes` jest pusty — class combobox disabled

### [ ] Step 4 — Podłączenie filtrów
- `_on_filter_change()` — odczytuje wartości z comboboxów:
  - annotation: `"all"` / `"annotated"` / `"unannotated"`
  - class: `-1` (All classes) lub indeks z listy klas
- Wywołuje `_apply_filters()`, potem `_show_image(0)` jeśli są wyniki, lub `_show_empty_filtered()`

### [ ] Step 5 — Geometry i polish
- Zwiększyć height okna: `140` → `220` (dodatkowe ~80px na filtr + slider)
- `_show_empty()` zmienić na `_show_empty_filtered()` — inny komunikat gdy filtry nie zwracają wyników
- Slider przy jednym obrazku: zakres 1..1, nieruchomy

---

## Jak testować

### Testowanie logiki filtrów (bez GUI):
```bash
python3 -c "
import os, tempfile, sys
sys.path.insert(0, '.')
from utils import save_yolo_label
from PIL import Image

tmpdir = tempfile.mkdtemp()
for i in range(5):
    img = Image.new('L', (100, 100))
    img.save(os.path.join(tmpdir, f'{i:04d}.jpg'))

save_yolo_label(os.path.join(tmpdir, '0000.jpg'), [{'x1':0.1,'x2':0.3,'y1':0.1,'y2':0.3}], class_id=0)
save_yolo_label(os.path.join(tmpdir, '0002.jpg'), [{'x1':0.2,'x2':0.4,'y1':0.2,'y2':0.4}], class_id=1)

from review_window import ReviewWindow  # sprawdza import + składnię
print('Import OK')
import shutil; shutil.rmtree(tmpdir)
"
```

### Testowanie całości (GUI):
1. Uruchom aplikację: `python main.py`
2. Wybierz katalog ze zdjęciami (musi zawierać `.jpg` i opcjonalnie `.txt`)
3. Kliknij **Review**
4. Sprawdź:
   - Slider przesuwa się między obrazkami
   - Przeciągnięcie slidera zmienia obrazek
   - Filtry annotation/class działają:
     - "Annotated" pokazuje tylko zdjęcia z `.txt`
     - "Unannotated" pokazuje tylko zdjęcia bez `.txt`
     - "All" pokazuje wszystkie
     - Class filter pokazuje tylko zdjęcia z daną klasą w labelach

### Testowanie skrajnych przypadków:
- Pusty katalog → komunikat "No images to review"
- Wszystkie zdjęcia bez `.txt` + filtr "Annotated" → "No images matching filter"
- 1 zdjęcie → slider nieruchomy, Prev/Next disabled

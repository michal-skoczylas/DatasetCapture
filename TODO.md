# TODO — Review Window: slider & filters

Wszystkie kroki zakończone. Nowy układ `review_window.py`:

```
Filter: [All ▼]  [All classes ▼]
┌───────────────────────────────────┐
│          Canvas 640×480           │
└───────────────────────────────────┘
Image: ─────────○──────────────────
Padding: ─────○────── 10 px
[← Prev]  Image 1/5  [Next →] [Close]
```

---

## Nowe funkcje

### Slider nawigacji
- `ttk.Scale` "Image:" — przeciąganie zmienia obrazek, kliknięcie skacze do pozycji
- Synchronizuje się z Prev/Next i strzałkami ← →
- Przy 1 obrazku nieruchomy, przy braku wyników — disabled

### Filtry
- **Annotation**: All / Annotated / Unannotated
- **Class**: All classes + lista z `classes.txt`
- Po zmianie filtra: pokazuje 1-szy obrazek z wyników lub komunikat "No images matching filter"
- Class combobox disabled gdy brak `classes.txt`

### Logika wewnętrzna
- `_all_images` — pełna lista z metadanymi (filename, annotated, class_ids)
- `_apply_filters()` — filtruje wg `_filter_annotated` / `_filter_class`
- `_images` — przefiltrowana lista nazw plików

---

## Jak testować (GUI)

1. `python main.py` → Browse → katalog ze zdjęciami z `.txt` i bez
2. Kliknij Review

Sprawdź:
- [ ] Slider Image: przesuwa obrazki, synchronizuje się z Prev/Next
- [ ] Filtr Annotated: pokazuje tylko zdjęcia z bounding boxami
- [ ] Filtr Unannotated: pokazuje tylko zdjęcia bez labeli
- [ ] Filtr Class: filtruje po konkretnej klasie
- [ ] Kombinacje filtrów (np. Annotated + konkretna klasa)
- [ ] Filtr dający 0 wyników → komunikat "No images matching filter"
- [ ] Powrót do "All" → przywraca wszystkie obrazki
- [ ] 1 obrazek → slider nieruchomy, Prev/Next disabled
- [ ] Pusty katalog → "No images to review"

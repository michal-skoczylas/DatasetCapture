# Konfiguracja — `utils.py` i `config.json`

## Plik konfiguracyjny

Aplikacja przechowuje ustawienia użytkownika w pliku `config.json` w katalogu głównym projektu.

### Lokalizacja

```python
CONFIG_FILE = Path(__file__).parent / "config.json"
```

Plik znajduje się zawsze w tym samym katalogu co `utils.py` (główny katalog projektu), niezależnie od bieżącego katalogu roboczego.

### Format

```json
{
  "last_port": "/dev/cu.usbmodem11101",
  "last_baud": 115200,
  "last_directory": "/Users/user/dataset",
  "last_resolution": "324×244",
  "auto_resize": false,
  "last_duration": 10.0,
  "class_history": []
}
```

### Domyślne wartości (`DEFAULT_CONFIG`)

```python
DEFAULT_CONFIG = {
    "last_port": "",                                                # pusty string — żaden port
    "last_baud": DEFAULT_BAUD,                                     # 115200
    "last_directory": str(Path.home() / "dataset"),                 # ~/dataset
    "last_resolution": DEFAULT_RESOLUTION,                         # "324×244"
    "auto_resize": False,                                          # wyłączone
    "last_duration": DEFAULT_DURATION,                             # 10
    "class_history": [],                                           # pusta lista (nieużywane)
}
```

| Klucz | Typ | Domyślnie | Opis |
|-------|-----|-----------|------|
| `last_port` | string | `""` | Ostatnio używany port szeregowy |
| `last_baud` | int | `115200` | Ostatnia prędkość transmisji |
| `last_directory` | string | `~/dataset` | Ostatni wybrany katalog zapisu |
| `last_resolution` | string | `"324×244"` | Ostatnia rozdzielczość docelowa |
| `auto_resize` | bool | `false` | Czy automatycznie skalować obraz |
| `last_duration` | float | `10.0` | Ostatni czas przechwytywania (sekundy) |
| `class_history` | list | `[]` | Historia klas (pole zachowane dla kompatybilności, nieużywane) |

---

## Funkcje konfiguracyjne

### `load_config()`

```python
def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                saved = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(saved)
                return cfg
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()
```

**Logika**:
1. Jeśli plik `config.json` istnieje:
   - Wczytaj JSON
   - Skopiuj `DEFAULT_CONFIG` jako bazę
   - Nadpisz wartościami z pliku (`cfg.update(saved)`)
   - Dzięki temu nowe klucze dodane w przyszłości będą miały wartości domyślne
2. Jeśli plik nie istnieje lub jest uszkodzony:
   - Zwróć kopię `DEFAULT_CONFIG`

**Merge a nie replace**: `DEFAULT_CONFIG.copy()` + `.update(saved)` zapewnia, że nawet jeśli `config.json` jest niekompletny (np. ze starszej wersji aplikacji), brakujące klucze dostaną wartości domyślne.

### `save_config(config)`

```python
def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except IOError:
        pass
```

Zapisuje konfigurację z formatowaniem (2-spacjowy indent). Błędy I/O są ignorowane — brak uprawnień do zapisu nie powinien crashować aplikacji.

---

## Kiedy konfiguracja jest zapisywana

| Moment | Co jest zapisywane | Gdzie w kodzie |
|--------|--------------------|----------------|
| Kliknięcie **START CAPTURE** | port, baud, directory, resolution, auto_resize, duration | `start_capture()` w `app.py` |
| Zamknięcie okna (WM_DELETE_WINDOW) | port, baud, directory, resolution, auto_resize, duration | `_on_close()` w `app.py` |

Zapis przy starcie capture zapewnia, że nawet jeśli aplikacja zostanie zabita (force quit), ostatnie poprawne ustawienia zostaną zachowane.

Zapis przy zamknięciu okna zapewnia, że wszelkie zmiany dokonane PO ostatnim capture (np. zmiana portu bez rozpoczynania capture) też zostaną zapisane.

---

## Kiedy konfiguracja jest wczytywana

| Moment | Gdzie w kodzie |
|--------|----------------|
| Start aplikacji (`MainWindow.__init__`) | `self.config = load_config()` |
| Następnie przywracana do UI | `_restore_config()` |

`_restore_config()` wypełnia kontrolki UI wartościami z configu:
- `dir_var`, `port_var`, `baud_var`, `res_var`, `auto_resize_var`, `duration_var`
- Następnie odświeża listę portów i aktualizuje podgląd ścieżki

Port jest przywracany tylko jeśli nadal istnieje w systemie:
```python
if cfg.get("last_port") in self.serial.list_ports():
    self.port_var.set(cfg["last_port"])
```

---

## Funkcje pomocnicze w `utils.py`

### `get_next_index(directory)`

```python
def get_next_index(directory):
    if not os.path.isdir(directory):
        return 1
    max_idx = 0
    for fname in os.listdir(directory):
        if fname.endswith(".jpg"):
            try:
                idx = int(os.path.splitext(fname)[0])
                max_idx = max(max_idx, idx)
            except ValueError:
                pass
    return max_idx + 1
```

Znajduje następny dostępny indeks dla nazwy pliku JPEG. Przeszukuje katalog, wyciąga numery z nazw plików (np. `0042.jpg` → 42), zwraca `max_idx + 1`. Jeśli katalog nie istnieje, zwraca 1.

### `sanitize_class_name(name)`

```python
def sanitize_class_name(name):
    keep = {"_", "-"}
    cleaned = "".join(c if c.isalnum() or c in keep else "_" for c in name)
    return cleaned.strip("_") or "unknown"
```

Czyści nazwę klasy użytkownika do bezpiecznej nazwy katalogu:
- Dozwolone: litery, cyfry, `_`, `-`
- Niedozwolone znaki zastępowane `_`
- Usuwa `_` z początku i końca
- Jeśli po czyszczeniu pusty string → `"unknown"`

### `parse_resolution(text)`

```python
def parse_resolution(text):
    if text in RESOLUTIONS:
        return RESOLUTIONS[text]
    # regex: WxH, W×H, W H
    m = re.match(r'^\s*(\d{1,5})\s*[×xX,\s]\s*(\d{1,5})\s*$', text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w < 1 or h < 1:
            raise ValueError(f"Invalid resolution: {text}")
        return w, h
    raise ValueError(f"Unrecognized resolution format: {text}")
```

Parsuje tekst rozdzielczości na krotkę `(width, height)`. Akceptuje formaty:
- `"324×244"` (znak mnożenia Unicode)
- `"324x244"` (litera x)
- `"324 244"` (spacja)
- `"324,244"` (przecinek)

Najpierw sprawdza predefiniowane rozdzielczości w `RESOLUTIONS`, potem próbuje regex.

### `count_images(directory)`

```python
def count_images(directory):
    if not os.path.isdir(directory):
        return 0
    return sum(1 for f in os.listdir(directory) if f.endswith(".jpg"))
```

Zwraca liczbę plików `.jpg` w katalogu. Używane po zakończeniu capture do wyświetlenia całkowitej liczby obrazów oraz przy `_check_renumber()`.

### `renumber_images(directory, start=0)`

```python
def renumber_images(directory, start=0):
    if not os.path.isdir(directory):
        return 0
    files = [f for f in os.listdir(directory) if f.endswith(".jpg")]
    n = len(files)
    if n == 0:
        return 0

    def sort_key(fname):
        try:
            return (0, int(os.path.splitext(fname)[0]))
        except ValueError:
            return (1, fname)

    files.sort(key=sort_key)
    # Faza 1: tymczasowe nazwy
    tmp_prefix = "_rn_tmp_"
    for i, old_name in enumerate(files):
        os.rename(os.path.join(directory, old_name),
                  os.path.join(directory, f"{tmp_prefix}{i}.tmp"))
    # Faza 2: docelowe nazwy
    for i in range(n):
        os.rename(os.path.join(directory, f"{tmp_prefix}{i}.tmp"),
                  os.path.join(directory, f"{start + i:04d}.jpg"))
    # Sprzątanie
    for fname in os.listdir(directory):
        if fname.startswith(tmp_prefix) and fname.endswith(".tmp"):
            os.remove(os.path.join(directory, fname))
    return n
```

Przenumerowuje wszystkie pliki `.jpg` w katalogu od `start` (domyślnie 0), format `0000.jpg`.

**Dlaczego dwufazowo (przez tymczasowe nazwy)?**

Gdyby zmieniać nazwy bezpośrednio (np. `0020.jpg` → `0005.jpg`), mogłoby dojść do konfliktu nazw jeśli plik `0005.jpg` już istnieje. Przez tymczasowe nazwy (`_rn_tmp_0.tmp`) unikamy kolizji:

```
Faza 1: 0020.jpg → _rn_tmp_0.tmp          (wszystkie dostają bezpieczne nazwy)
        0005.jpg → _rn_tmp_1.tmp
Faza 2: _rn_tmp_0.tmp → 0000.jpg          (teraz można bezpiecznie nadać docelowe)
        _rn_tmp_1.tmp → 0001.jpg
```

**Sortowanie**: pliki sortowane są numerycznie po prefiksie (np. `0005.jpg` przed `0020.jpg`), z fallbackiem do sortowania alfabetycznego dla plików bez numerycznej nazwy.

# Obsługa portu szeregowego — `serial_handler.py`

Moduł `serial_handler.py` zawiera klasę `SerialHandler`, która zarządza połączeniem szeregowym z Raspberry Pi Pico i ekstrahuje ramki obrazu z ciągłego strumienia bajtów.

## Klasa `SerialHandler`

### Inicjalizacja

```python
class SerialHandler:
    def __init__(self):
        self.ser = None              # obiekt serial.Serial
        self._thread = None          # wątek odczytu
        self._running = False        # flaga zatrzymania wątku
        self.frame_queue = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)  # 100
        self.connected = False       # stan połączenia
        self._lock = threading.Lock()  # mutex dla operacji connect/disconnect
```

### `connect(port, baud)`

Nawiązuje połączenie szeregowe i uruchamia wątek odczytu.

```python
def connect(self, port, baud):
    with self._lock:
        if self.connected:
            self.disconnect()         # rozłącz jeśli już połączony
        self.ser = serial.Serial(port, baud, timeout=0.5)
        self.connected = True
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
```

**Parametry `serial.Serial`**:
- `port` — nazwa portu (np. `/dev/cu.usbmodem11101`, `COM3`)
- `baud` — prędkość transmisji (115200, 230400, 460800, 921600)
- `timeout=0.5` — timeout odczytu w sekundach; zapobiega blokowaniu `read()` gdy brak danych

**Wątek daemon** — `daemon=True` oznacza, że wątek zostanie automatycznie zabity przy zamknięciu programu, nawet jeśli pętla odczytu nadal działa.

### `disconnect()`

Bezpiecznie zamyka połączenie.

```python
def disconnect(self):
    with self._lock:
        self._running = False         # sygnalizuj wątkowi żeby się zatrzymał
        self.connected = False
    if self._thread and self._thread.is_alive():
        self._thread.join(timeout=2.0)  # czekaj max 2s na zakończenie wątku
    if self.ser and self.ser.is_open:
        try:
            self.ser.close()           # zamknij port
        except Exception:
            pass
    # Wyczyść kolejkę ramek
    while True:
        try:
            self.frame_queue.get_nowait()
        except queue.Empty:
            break
```

**Kolejność operacji jest istotna:**
1. Ustaw `_running = False` — sygnał dla wątku
2. Poczekaj na zakończenie wątku (`join`)
3. Zamknij port szeregowy
4. Wyczyść kolejkę — zapobiega przetwarzaniu starych ramek po ponownym połączeniu

### `list_ports()` (statyczna)

```python
@staticmethod
def list_ports():
    return [p.device for p in serial.tools.list_ports.comports()]
```

Zwraca listę dostępnych portów szeregowych. Wywoływana przy otwarciu dropdowna portów i przy starcie aplikacji.

---

## Pętla odczytu (`_read_loop()`)

To serce modułu — działa w osobnym wątku i nieprzerwanie czyta dane z portu.

```python
def _read_loop(self):
    buf = bytearray()
    while self._running:
        try:
            if self.ser.in_waiting:
                chunk = self.ser.read(self.ser.in_waiting)
                buf.extend(chunk)
        except serial.SerialException:
            self.connected = False
            break
        except Exception:
            time.sleep(0.01)
            continue

        while True:
            frame, consumed = self._extract_frame(buf)
            if frame is None:
                if consumed > 0:
                    buf = buf[consumed:]
                break
            try:
                self.frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    self.frame_queue.get_nowait()
                    self.frame_queue.put_nowait(frame)
                except queue.Empty:
                    pass
            buf = buf[consumed:]
```

### Szczegółowy opis działania

**1. Odczyt danych z portu**

```python
if self.ser.in_waiting:
    chunk = self.ser.read(self.ser.in_waiting)
    buf.extend(chunk)
```

- `ser.in_waiting` — liczba bajtów dostępnych w buforze systemowym (nieblokujące)
- `ser.read(n)` — odczytuje do `n` bajtów; blokuje maksymalnie `timeout` sekund jeśli brak danych
- `buf.extend(chunk)` — dokleja nowe dane do istniejącego bufora

**Dlaczego nie używamy `ser.read()` z timeoutem w pętli?** Bo `in_waiting` daje nam informację ile danych jest gotowych — możemy odczytać wszystko na raz zamiast bajt po bajcie.

**2. Obsługa błędów**

```python
except serial.SerialException:
    self.connected = False
    break
```

`SerialException` jest rzucane gdy port został odłączony fizycznie (kabel wypięty). Wtedy wątek kończy działanie, a `connected` ustawiane jest na `False`.

```python
except Exception:
    time.sleep(0.01)
    continue
```

Inne wyjątki (np. chwilowe problemy z odczytem) są ignorowane — wątek czeka 10ms i próbuje dalej.

**3. Ekstrakcja ramek (pętla wewnętrzna)**

```python
while True:
    frame, consumed = self._extract_frame(buf)
    if frame is None:
        if consumed > 0:
            buf = buf[consumed:]
        break
    ...
    buf = buf[consumed:]
```

Pętla wewnętrzna wielokrotnie próbuje wyciąć ramkę z bufora:
- Jeśli `_extract_frame()` zwróci ramkę → wrzuć do kolejki, usuń przetworzone bajty, spróbuj ponownie (może być więcej ramek)
- Jeśli `_extract_frame()` zwróci `None` → usuń niepotrzebne bajty, wyjdź z pętli wewnętrznej, wróć do odczytu z portu

Dzięki temu pojedynczy duży `chunk` z `serial.read()` może zawierać wiele ramek — wszystkie zostaną przetworzone w jednej iteracji.

**4. Wrzucanie do kolejki (drop-oldest)**

```python
try:
    self.frame_queue.put_nowait(frame)
except queue.Full:
    try:
        self.frame_queue.get_nowait()   # usuń najstarszą
        self.frame_queue.put_nowait(frame)  # wstaw nową
    except queue.Empty:
        pass
```

Gdy kolejka jest pełna (100 ramek), najstarsza ramka jest usuwana, a nowa wstawiana. To zapobiega:
- Blokowaniu wątku odczytu (gdyby `put()` czekało)
- Nieograniczonemu wzrostowi pamięci (każda ramka to 79 KB, 100 ramek = ~7.9 MB)

---

## Ekstrakcja ramki (`_extract_frame()`)

```python
def _extract_frame(self, buf):
    sync_idx = buf.find(SYNC_BYTES)     # szukaj 0x55 0xAA
    if sync_idx == -1:
        keep = min(HEADER_SIZE - 1, len(buf))
        discard = len(buf) - keep
        return None, discard

    frame_total = HEADER_SIZE + FRAME_SIZE
    if len(buf) - sync_idx < frame_total:
        return None, sync_idx

    payload_start = sync_idx + HEADER_SIZE
    payload = bytes(buf[payload_start:payload_start + FRAME_SIZE])

    return payload, sync_idx + frame_total
```

### Zwracane wartości

Funkcja zwraca krotkę `(frame, consumed)`:

| Przypadek | `frame` | `consumed` | Znaczenie |
|-----------|---------|------------|-----------|
| Brak sync | `None` | `len(buf) - (HEADER_SIZE - 1)` | Wyrzuć większość bufora, zachowaj ostatnie 1-2 bajty |
| Sync znalezione, za mało danych | `None` | `sync_idx` | Wyrzuć dane przed sync, zachowaj sync + resztę |
| Pełna ramka | `bytes` (79056 B) | `sync_idx + 79058` | Zwróć payload, usuń całą ramkę z bufora |

### Dlaczego zachowujemy `HEADER_SIZE - 1` bajtów?

Bufor jest wypełniany chunkami z `serial.read()`. Może się zdarzyć, że sync bytes `0x55 0xAA` zostaną rozdzielone między dwa chunki:

```
Chunk 1: ... 0x55     ← koniec chucka
Chunk 2: 0xAA ...     ← początek następnego
```

Bez zachowania ostatniego bajta, `0x55` zostałoby wyrzucone, a `0xAA` z następnego chucka nie zostałoby rozpoznane jako sync. Zachowując `HEADER_SIZE - 1 = 1` bajt, mamy pewność że nie zgubimy rozpoczętego sync.

---

## Diagram stanu bufora

```
Stan początkowy: buf = []

serial.read() → chunk = [0x12, 0x34, 0x55, 0xAA, (79056 bajtów payloadu), 0x55, ...]
buf = [0x12, 0x34, 0x55, 0xAA, (payload#1), 0x55, ...]

_extract_frame():
  sync_idx = 2 (pozycja 0x55 0xAA)
  frame_total = 79058
  payload = buf[4:79060] → payload#1 (79056 bajtów)
  consumed = 2 + 79058 = 79060
  return (payload#1, 79060)

buf = buf[79060:] → [0x55, ... (reszta payloadu#2)]

_extract_frame():
  sync_idx = 0
  jeśli za mało danych → return (None, 0), break

serial.read() → chunk = [(reszta payloadu#2)]
buf.extend(chunk) → [0x55, 0xAA, (payload#2)]

_extract_frame():
  sync_idx = 0
  frame_total = 79058, len(buf)-0 >= 79058 → OK
  payload = buf[2:79058] → payload#2
  return (payload#2, 79058)

buf = buf[79058:] → []
```

---

## Współbieżność (thread safety)

| Operacja | Synchronizacja |
|----------|---------------|
| `connect()` / `disconnect()` | `self._lock` (mutex) |
| `frame_queue.get_nowait()` | Wbudowana w `queue.Queue` (thread-safe) |
| `frame_queue.put_nowait()` | Wbudowana w `queue.Queue` |
| `self._running` | Python GIL (atomic dla prostych przypisań) |
| `self.connected` | Python GIL + częściowo chroniony przez `_lock` w connect/disconnect |

Uwaga: `self.connected` nie jest w pełni thread-safe (czytane poza lockiem w `_toggle_connect()`), ale w praktyce nie powoduje to problemów ze względu na GIL i charakter operacji.

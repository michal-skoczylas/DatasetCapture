# Dataset Capture Tool — Dokumentacja

Narzędzie do przechwytywania klatek obrazu z kamery **Pico HM01B0** przez interfejs USB/Serial i zapisywania ich jako plików JPEG w katalogach podzielonych na klasy.

## Szybki start

```bash
pip install -r requirements.txt
python main.py
```

1. Wybierz port szeregowy i kliknij **Connect**
2. Wybierz katalog zapisu (**Browse**) i wpisz nazwę klasy
3. Ustaw rozdzielczość docelową i czas trwania
4. Kliknij **START CAPTURE** — po 3-sekundowym odliczaniu rozpocznie się przechwytywanie

## Spis treści

| Dokument | Opis |
|----------|------|
| [architecture.md](architecture.md) | Architektura projektu — podział na moduły, relacje między nimi |
| [image-capture.md](image-capture.md) | ★ **Pipeline przechwytywania obrazu krok po kroku** — od sprzętu do pliku JPEG |
| [protocol.md](protocol.md) | Specyfikacja protokołu komunikacji — format ramki, sync bytes, stałe |
| [serial-handler.md](serial-handler.md) | Obsługa portu szeregowego — wątek odczytu, buforowanie, ekstrakcja ramek |
| [gui-reference.md](gui-reference.md) | Interfejs użytkownika — układ, kontrolki, flow aplikacji |
| [configuration.md](configuration.md) | Format `config.json` i mechanizm persistencji ustawień |

## Wymagania

- Python 3.7+
- `pyserial >= 3.5`
- `Pillow >= 10.0`
- Raspberry Pi Pico z firmware HM01B0 podłączone przez USB

## Pliki źródłowe

| Plik | Linie | Opis |
|------|-------|------|
| `main.py` | 15 | Punkt wejścia — tworzy okno tkinter i uruchamia pętlę zdarzeń |
| `app.py` | 680 | Główna klasa `MainWindow` — GUI, logika przechwytywania, przetwarzanie ramek |
| `serial_handler.py` | 95 | Klasa `SerialHandler` — wątkowy odczyt z portu szeregowego, ekstrakcja ramek z ciągu bajtów |
| `protocol.py` | 23 | Stałe współdzielone: sync bytes, wymiary ramki, prędkości transmisji |
| `utils.py` | 195 | Narzędzia: persistencja konfiguracji, zliczanie/numerowanie plików, parsowanie rozdzielczości, ładowanie etykiet YOLO |
| `review_window.py` | 155 | Klasa `ReviewWindow` — okno podglądu zdjęć z bounding boxami |

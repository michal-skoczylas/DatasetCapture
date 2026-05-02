import queue
import threading
import time

import serial
import serial.tools.list_ports

from protocol import SYNC_BYTES, HEADER_SIZE, FRAME_SIZE, FRAME_QUEUE_MAXSIZE


class SerialHandler:
    def __init__(self):
        self.ser = None
        self._thread = None
        self._running = False
        self.frame_queue = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
        self.connected = False
        self._lock = threading.Lock()

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect(self, port, baud):
        with self._lock:
            if self.connected:
                self.disconnect()
            self.ser = serial.Serial(port, baud, timeout=0.5)
            self.connected = True
            self._running = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()

    def disconnect(self):
        with self._lock:
            self._running = False
            self.connected = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        while True:
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break

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

    def _extract_frame(self, buf):
        sync_idx = buf.find(SYNC_BYTES)
        if sync_idx == -1:
            keep = min(HEADER_SIZE - 1, len(buf))
            discard = len(buf) - keep
            return None, discard if discard > 0 else 0

        frame_total = HEADER_SIZE + FRAME_SIZE
        if len(buf) - sync_idx < frame_total:
            return None, sync_idx

        payload_start = sync_idx + HEADER_SIZE
        payload = bytes(buf[payload_start:payload_start + FRAME_SIZE])

        return payload, sync_idx + frame_total

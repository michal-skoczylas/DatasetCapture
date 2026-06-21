import os
import queue
import threading


class DetectionWorker:
    def __init__(self, hand_detector, save_callback, log_callback=None, single_bbox=False):
        self._detector = hand_detector
        self._save_callback = save_callback
        self._log = log_callback or (lambda msg: None)
        self._single_bbox = single_bbox
        self._queue = queue.Queue(maxsize=500)
        self._thread = None
        self._running = False
        self._processed = 0
        self._failed = 0

    def start(self):
        if self._thread is not None:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=10.0)
            self._thread = None

    def enqueue(self, image, save_path, class_id):
        try:
            self._queue.put_nowait((image, save_path, class_id))
            return True
        except queue.Full:
            self._log("Detection queue full, skipping frame")
            return False

    @property
    def queue_size(self):
        return self._queue.qsize()

    @property
    def processed(self):
        return self._processed

    @property
    def failed(self):
        return self._failed

    def _run(self):
        while self._running:
            try:
                img, save_path, class_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                bboxes = self._detector.detect(img)
                
                if bboxes and self._single_bbox and len(bboxes) > 1:
                    bboxes.sort(key=lambda b: b.get("confidence", 0.0), reverse=True)
                    bboxes = [bboxes[0]]

                if bboxes:
                    self._save_callback(save_path, bboxes, class_id)
                    self._processed += 1
                else:
                    self._log(f"No hand detected in {os.path.basename(save_path)}")
                    self._failed += 1

            except Exception as e:
                self._log(f"Detection error for {os.path.basename(save_path)}: {e}")
                self._failed += 1
            finally:
                self._queue.task_done()

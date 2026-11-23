"""Bounded incremental parser for the device's MJPEG upload body."""
from smart_parking.domain.exceptions import DomainException


class MjpegParser:
    def __init__(self):
        self.buffer = bytearray()
        self.length = None
        self.frame_id = ""
        self.finished = False

    def feed(self, data: bytes):
        if self.finished:
            if data:
                self.fail()
            return []
        self.buffer.extend(data)
        frames = []
        while True:
            if self.length is None:
                if self.buffer.startswith(b"--frame--\r\n"):
                    del self.buffer[:11]
                    self.finished = True
                    if self.buffer:
                        self.fail()
                    break
                end = self.buffer.find(b"\r\n\r\n")
                if end < 0:
                    if len(self.buffer) > 2048:
                        self.fail()
                    break
                if end > 2048:
                    self.fail()
                try:
                    lines = self.buffer[:end].decode("ascii").split("\r\n")
                    if lines.pop(0) != "--frame":
                        self.fail()
                    headers = {}
                    for line in lines:
                        key, value = line.split(":", 1)
                        key = key.strip().lower()
                        if key in headers:
                            self.fail()
                        headers[key] = value.strip()
                    self.length = int(headers["content-length"])
                    self.frame_id = headers["x-frame-id"]
                    if headers.get("content-type") != "image/jpeg" or not 64 <= self.length <= 5 * 1024 * 1024 or len(self.frame_id) > 95:
                        self.fail()
                except (ValueError, KeyError, UnicodeError):
                    self.fail()
                del self.buffer[:end + 4]
            if len(self.buffer) < self.length + 2:
                break
            if self.buffer[self.length:self.length + 2] != b"\r\n":
                self.fail()
            frames.append((self.frame_id, bytes(self.buffer[:self.length])))
            del self.buffer[:self.length + 2]
            self.length = None
        return frames

    def finish(self):
        if not self.finished or self.buffer or self.length is not None:
            self.fail()

    @staticmethod
    def fail():
        raise DomainException("Invalid MJPEG multipart body.", reason_code="INVALID_MJPEG", http_status=400)

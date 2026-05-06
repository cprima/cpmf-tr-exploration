"""HTTP audio streaming sessions.

LiveStreamSession   — ffmpeg pipe, no Range support.
                      Good for radio, TTS, generated audio.

CachedStreamSession — serves a static file with full Range + Content-Length.
                      Enables accurate seeking.

Both sessions use a per-instance UUID path:
    /session/<uuid>/stream.mp3
This prevents stale Raumfeld reconnects from hitting a new session.
"""

import logging
import subprocess
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

log = logging.getLogger(__name__)

CHUNK = 65536


# ─── Shared handler base ──────────────────────────────────────────────────────


class _BaseHandler(BaseHTTPRequestHandler):
    def log_message(self, *_) -> None:
        pass

    def _reject(self, code: int = 404) -> None:
        self.send_error(code)


# ─── Live (pipe) ──────────────────────────────────────────────────────────────


class _LiveHandler(_BaseHandler):
    session: "LiveStreamSession | None" = None

    def do_GET(self) -> None:
        s = _LiveHandler.session
        if s is None or self.path != s.path:
            self._reject()
            return

        log.info("[live] client %s connected  path=%s", self.client_address[0], self.path)
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Connection", "close")
        self.end_headers()

        proc = subprocess.Popen(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "warning",
                "-reconnect",
                "1",
                "-reconnect_streamed",
                "1",
                "-i",
                s.audio_url,
                "-vn",
                "-f",
                "mp3",
                "-b:a",
                "192k",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=None,
        )
        s._register(proc)
        try:
            while chunk := proc.stdout.read(CHUNK):
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            log.info("[live] client disconnected")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            s._unregister(proc)
            log.info("[live] ffmpeg stopped")


class LiveStreamSession:
    def __init__(self, audio_url: str, local_ip: str, port: int = 8080) -> None:
        self.audio_url = audio_url
        self.local_ip = local_ip
        self.port = port
        self.path = f"/session/{uuid.uuid4().hex}/stream.mp3"
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._procs: list[subprocess.Popen] = []

    @property
    def stream_url(self) -> str:
        return f"http://{self.local_ip}:{self.port}{self.path}"

    def start(self) -> None:
        _LiveHandler.session = self
        self._server = HTTPServer(("0.0.0.0", self.port), _LiveHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="live-http"
        )
        self._thread.start()
        log.info("[live] serving  %s", self.stream_url)

    def stop(self) -> None:
        with self._lock:
            for p in self._procs:
                p.terminate()
        if self._server:
            self._server.shutdown()
        log.info("[live] server stopped")

    def _register(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.append(proc)

    def _unregister(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs = [p for p in self._procs if p is not proc]

    def __enter__(self) -> "LiveStreamSession":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


# ─── Cached (static file + Range) ────────────────────────────────────────────


class _CachedHandler(_BaseHandler):
    session: "CachedStreamSession | None" = None

    def do_GET(self) -> None:
        s = _CachedHandler.session
        if s is None or self.path != s.path:
            self._reject()
            return

        size = s.file_size
        range_hdr = self.headers.get("Range", "")
        start, end = 0, size - 1
        status = 200

        if range_hdr.startswith("bytes="):
            parts = range_hdr[6:].split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else size - 1
            end = min(end, size - 1)
            status = 206

        length = end - start + 1
        kind = f"Range bytes={start}-{end}" if status == 206 else "Full"
        log.info("[cache] %s  from %s", kind, self.client_address[0])

        self.send_response(status)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()

        try:
            with open(s.file_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError, OSError):
            log.info("[cache] client disconnected")


class CachedStreamSession:
    def __init__(self, file_path: Path, local_ip: str, port: int = 8080) -> None:
        self.file_path = file_path
        self.file_size = file_path.stat().st_size
        self.local_ip = local_ip
        self.port = port
        self.path = f"/session/{uuid.uuid4().hex}/stream.mp3"
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def stream_url(self) -> str:
        return f"http://{self.local_ip}:{self.port}{self.path}"

    def start(self) -> None:
        _CachedHandler.session = self
        self._server = HTTPServer(("0.0.0.0", self.port), _CachedHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="cache-http"
        )
        self._thread.start()
        mb = self.file_size / 1024 / 1024
        log.info("[cache] serving %s  (%.1f MB, Range-capable)", self.stream_url, mb)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
        log.info("[cache] server stopped")

    def __enter__(self) -> "CachedStreamSession":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

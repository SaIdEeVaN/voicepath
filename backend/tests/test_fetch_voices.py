"""The voice download cannot hang a build.

On 2026-11-05 a Render build hung for over fifteen minutes on a voice that
trickled in: the only timeout fired after ten minutes of total silence, which
a slow download never reaches. Served here by a local server, no network.
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.scripts import fetch_voices


class Trickle(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server's name
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.end_headers()
        if self.path == "/whole":
            self.wfile.write(b"voice" * 1000)
            return
        try:
            for _ in range(200):  # a byte every 50 ms: never silent, never done
                self.wfile.write(b"x")
                self.wfile.flush()
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Trickle)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def test_a_whole_file_lands_under_its_name(server, tmp_path):
    target = tmp_path / "voice.onnx"
    fetch_voices._download(f"{server}/whole", target)
    assert target.read_bytes() == b"voice" * 1000
    assert not list(tmp_path.glob("*.part"))


def test_a_trickle_is_cut_off_and_leaves_nothing(server, tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_voices, "PER_FILE_SECONDS", 0.5)
    monkeypatch.setattr(fetch_voices, "CHUNK_BYTES", 1)
    target = tmp_path / "voice.onnx"
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        fetch_voices._download(f"{server}/trickle", target)
    assert time.monotonic() - started < 5
    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))

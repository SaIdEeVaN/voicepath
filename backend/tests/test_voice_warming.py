"""Loading speech voices before anyone asks for one (spec section 4.6).

The first synthesis in a language reads a 63 MB ONNX graph. On a tier that
sleeps after fifteen minutes idle, that happens again after every nap — and it
lands in the worst possible place, because the answer and its audio are two
separate requests. The text arrives, the spinner stops, and *then* the model
loads while the person sits looking at a reply they cannot hear.

Warming moves that read to startup, where nobody is waiting. It does not reduce
the memory a running container holds; it only changes when the read happens.

What these tests protect is the part that could go wrong. Warming touches
application startup, and a missing voice file is a **supported configuration** —
synthesis falls back to the browser's own speech, which is real speech in the
person's language. So nothing about warming may be able to stop the application
starting, and it must stay silent when there is nothing to warm.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import app
from app.services import tts


class TestItNeverBreaksStartup:
    def test_the_app_starts_when_no_voice_file_exists(self, monkeypatch):
        """The offline test environment has no voices at all, which is exactly
        the case that must not raise."""
        monkeypatch.setenv("TTS_PROVIDER", "local")
        monkeypatch.setenv("PIPER_VOICE_DIR", "does/not/exist")
        monkeypatch.setenv("TTS_WARM_LANGUAGES", "ta")
        reload_settings()

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

        monkeypatch.undo()
        reload_settings()

    def test_the_app_starts_when_warming_raises(self, monkeypatch):
        monkeypatch.setenv("TTS_PROVIDER", "local")
        monkeypatch.setenv("TTS_WARM_LANGUAGES", "ta")
        reload_settings()

        async def _explode(languages):
            raise RuntimeError("piper exploded")

        monkeypatch.setattr(tts, "warm", _explode)

        with TestClient(app) as client:
            assert client.get("/health").status_code == 200

        monkeypatch.undo()
        reload_settings()


class TestItWarmsOnlyWhatItShould:
    @pytest.mark.asyncio
    async def test_nothing_is_loaded_when_tts_is_offline(self, monkeypatch):
        """No voice is going to be used, so holding 63 MB would be waste."""
        monkeypatch.setenv("TTS_PROVIDER", "offline")
        reload_settings()

        assert await tts.warm(["ta", "hi", "en"]) == []

        monkeypatch.undo()
        reload_settings()

    @pytest.mark.asyncio
    async def test_a_missing_voice_is_skipped_rather_than_raised(self, monkeypatch):
        monkeypatch.setenv("TTS_PROVIDER", "local")
        monkeypatch.setenv("PIPER_VOICE_DIR", "does/not/exist")
        reload_settings()

        assert await tts.warm(["ta"]) == []

        monkeypatch.undo()
        reload_settings()

    def test_an_empty_setting_warms_nothing(self, monkeypatch):
        monkeypatch.setenv("TTS_WARM_LANGUAGES", "")
        settings = reload_settings()

        assert settings.tts_warm_language_list == []

        monkeypatch.undo()
        reload_settings()

    def test_the_setting_is_a_comma_separated_list(self, monkeypatch):
        monkeypatch.setenv("TTS_WARM_LANGUAGES", "ta, hi")
        settings = reload_settings()

        assert settings.tts_warm_language_list == ["ta", "hi"]

        monkeypatch.undo()
        reload_settings()

    def test_it_defaults_to_the_interface_language(self):
        """Tamil alone. Warming all three would hold roughly 190 MB on a
        512 MB container."""
        assert reload_settings().tts_warm_language_list == ["ta"]

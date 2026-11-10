"""At most N speech voices stay loaded; the least recently used is let go.

On 2026-11-10 at 12:33 UTC Render killed the server for memory, 40 seconds
after Tamil, Hindi and English had all been spoken on top of the embedding
model. A voice is ~105 MB resident once it has spoken, and with the embedder
resident the 512 MB container holds one. The fix is the cap
(config.tts_max_resident_voices) and what /health reports about memory.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.config import reload_settings
from app.services import memory, tts


class FakeVoice:
    loaded: list[str] = []

    def __init__(self, path):
        self.path = path

    @staticmethod
    def load(path):
        FakeVoice.loaded.append(path.rsplit("/", 1)[-1])
        return FakeVoice(path)


@pytest.fixture
def voices(tmp_path, monkeypatch):
    for name in tts.VOICE_FILES.values():
        (tmp_path / name).write_bytes(b"x")
    monkeypatch.setenv("PIPER_VOICE_DIR", str(tmp_path))
    fake = types.ModuleType("piper")
    fake.PiperVoice = FakeVoice
    monkeypatch.setitem(sys.modules, "piper", fake)
    FakeVoice.loaded = []
    monkeypatch.setattr(tts, "_voices", {})
    yield
    reload_settings()


def cap(monkeypatch, n):
    monkeypatch.setenv("TTS_MAX_RESIDENT_VOICES", str(n))
    reload_settings()


class TestTheCap:
    def test_the_default_is_no_limit(self, voices):
        for language in ("ta", "hi", "en"):
            tts._load_voice(language)
        assert list(tts._voices) == ["ta", "hi", "en"]

    def test_one_keeps_only_the_voice_in_use(self, voices, monkeypatch):
        cap(monkeypatch, 1)
        tts._load_voice("ta")
        tts._load_voice("hi")
        assert list(tts._voices) == ["hi"]
        tts._load_voice("en")
        assert list(tts._voices) == ["en"]

    def test_a_voice_in_use_is_not_loaded_again(self, voices, monkeypatch):
        cap(monkeypatch, 1)
        first = tts._load_voice("ta")
        assert tts._load_voice("ta") is first
        assert FakeVoice.loaded == ["ta_IN-rasa_female-medium.onnx"]

    def test_the_least_recently_used_goes_first(self, voices, monkeypatch):
        cap(monkeypatch, 2)
        tts._load_voice("ta")
        tts._load_voice("hi")
        tts._load_voice("ta")          # Tamil is used again: Hindi is now the oldest
        tts._load_voice("en")
        assert sorted(tts._voices) == ["en", "ta"]

    def test_a_released_voice_loads_again_when_asked_for(self, voices, monkeypatch):
        cap(monkeypatch, 1)
        tts._load_voice("ta")
        tts._load_voice("hi")
        tts._load_voice("ta")
        assert FakeVoice.loaded == [
            "ta_IN-rasa_female-medium.onnx",
            "hi_IN-priyamvada-medium.onnx",
            "ta_IN-rasa_female-medium.onnx",
        ]

    def test_a_voice_being_spoken_with_outlives_its_release(self, voices, monkeypatch):
        cap(monkeypatch, 1)
        speaking = tts._load_voice("ta")
        tts._load_voice("hi")           # releases Tamil from the cache only
        assert speaking.path.endswith("ta_IN-rasa_female-medium.onnx")


class TestWhatHealthSaysAboutMemory:
    @pytest.fixture
    def cgroup(self, tmp_path, monkeypatch):
        v2, v1 = tmp_path / "v2", tmp_path / "v1"
        v2.mkdir(), v1.mkdir()
        monkeypatch.setattr(memory, "CGROUP_V2", v2)
        monkeypatch.setattr(memory, "CGROUP_V1", v1)
        return v2, v1

    MB = memory.MB

    def test_the_working_set_leaves_out_cache_the_kernel_may_drop(self, cgroup):
        v2, _ = cgroup
        (v2 / "memory.max").write_text(str(512 * self.MB))
        (v2 / "memory.current").write_text(str(450 * self.MB))
        (v2 / "memory.stat").write_text(f"anon {200 * self.MB}\ninactive_file {80 * self.MB}\n")
        assert memory.working_set_bytes() == 370 * self.MB
        assert memory.snapshot() == {"limit_mb": 512.0, "heap_mb": 200.0, "working_set_mb": 370.0}

    def test_v1(self, cgroup):
        _, v1 = cgroup
        (v1 / "memory.limit_in_bytes").write_text(str(512 * self.MB))
        (v1 / "memory.usage_in_bytes").write_text(str(400 * self.MB))
        (v1 / "memory.stat").write_text(f"total_rss {150 * self.MB}\ntotal_inactive_file {60 * self.MB}\n")
        assert memory.working_set_bytes() == 340 * self.MB

    def test_unreadable_is_none_not_an_error(self, cgroup):
        assert memory.snapshot() == {"limit_mb": None, "heap_mb": None, "working_set_mb": None}

    async def test_health_carries_it(self, cgroup):
        from app.main import health

        v2, _ = cgroup
        (v2 / "memory.max").write_text(str(512 * self.MB))
        (v2 / "memory.current").write_text(str(300 * self.MB))
        (v2 / "memory.stat").write_text(f"anon {120 * self.MB}\n")
        body = await health()
        assert body.memory["limit_mb"] == 512.0
        assert body.memory["working_set_mb"] == 300.0

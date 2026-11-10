"""The server asks how much memory is left before loading a model (2026-11-10).

Read from the container's cgroup; anywhere that cannot be read, the answer is
"unknown" and the model loads as it would have.
"""

from __future__ import annotations

import pytest

from app.services import embeddings, memory

MB = memory.MB


@pytest.fixture
def cgroup(tmp_path, monkeypatch):
    v2, v1 = tmp_path / "v2", tmp_path / "v1"
    v2.mkdir(), v1.mkdir()
    monkeypatch.setattr(memory, "CGROUP_V2", v2)
    monkeypatch.setattr(memory, "CGROUP_V1", v1)
    return v2, v1


class TestReadingTheCgroup:
    def test_v2_limit_and_heap(self, cgroup):
        v2, _ = cgroup
        (v2 / "memory.max").write_text(f"{512 * MB}\n")
        (v2 / "memory.stat").write_text(f"anon {300 * MB}\nfile {90 * MB}\nkernel 1\n")
        assert memory.limit_bytes() == 512 * MB
        assert memory.anon_bytes() == 300 * MB
        assert memory.headroom_mb() == pytest.approx(212)

    def test_file_cache_is_not_counted(self, cgroup):
        v2, _ = cgroup
        (v2 / "memory.max").write_text(str(512 * MB))
        (v2 / "memory.stat").write_text(f"anon {100 * MB}\nfile {400 * MB}\n")
        assert memory.headroom_mb() == pytest.approx(412)

    def test_no_limit_means_unknown(self, cgroup):
        v2, _ = cgroup
        (v2 / "memory.max").write_text("max\n")
        (v2 / "memory.stat").write_text(f"anon {100 * MB}\n")
        assert memory.limit_bytes() is None and memory.headroom_mb() is None

    def test_v1_is_read_when_there_is_no_v2(self, cgroup):
        _, v1 = cgroup
        (v1 / "memory.limit_in_bytes").write_text(str(512 * MB))
        (v1 / "memory.stat").write_text(f"cache 5\nrss {200 * MB}\ntotal_rss {250 * MB}\n")
        assert memory.headroom_mb() == pytest.approx(262)

    def test_v1_unlimited_is_a_huge_number_and_means_unknown(self, cgroup):
        _, v1 = cgroup
        (v1 / "memory.limit_in_bytes").write_text("9223372036854771712")
        (v1 / "memory.stat").write_text(f"total_rss {1 * MB}\n")
        assert memory.headroom_mb() is None

    def test_nothing_readable_means_unknown(self, cgroup):
        assert memory.limit_bytes() is None
        assert memory.anon_bytes() is None
        assert memory.headroom_mb() is None


class TestTheGuard:
    @pytest.fixture(autouse=True)
    def fresh(self, monkeypatch):
        monkeypatch.setattr(embeddings, "_onnx", None)

    def test_too_little_room_is_refused_and_remembered(self, monkeypatch):
        from types import SimpleNamespace

        monkeypatch.setattr(memory, "headroom_mb", lambda: 120.0)
        monkeypatch.setattr(embeddings, "get_settings",
                            lambda: SimpleNamespace(embedding_provider="onnx"))
        with pytest.raises(embeddings.EmbeddingUnavailable, match="Not enough memory"):
            embeddings._load_onnx()
        assert embeddings.recent_failure()["reason"] == "out_of_memory"
        assert embeddings.status()["status"] == "out_of_memory"

    def test_the_embedding_call_raises_what_the_callers_already_catch(self, monkeypatch):
        monkeypatch.setattr(memory, "headroom_mb", lambda: 10.0)
        with pytest.raises(embeddings.EmbeddingUnavailable):
            embeddings._embed_onnx(["passage: x"])

    def test_unknown_headroom_loads_as_before(self, monkeypatch, tmp_path):
        from types import SimpleNamespace

        monkeypatch.setattr(memory, "headroom_mb", lambda: None)
        monkeypatch.setattr(embeddings, "get_settings", lambda: SimpleNamespace(
            embedding_provider="onnx", embedding_model_dir=str(tmp_path), embedding_dimension=384))
        # An empty model directory: it gets past the guard and fails looking for
        # the files (or for onnxruntime), which is not a refusal for memory.
        with pytest.raises(Exception) as caught:  # noqa: PT011 - the kind depends on what is installed
            embeddings._load_onnx()
        assert not isinstance(caught.value, embeddings.EmbeddingUnavailable)
        assert embeddings.recent_failure() is None

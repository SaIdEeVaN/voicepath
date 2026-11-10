"""multilingual-e5-small, running inside the API (decided 2026-11-10).

The Hugging Face Inference API answered 402 from 2026-11-04: out of credits.
The API now runs e5-small itself -- int8 ONNX on onnxruntime, tokenised by
sentencepiece -- whose vectors have 384 numbers, not 768. These hold the
pieces that make that safe: the tokenizer's id mapping, the settings that fall
back when the files are missing, the block while the database's columns are
the old size, the re-embedding of stored passages, migration 015, and the
pinned download. CI has no model files; the one test that runs the real
model is skipped there.
"""

from __future__ import annotations

import hashlib
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app.config import Settings, get_settings
from app.services import corpus_sync, db, embeddings, retrieval
from app.scripts import fetch_embedding_model

MIGRATION = Path(__file__).resolve().parents[2] / "db" / "015_small_embeddings.sql"


class FakePieces:
    """sentencepiece's interface: encode(text) -> piece ids, <unk> = 0."""

    def __init__(self, ids):
        self.ids = ids
        self.seen = None

    def encode(self, text):
        self.seen = text
        return list(self.ids)


class TestTheTokenizer:
    def test_pieces_are_shifted_into_xlm_roberta_ids(self):
        # sentencepiece: <unk>=0, then pieces. fairseq: <s>=0 <pad>=1 </s>=2
        # <unk>=3, every other piece one up.
        assert embeddings._token_ids(FakePieces([0, 5, 9]), "x") == [0, 3, 6, 10, 2]

    def test_whitespace_is_collapsed_first(self):
        pieces = FakePieces([5])
        embeddings._token_ids(pieces, "  query:  I\tweld \n gates  ")
        assert pieces.seen == "query: I weld gates"

    def test_it_stops_at_512_with_the_end_marker(self):
        ids = embeddings._token_ids(FakePieces(range(1, 2000)), "long")
        assert len(ids) == embeddings.MAX_TOKENS
        assert ids[0] == 0 and ids[-1] == 2


class TestTheSettings:
    def test_e5_small_is_the_default(self):
        fields = Settings.model_fields
        assert fields["embedding_provider"].default == "onnx"
        assert fields["embedding_model"].default == "intfloat/multilingual-e5-small"
        assert fields["embedding_dimension"].default == 384

    def test_without_the_model_files_it_is_offline_not_a_500(self, tmp_path):
        settings = Settings(embedding_provider="onnx", embedding_model_dir=str(tmp_path))
        assert settings.embedding_provider == "offline"

    def test_with_the_files_it_stays(self, tmp_path):
        pytest.importorskip("onnxruntime")
        pytest.importorskip("sentencepiece")
        (tmp_path / "model_quantized.onnx").write_bytes(b"x")
        (tmp_path / "sentencepiece.bpe.model").write_bytes(b"x")
        settings = Settings(embedding_provider="onnx", embedding_model_dir=str(tmp_path))
        assert settings.embedding_provider == "onnx"


def columns(size):
    return [
        {"table_name": "skill_taxonomy", "column_name": "embedding", "type": f"vector({size})"},
        {"table_name": "document_chunks", "column_name": "embedding", "type": f"vector({size})"},
    ]


class TestTheOldColumns:
    def test_768_columns_are_a_gap_naming_015(self):
        gaps = db._vector_gaps(columns(768))
        assert len(gaps) == 2
        assert all("vector(768)" in g and "vector(384)" in g and "015_small_embeddings.sql" in g
                   for g in gaps)

    def test_and_block_every_embedding(self):
        db._vector_gaps(columns(768))
        with pytest.raises(embeddings.EmbeddingUnavailable, match="015"):
            embeddings.embed_query("I weld gates")
        assert embeddings.status()["status"] == "dimension_mismatch"

    def test_the_block_lifts_once_they_fit(self):
        db._vector_gaps(columns(768))
        assert db._vector_gaps(columns(384)) == []
        assert embeddings.blocked() is None
        assert len(embeddings.embed_query("I weld gates")) == 384

    def test_health_lists_embeddings_as_degraded(self):
        from app.main import _degraded

        db._vector_gaps(columns(768))
        assert "embeddings" in _degraded(get_settings())

    def test_a_database_without_the_tables_is_not_a_mismatch(self):
        assert db._vector_gaps([]) == []

    async def test_a_skill_said_by_name_is_still_recognised(self):
        """The fallback the block relies on: names and aliases need no vector."""
        from app.services import normalization

        from app.services import taxonomy

        taxonomy.reset_memory_cache()
        db._vector_gaps(columns(768))
        [welding] = await normalization.normalize_many([("welding", "I do welding")],
                                                       use_llm_assist=False)
        assert welding.code == "SK022"
        taxonomy.reset_memory_cache()

    async def test_catch_up_writes_nothing_while_blocked(self, monkeypatch):
        calls = []
        monkeypatch.setattr(corpus_sync.db, "is_available", lambda: True)

        async def check_schema(force=False):
            db._vector_gaps(columns(768))
            return []

        async def step():
            calls.append("ran")
            return 1

        async def no_urls():
            return 0

        monkeypatch.setattr(corpus_sync.db, "check_schema", check_schema)
        monkeypatch.setattr(corpus_sync, "fill_missing_urls", no_urls)
        monkeypatch.setattr(corpus_sync, "embed_missing_skills", step)
        monkeypatch.setattr(corpus_sync, "ingest_missing_documents", step)
        monkeypatch.setattr(corpus_sync, "embed_missing_chunks", step)
        monkeypatch.setattr(corpus_sync, "get_settings",
                            lambda: Settings(embedding_provider="hf_api", hf_token="x"))
        done = await corpus_sync.catch_up()
        assert calls == []
        assert done == {"urls_filled": 0, "skills_embedded": 0,
                        "documents_ingested": 0, "chunks_embedded": 0}


class FakeConn:
    def __init__(self, written):
        self.written = written

    async def execute(self, query, *args):
        assert "embedding is null" in query
        self.written.append(args[0])


class FakeTransaction:
    def __init__(self, written):
        self.written = written

    async def __aenter__(self):
        return FakeConn(self.written)

    async def __aexit__(self, *exc):
        return False


class TestRefillingPassages:
    @pytest.fixture
    def stored(self, monkeypatch):
        rows = [{"id": i, "title": "PM Vishwakarma", "heading": "Training",
                 "content": f"Passage {i}"} for i in range(1, 36)]
        written: list[int] = []
        embedded: list[str] = []

        async def fetch(query, *args):
            assert "status <> 'rejected'" in query and "embedding is null" in query
            return [r for r in rows if r["id"] not in written][: args[0]]

        def embed_documents(texts):
            embedded.extend(texts)
            return [[0.0] * get_settings().embedding_dimension for _ in texts]

        monkeypatch.setattr(corpus_sync.db, "fetch", fetch)
        monkeypatch.setattr(corpus_sync.db, "transaction", lambda: FakeTransaction(written))
        monkeypatch.setattr(corpus_sync.embeddings, "embed_documents", embed_documents)
        return rows, written, embedded

    async def test_every_passage_in_rounds_with_a_pause_between(self, stored):
        rows, written, _ = stored
        pauses = []

        async def sleep(seconds):
            pauses.append(seconds)

        assert await corpus_sync.embed_missing_chunks(pause=2.0, sleep=sleep) == 35
        assert sorted(written) == [r["id"] for r in rows]
        # 16 + 16 + 3, a pause after each round
        assert pauses == [2.0, 2.0, 2.0]

    async def test_the_text_is_what_ingest_embeds(self, stored):
        _, _, embedded = stored

        async def sleep(_):
            pass

        await corpus_sync.embed_missing_chunks(sleep=sleep)
        assert embedded[0] == retrieval.passage_text("PM Vishwakarma", "Training", "Passage 1")
        assert embedded[0] == "PM Vishwakarma | Training | Passage 1"

    async def test_a_wrong_size_stops_rather_than_loops(self, stored, monkeypatch):
        monkeypatch.setattr(corpus_sync.embeddings, "embed_documents",
                            lambda texts: [[0.0] * 768 for _ in texts])

        async def sleep(_):
            raise AssertionError("must not go round again")

        assert await corpus_sync.embed_missing_chunks(sleep=sleep) == 0


class TestTheMigration:
    # Statements only: the comments may name the old size.
    sql = re.sub(r"--[^\n]*", "", MIGRATION.read_text(encoding="utf-8"))

    def test_both_columns_become_384_and_are_cleared(self):
        for table in ("skill_taxonomy", "document_chunks"):
            assert re.search(
                rf"alter table {table}\s+alter column embedding type vector\(384\) using null",
                self.sql,
            ), table

    def test_its_size_is_the_configured_one(self):
        sizes = set(re.findall(r"vector\((\d+)\)", self.sql))
        assert sizes == {str(Settings.model_fields["embedding_dimension"].default)}

    def test_the_functions_take_any_size(self):
        assert "query_embedding vector," in self.sql
        assert "embedding    vector\n" in self.sql

    def test_the_dropped_function_gets_its_grant_back(self):
        assert "drop function if exists scheme_skill_vectors(text);" in self.sql
        assert "grant execute on function scheme_skill_vectors(text) to anon, authenticated;" in self.sql

    def test_the_index_is_rebuilt(self):
        assert "create index skill_taxonomy_embedding_idx" in self.sql

    def test_it_is_one_transaction(self):
        assert self.sql.count("begin;") == 1 and self.sql.count("commit;") == 1

    def test_the_schema_check_names_it(self):
        assert db.VECTOR_MIGRATION == MIGRATION.name


class Files(BaseHTTPRequestHandler):
    body = b"model bytes"

    def do_GET(self):  # noqa: N802 - http.server's name
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


class TestTheDownload:
    def test_each_file_is_pinned_to_a_commit_and_a_hash(self):
        for url, name, sha in fetch_embedding_model.FILES:
            assert re.search(r"/resolve/[0-9a-f]{40}/", url), url
            assert url.endswith(name)
            assert re.fullmatch(r"[0-9a-f]{64}", sha)

    @pytest.fixture
    def server(self):
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Files)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
        httpd.shutdown()

    def test_a_file_that_does_not_match_is_deleted_and_fails_the_build(
        self, server, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("EMBEDDING_MODEL_DIR", str(tmp_path))
        from app.config import reload_settings

        reload_settings()
        monkeypatch.setattr(fetch_embedding_model, "FILES",
                            ((f"{server}/m.onnx", "m.onnx", "0" * 64),))
        monkeypatch.setattr(fetch_embedding_model.time, "sleep", lambda _s: None)
        assert fetch_embedding_model.main() == 1
        assert not (tmp_path / "m.onnx").exists()

    def test_a_matching_file_is_kept(self, server, tmp_path, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL_DIR", str(tmp_path))
        from app.config import reload_settings

        reload_settings()
        sha = hashlib.sha256(Files.body).hexdigest()
        monkeypatch.setattr(fetch_embedding_model, "FILES", ((f"{server}/m.onnx", "m.onnx", sha),))
        assert fetch_embedding_model.main() == 0
        assert (tmp_path / "m.onnx").read_bytes() == Files.body


def _model_dir() -> Path | None:
    for candidate in (Path(get_settings().embedding_model_dir), Path("models/e5-small")):
        if (candidate / "model_quantized.onnx").is_file():
            return candidate
    return None


@pytest.mark.skipif(_model_dir() is None, reason="model files not fetched (CI)")
class TestTheRealModel:
    @pytest.fixture(autouse=True)
    def onnx(self, monkeypatch):
        pytest.importorskip("onnxruntime")
        pytest.importorskip("sentencepiece")
        monkeypatch.setenv("EMBEDDING_PROVIDER", "onnx")
        monkeypatch.setenv("EMBEDDING_MODEL_DIR", str(_model_dir()))
        from app.config import reload_settings

        reload_settings()
        yield
        reload_settings()

    def test_tamil_welding_is_nearest_welding(self):
        from app.data.catalogue import TAXONOMY, embedding_text

        codes = [e["code"] for e in TAXONOMY]
        skills = embeddings.embed_documents([embedding_text(e) for e in TAXONOMY])
        query = embeddings.embed_query("நான் வெல்டிங் வேலை செய்கிறேன்")
        best = max(zip(skills, codes), key=lambda sc: embeddings.cosine_similarity(query, sc[0]))
        assert best[1] in {"SK022", "SK023", "SK024"}

    def test_a_text_gets_the_same_vector_alone_or_with_others(self):
        texts = ["short", "a much longer passage about loans " * 20, "x"]
        assert embeddings.embed_documents(texts) == [embeddings.embed_documents([t])[0] for t in texts]

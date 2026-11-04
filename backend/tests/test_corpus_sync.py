"""The startup catch-up does only what is missing, and never anything harmful.

`services/corpus_sync.py` runs against production on every start. The things
it must never do matter more than the things it does: write hash vectors into
the corpus, re-open a document an admin rejected, overwrite a URL someone set
on purpose, or take the API down when the embedder is slow or broken.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest

from app.config import reload_settings
from app.services import corpus_sync


class FakeDB:
    def __init__(self, *, sources=(), skills=()):
        self.sources = list(sources)
        self.skills = list(skills)
        self.executed: list[tuple] = []

    def is_available(self):
        return True

    async def fetch(self, query, *args):
        if "from scheme_documents" in query:
            return [{"source": s} for s in self.sources]
        if "from skill_taxonomy" in query:
            return self.skills
        raise AssertionError(query)

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "UPDATE 1"

    @asynccontextmanager
    async def transaction(self):
        yield self

    def vector_literal(self, values):
        return "[" + ",".join(str(v) for v in values) + "]"


@pytest.fixture
def fake_db(monkeypatch):
    fake = FakeDB()
    for name in ("is_available", "fetch", "execute", "transaction", "vector_literal"):
        monkeypatch.setattr(corpus_sync.db, name, getattr(fake, name))
    return fake


@pytest.fixture
def real_embeddings(monkeypatch):
    """A configured embedder, so catch_up does not stop at the offline guard."""
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hf_api")
    monkeypatch.setenv("HF_TOKEN", "test-token-not-real")
    reload_settings()
    dim = corpus_sync.get_settings().embedding_dimension
    calls: list[list[str]] = []

    def embed(texts):
        calls.append(list(texts))
        return [[0.1] * dim for _ in texts]

    monkeypatch.setattr(corpus_sync.embeddings, "embed_documents", embed)
    yield calls
    reload_settings()


@pytest.fixture
def docs(tmp_path):
    (tmp_path / "already.md").write_text("# Already in\n\n" + "x " * 200, encoding="utf-8")
    (tmp_path / "new.md").write_text(
        "# Official release title\n\nIssued by a ministry.\n\n" + "words " * 100,
        encoding="utf-8",
    )
    (tmp_path / "stub.md").write_text("# Too short\n", encoding="utf-8")
    (tmp_path / "scan.pdf").write_bytes(b"%PDF-1.4 not read here")
    (tmp_path / "sources.json").write_text(json.dumps({
        "_README": ["ignored"],
        "new.md": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1",
        "already.md": "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2",
        "missing-url.pdf": "",
    }), encoding="utf-8")
    return tmp_path


class TestDocuments:
    async def test_only_new_text_files_are_ingested(self, fake_db, docs, monkeypatch):
        fake_db.sources = ["already.md"]
        ingested = []

        async def ingest(**kwargs):
            ingested.append(kwargs)
            return 7, 3

        monkeypatch.setattr(corpus_sync.retrieval, "ingest", ingest)
        assert await corpus_sync.ingest_missing_documents(docs) == 1

        (only,) = ingested
        assert only["source"] == "new.md"
        assert only["title"] == "Official release title"
        assert only["source_url"] == "https://www.pib.gov.in/PressReleasePage.aspx?PRID=1"
        assert only["source_domain"] == "www.pib.gov.in"

    async def test_a_rejected_document_is_not_reopened(self, fake_db, docs, monkeypatch):
        # Rejected rows are still rows: their source is "known", so skipped.
        fake_db.sources = ["already.md", "new.md"]

        async def ingest(**kwargs):
            raise AssertionError("nothing should be ingested")

        monkeypatch.setattr(corpus_sync.retrieval, "ingest", ingest)
        assert await corpus_sync.ingest_missing_documents(docs) == 0

    async def test_one_bad_file_does_not_stop_the_rest(self, fake_db, docs, monkeypatch):
        (docs / "another.md").write_text("# Another\n\n" + "text " * 100, encoding="utf-8")
        seen = []

        async def ingest(**kwargs):
            seen.append(kwargs["source"])
            if kwargs["source"] == "already.md":
                raise RuntimeError("embedder timed out")
            return 1, 1

        monkeypatch.setattr(corpus_sync.retrieval, "ingest", ingest)
        assert await corpus_sync.ingest_missing_documents(docs) == 2
        assert seen == ["already.md", "another.md", "new.md"]


class TestUrls:
    async def test_urls_are_filled_only_where_blank(self, fake_db, docs):
        await corpus_sync.fill_missing_urls(docs)
        assert {args[0] for _, args in fake_db.executed} == {"new.md", "already.md"}
        for query, _ in fake_db.executed:
            assert "source_url is null or source_url = ''" in query


class TestSkills:
    async def test_only_skills_without_a_vector_are_embedded(self, fake_db, real_embeddings):
        fake_db.skills = [
            {"id": 1, "code": "SK121", "name": "Boat Making", "category": "Traditional Crafts",
             "aliases": ["boat maker"]},
        ]
        assert await corpus_sync.embed_missing_skills() == 1
        (query, args), = fake_db.executed
        assert "embedding is null" in query
        assert args[0] == 1
        # The catalogue's own text, the same one the embed script uses.
        assert "Boat Making" in real_embeddings[0][0]

    async def test_a_wrong_sized_vector_is_never_written(self, fake_db, monkeypatch, real_embeddings):
        fake_db.skills = [{"id": 1, "code": "SK121", "name": "Boat Making",
                           "category": "Traditional Crafts", "aliases": []}]
        monkeypatch.setattr(corpus_sync.embeddings, "embed_documents", lambda t: [[0.1, 0.2]])
        assert await corpus_sync.embed_missing_skills() == 0
        assert fake_db.executed == []


class TestSafety:
    async def test_offline_embeddings_write_nothing(self, fake_db, monkeypatch):
        async def boom(*args, **kwargs):
            raise AssertionError("must not touch the corpus with hash vectors")

        monkeypatch.setattr(corpus_sync, "embed_missing_skills", boom)
        monkeypatch.setattr(corpus_sync, "ingest_missing_documents", boom)
        assert await corpus_sync.catch_up() == {}

    async def test_no_database_means_nothing_to_do(self, monkeypatch):
        monkeypatch.setattr(corpus_sync.db, "is_available", lambda: False)
        assert await corpus_sync.catch_up() == {}

    async def test_a_failure_never_reaches_the_api(self, fake_db, monkeypatch, real_embeddings):
        async def boom():
            raise RuntimeError("database went away")

        monkeypatch.setattr(corpus_sync, "embed_missing_skills", boom)
        await corpus_sync.catch_up_safely()  # does not raise

    async def test_everything_shipped_is_text_the_server_can_read(self):
        # The deployed image has no PDF reader: new documents must be text.
        urls = corpus_sync.source_urls()
        new = [name for name in urls if name.startswith("PIB_")]
        assert new and all(name.endswith(".md") for name in new)

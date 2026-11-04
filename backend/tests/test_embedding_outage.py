"""When the embedder stops answering, VoicePath degrades instead of failing.

On 2026-11-04 the Hugging Face Inference API began answering 402 Payment
Required. Every request that normalized a skill -- /api/profile/extract, the
typed-skill box, /api/schemes/match for an unplaced skill -- returned 500, so
nobody could get from describing their work to seeing a result, and /health
still reported the embedder as fine.

These tests hold the fallback: names and aliases still normalize, matching
still runs, document search falls back to keywords, and /health says why.
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import reload_settings
from app.main import app, health
from app.services import embeddings, normalization, retrieval


@pytest.fixture
def embedder_down(monkeypatch):
    def refuse(texts):
        embeddings._note_failure("payment_required")
        raise embeddings.EmbeddingUnavailable("Embedding API returned 402: credits spent")

    monkeypatch.setattr(embeddings, "embed_queries", refuse)
    monkeypatch.setattr(embeddings, "embed_query", lambda text: refuse([text])[0])


class TestNormalization:
    async def test_a_skill_said_by_name_still_normalizes(self, embedder_down):
        (skill,) = await normalization.normalize_many([("welding", "I do welding")])
        assert skill.code == "SK022"
        assert skill.confidence == 1.0

    async def test_an_alias_in_tamil_still_normalizes(self, embedder_down):
        (skill,) = await normalization.normalize_many([("தையல்", "தையல் வேலை செய்கிறேன்")])
        # Unnormalized is acceptable; an exception is not.
        assert skill.raw_name == "தையல்"

    async def test_a_described_skill_is_kept_unplaced_rather_than_failing(self, embedder_down):
        (skill,) = await normalization.normalize_many(
            [("joining metal pipes with heat", "I join metal pipes with heat")]
        )
        assert skill.skill_id is None
        assert skill.evidence_phrase == "I join metal pipes with heat"
        assert skill.embedding is None


class TestTheRequestsThatUsedToFail:
    def test_extract_and_match_answer_instead_of_500(self, embedder_down):
        with TestClient(app) as client:
            session_id = client.post(
                "/api/speech/client-transcript",
                json={"transcript": "I know welding and I have worked six years.",
                      "language_detected": "en"},
            ).json()["session_id"]
            extracted = client.post("/api/profile/extract", json={"session_id": session_id})
            assert extracted.status_code == 200
            assert any(s["raw_name"].lower() == "welding" for s in extracted.json()["skills"])

            matched = client.post("/api/schemes/match", json={"session_id": session_id})
            assert matched.status_code == 200


class TestRetrieval:
    async def test_search_falls_back_to_keywords(self, embedder_down, monkeypatch):
        queries: list[str] = []

        async def fetch(query, *args):
            queries.append(query)
            return [{"chunk_id": 1, "document_title": "PMEGP", "source": "pmegp.md",
                     "source_url": None, "heading": None, "content": "Margin money subsidy",
                     "rank": 0.5}]

        monkeypatch.setattr(retrieval.db, "fetch", fetch)
        found = await retrieval.search("PMEGP margin money subsidy")
        assert [r.chunk_id for r in found] == [1]
        assert found[0].matched_keyword
        # Only the keyword query ran; there was no vector to search with.
        assert len(queries) == 1 and "websearch_to_tsquery" in queries[0]


class TestHealth:
    @pytest.fixture
    def hosted(self, monkeypatch):
        monkeypatch.setenv("EMBEDDING_PROVIDER", "hf_api")
        monkeypatch.setenv("HF_TOKEN", "test-token-not-real")
        reload_settings()
        yield
        reload_settings()

    async def test_a_refusing_embedder_is_reported_with_its_reason(self, hosted, monkeypatch):
        def reply(*args, **kwargs):
            return httpx.Response(402, text='{"error":"Purchase pre-paid credits"}')

        class Client:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            post = staticmethod(reply)

        monkeypatch.setattr(httpx, "Client", Client)
        with pytest.raises(embeddings.EmbeddingUnavailable):
            embeddings.embed_queries(["welding"])

        report = await health()
        assert "embeddings" in report.degraded
        assert report.embeddings["status"] == "payment_required"

    async def test_an_answer_clears_it(self, hosted):
        embeddings._note_failure("payment_required")
        embeddings._note_success()
        report = await health()
        assert report.embeddings == {"status": "ok"}
        assert "embeddings" not in report.degraded

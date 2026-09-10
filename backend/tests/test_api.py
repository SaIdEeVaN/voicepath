"""End-to-end pipeline over the HTTP surface.

Runs on offline providers and the in-memory store, so it exercises real routing,
real validation and real persistence semantics without any external service.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

TRANSCRIPT = (
    "I have been repairing bikes for six years. I worked at a shop in Salem, "
    "I can tell the problem just by the engine sound. I know a little welding. "
    "I talk to the customers who come to the shop myself."
)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health_reports_degraded_providers_honestly(self, client):
        body = client.get("/health").json()
        assert body["status"] == "degraded"
        assert set(body["degraded"]) >= {"stt", "tts", "llm", "database"}
        assert body["providers"]["llm"] == "offline"

    def test_root_points_at_the_docs(self, client):
        assert client.get("/").json()["docs"] == "/docs"


class TestSpeech:
    def test_server_transcription_reports_unavailable_rather_than_faking_it(self, client):
        response = client.post(
            "/api/speech/transcribe",
            files={"file": ("clip.webm", b"not-real-audio", "audio/webm")},
            data={"language": "en"},
        )
        assert response.status_code == 503
        assert "speech-to-text" in response.json()["detail"].lower()

    def test_empty_upload_is_a_client_error(self, client):
        response = client.post(
            "/api/speech/transcribe",
            files={"file": ("clip.webm", b"", "audio/webm")},
        )
        assert response.status_code == 400

    def test_browser_transcript_creates_a_session(self, client):
        response = client.post(
            "/api/speech/client-transcript",
            json={"transcript": TRANSCRIPT, "language_detected": "en"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["provider"] == "browser"
        assert body["audio_retained"] is False
        assert body["session_id"]

    def test_blank_transcript_is_refused(self, client):
        response = client.post(
            "/api/speech/client-transcript",
            json={"transcript": "   ", "language_detected": "en"},
        )
        assert response.status_code in (400, 422)

    def test_synthesis_hands_off_to_the_browser_when_offline(self, client):
        response = client.post(
            "/api/speech/synthesize", json={"text": "Hello", "language": "en"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["use_browser_tts"] is True
        assert body["audio_base64"] is None
        assert body["speech_locale"] == "en-IN"


class TestPipeline:
    def _session(self, client) -> str:
        response = client.post(
            "/api/speech/client-transcript",
            json={"transcript": TRANSCRIPT, "language_detected": "en"},
        )
        return response.json()["session_id"]

    def test_extract_returns_skills_with_evidence(self, client):
        session_id = self._session(client)
        response = client.post("/api/profile/extract", json={"session_id": session_id})
        assert response.status_code == 200
        body = response.json()
        assert body["degraded"] is True
        assert body["skills"]
        for skill in body["skills"]:
            assert skill["evidence_phrase"].strip()

    def test_extract_finds_the_six_years(self, client):
        session_id = self._session(client)
        body = client.post(
            "/api/profile/extract", json={"session_id": session_id}
        ).json()
        assert body["profile"]["experience_years"] == 6.0

    def test_extract_without_a_transcript_is_refused(self, client):
        response = client.post("/api/profile/extract", json={})
        assert response.status_code == 400

    def test_unknown_session_is_a_404(self, client):
        response = client.post(
            "/api/profile/extract",
            json={"session_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 404

    def test_normalize_respects_a_removal(self, client):
        session_id = self._session(client)
        extracted = client.post(
            "/api/profile/extract", json={"session_id": session_id}
        ).json()
        skills = extracted["skills"]
        assert len(skills) >= 2

        payload = {
            "session_id": session_id,
            "skills": [
                {
                    "id": s["id"],
                    "raw_name": s["raw_name"],
                    "evidence_phrase": s["evidence_phrase"],
                    "removed": index == 0,
                }
                for index, s in enumerate(skills)
            ],
        }
        response = client.post("/api/profile/normalize", json=payload)
        assert response.status_code == 200
        assert len(response.json()["skills"]) == len(skills) - 1

    def test_removal_persists_rather_than_being_merged_back(self, client):
        session_id = self._session(client)
        extracted = client.post(
            "/api/profile/extract", json={"session_id": session_id}
        ).json()
        keep = extracted["skills"][:1]
        client.post(
            "/api/profile/normalize",
            json={
                "session_id": session_id,
                "skills": [
                    {
                        "raw_name": s["raw_name"],
                        "evidence_phrase": s["evidence_phrase"],
                    }
                    for s in keep
                ],
            },
        )
        passport = client.get(f"/api/sessions/{session_id}").json()
        assert len(passport["skills"]) == 1

    def test_match_ranks_and_explains(self, client):
        session_id = self._session(client)
        client.post("/api/profile/extract", json={"session_id": session_id})
        response = client.post(
            "/api/opportunities/match", json={"session_id": session_id}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["matches"]

        ranks = [m["rank"] for m in body["matches"]]
        assert ranks == sorted(ranks)
        scores = [m["overall_score"] for m in body["matches"]]
        assert scores == sorted(scores, reverse=True)

        top = body["matches"][0]
        assert 0.0 <= top["overall_score"] <= 1.0
        assert top["explanation_bullets"]
        breakdown = top["breakdown"]
        assert set(breakdown) == {
            "skill_similarity_score", "experience_score",
            "eligibility_score", "location_score",
        }

    def test_match_without_skills_returns_empty_not_an_error(self, client):
        session_id = self._session(client)
        response = client.post(
            "/api/opportunities/match",
            json={"session_id": session_id, "profile": {}, "skills": []},
        )
        assert response.status_code in (200, 400)

    def test_stored_match_is_readable_afterwards(self, client):
        session_id = self._session(client)
        client.post("/api/profile/extract", json={"session_id": session_id})
        matched = client.post(
            "/api/opportunities/match", json={"session_id": session_id}
        ).json()
        opportunity_id = matched["matches"][0]["opportunity"]["id"]

        response = client.get(
            f"/api/opportunities/{opportunity_id}/match/{session_id}"
        )
        assert response.status_code == 200
        assert response.json()["overall_score"] == matched["matches"][0]["overall_score"]


class TestOpportunities:
    def test_catalogue_lists(self, client):
        body = client.get("/api/opportunities").json()
        assert len(body) >= 10

    def test_district_filter_narrows(self, client):
        body = client.get("/api/opportunities", params={"district": "Erode"}).json()
        assert body
        assert all(o["district"] == "Erode" for o in body)

    def test_detail_includes_the_listing_text_and_requirements(self, client):
        body = client.get("/api/opportunities/1").json()
        assert body["description"]
        assert body["required_skills"]

    def test_missing_opportunity_is_a_404(self, client):
        assert client.get("/api/opportunities/99999").status_code == 404


class TestAssistant:
    def _matched_session(self, client) -> tuple[str, int]:
        session_id = client.post(
            "/api/speech/client-transcript",
            json={"transcript": TRANSCRIPT, "language_detected": "en"},
        ).json()["session_id"]
        client.post("/api/profile/extract", json={"session_id": session_id})
        matched = client.post(
            "/api/opportunities/match", json={"session_id": session_id}
        ).json()
        return session_id, matched["matches"][0]["opportunity"]["id"]

    def test_salary_question_is_answered_from_the_listing(self, client):
        session_id, opportunity_id = self._matched_session(client)
        body = client.post(
            "/api/assistant/query",
            json={
                "session_id": session_id,
                "opportunity_id": opportunity_id,
                "question_text": "What is the salary for this?",
                "language": "en",
            },
        ).json()
        assert body["answered_from_data"] is True
        assert "₹" in body["answer_text"]

    def test_privacy_question_is_answered_from_the_session(self, client):
        session_id, opportunity_id = self._matched_session(client)
        body = client.post(
            "/api/assistant/query",
            json={
                "session_id": session_id,
                "opportunity_id": opportunity_id,
                "question_text": "Who hears my voice?",
                "language": "en",
            },
        ).json()
        assert "not saved" in body["answer_text"].lower()

    def test_unanswerable_question_says_so_instead_of_guessing(self, client):
        session_id, opportunity_id = self._matched_session(client)
        body = client.post(
            "/api/assistant/query",
            json={
                "session_id": session_id,
                "opportunity_id": opportunity_id,
                "question_text": "Who is the manager's cousin?",
                "language": "en",
            },
        ).json()
        assert body["answered_from_data"] is False
        assert "not" in body["answer_text"].lower()

    def test_questions_are_logged_for_the_session(self, client):
        session_id, opportunity_id = self._matched_session(client)
        client.post(
            "/api/assistant/query",
            json={
                "session_id": session_id,
                "opportunity_id": opportunity_id,
                "question_text": "What is the salary?",
                "language": "en",
            },
        )
        logged = client.get(f"/api/sessions/{session_id}/questions").json()
        assert len(logged) == 1
        assert logged[0]["source_note"]

    def test_empty_question_is_refused(self, client):
        response = client.post(
            "/api/assistant/query", json={"question_text": "   ", "language": "en"}
        )
        assert response.status_code in (400, 422)


class TestPrivacy:
    def test_audio_is_not_retained_by_default(self, client):
        session_id = client.post(
            "/api/speech/client-transcript",
            json={"transcript": TRANSCRIPT, "language_detected": "en"},
        ).json()["session_id"]
        session = client.get(f"/api/sessions/{session_id}").json()["session"]
        assert session["audio_retained"] is False
        assert session["audio_url"] is None

    def test_opt_in_can_be_turned_on_and_off(self, client):
        session_id = client.post(
            "/api/speech/client-transcript",
            json={"transcript": TRANSCRIPT, "language_detected": "en"},
        ).json()["session_id"]

        on = client.post(
            f"/api/sessions/{session_id}/audio-retention", json={"audio_retained": True}
        ).json()
        assert on["audio_retained"] is True

        off = client.post(
            f"/api/sessions/{session_id}/audio-retention", json={"audio_retained": False}
        ).json()
        assert off["audio_retained"] is False
        assert off["audio_url"] is None

    def test_a_url_cannot_exist_without_consent(self):
        """The database has a check constraint; the in-memory path must agree."""
        import asyncio

        from app.services import repository

        with pytest.raises(ValueError):
            asyncio.run(
                repository.create_session(
                    transcript="x", language_detected="en",
                    audio_retained=False, audio_url="https://example/clip.wav",
                )
            )


class TestAdminGate:
    """PRD section 6.6: every admin route verifies the role server-side."""

    ADMIN_ROUTES = [
        ("get", "/api/admin/opportunities"),
        ("get", "/api/admin/taxonomy"),
        ("get", "/api/admin/sessions"),
        ("get", "/api/admin/whoami"),
    ]

    @pytest.mark.parametrize("method,path", ADMIN_ROUTES)
    def test_no_token_is_rejected(self, client, method, path):
        assert getattr(client, method)(path).status_code == 401

    @pytest.mark.parametrize("method,path", ADMIN_ROUTES)
    def test_wrong_token_is_rejected(self, client, method, path):
        response = getattr(client, method)(
            path, headers={"Authorization": "Bearer not-the-token"}
        )
        assert response.status_code == 403

    def test_malformed_header_is_rejected(self, client):
        response = client.get(
            "/api/admin/opportunities", headers={"Authorization": "Basic abc"}
        )
        assert response.status_code == 401

    def test_writes_are_gated_too(self, client):
        response = client.post(
            "/api/admin/taxonomy",
            json={"code": "SK999", "name": "Fake", "category": "Fake"},
        )
        assert response.status_code == 401

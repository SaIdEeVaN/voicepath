"""Trade words said in Tamil and Hindi reach the right skill (2026-11-09).

Whisper misheard "வெல்டிங்" (welding) as "வெள்ளி" (silver). Two remedies that
need no new model: the recogniser is primed with the skill list's loanwords
(services/stt_vocabulary.py), and the keyword shortlist matches words by how
they sound, so a trade word in an unfamiliar spelling is still offered
(taxonomy._sound_key). No audio here: the request Groq would receive is
checked instead.
"""

from __future__ import annotations

import pytest

from app.config import reload_settings
from app.data.catalogue import TAXONOMY
from app.services import stt, stt_vocabulary, taxonomy
from app.services.taxonomy import _sound_key


class TestThePrompt:
    @pytest.mark.parametrize("language", ["ta", "hi"])
    def test_every_word_is_an_alias_in_the_skill_list(self, language):
        aliases = {a for e in TAXONOMY for a in e["aliases"]}
        for word in stt_vocabulary.VOCABULARY[language]:
            assert any(word in alias for alias in aliases), word

    @pytest.mark.parametrize("language", ["ta", "hi"])
    def test_it_fits_what_whisper_reads(self, language):
        prompt = stt_vocabulary.prompt_for(language)
        assert len(prompt.encode("utf-8")) <= stt_vocabulary.PROMPT_BUDGET_BYTES

    def test_welding_is_first_in_tamil(self):
        assert stt_vocabulary.prompt_for("ta").startswith("வெல்டிங்")

    @pytest.mark.parametrize("language", ["en", "auto", None, ""])
    def test_no_prompt_when_the_language_is_english_or_unknown(self, language):
        assert stt_vocabulary.prompt_for(language) is None

    def test_an_echo_of_the_prompt_is_nothing_heard(self):
        assert stt_vocabulary.is_echo("வெல்டிங், மெக்கானிக், ரிப்பேர்.", "ta")
        assert not stt_vocabulary.is_echo("நான் வெல்டிங் வேலை செய்தேன்", "ta")
        assert not stt_vocabulary.is_echo("வெல்டிங், மெக்கானிக்", "ta")  # two is a person
        assert not stt_vocabulary.is_echo("welding mechanic repair", "en")


class FakeResponse:
    status_code = 200

    def __init__(self, text):
        self._text = text

    def json(self):
        return {"text": self._text}


@pytest.fixture
def groq(monkeypatch):
    sent: dict = {}
    reply = {"text": "நான் ஆறு வருடம் வெல்டிங் வேலை செய்தேன்"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, files=None, data=None):
            sent.update(data or {})
            return FakeResponse(reply["text"])

    monkeypatch.setenv("STT_PROVIDER", "groq")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    reload_settings()
    monkeypatch.setattr(stt.httpx, "AsyncClient", FakeClient)
    yield sent, reply
    reload_settings()


class TestTheRequest:
    async def test_tamil_audio_is_sent_with_the_tamil_prompt(self, groq):
        sent, _ = groq
        result = await stt.transcribe(b"RIFF....", language="ta")
        assert sent["prompt"] == stt_vocabulary.prompt_for("ta")
        assert sent["language"] == "ta"
        assert "வெல்டிங்" in result.transcript

    async def test_auto_detected_audio_is_sent_without_one(self, groq):
        sent, _ = groq
        await stt.transcribe(b"RIFF....", language="auto")
        assert "prompt" not in sent

    async def test_an_echoed_prompt_is_reported_as_nothing_heard(self, groq):
        _, reply = groq
        reply["text"] = stt_vocabulary.prompt_for("ta")
        with pytest.raises(stt.STTUnavailable):
            await stt.transcribe(b"RIFF....", language="ta")


class TestSoundsAlike:
    @pytest.mark.parametrize("a, b", [
        ("வெல்டிங்", "welding"),
        ("वेल्डिंग", "welding"),
        ("எலெக்ட்ரீஷியன்", "எலக்ட்ரீசியன்"),   # two Tamil spellings
        ("electrician", "इलेक्ट्रीशियन"),
        ("பிளம்பர்", "प्लंबर"),
        ("மெக்கானிக்", "மெக்கானிக்கு"),       # a case ending
    ])
    def test_the_same_word_keys_alike_across_spellings(self, a, b):
        assert _sound_key(a) == _sound_key(b)

    def test_silver_does_not_key_as_welding(self):
        assert _sound_key("வெள்ளி") != _sound_key("வெல்டிங்")

    def test_short_keys_do_not_cross_languages(self):
        # English "sound" and Tamil "சொந்த" (own) both have consonants s-n-t.
        assert _sound_key("sound") != _sound_key("சொந்த")

    async def test_an_unfamiliar_spelling_is_still_offered(self):
        codes = [c.skill.code for c in await taxonomy.keyword_candidates("எலக்ட்ரீசியன் வேலை")]
        assert "SK031" in codes

    async def test_a_hindi_spelling_variant_is_offered_too(self):
        codes = [c.skill.code for c in await taxonomy.keyword_candidates("इलैक्ट्रीशियन का काम")]
        assert "SK031" in codes

    async def test_silver_work_is_not_offered_welding(self):
        codes = [c.skill.code for c in await taxonomy.keyword_candidates("வெள்ளி வேலை")]
        assert "SK022" not in codes

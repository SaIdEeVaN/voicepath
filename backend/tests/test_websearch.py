"""What web search may and may not do (PRD sections 7, 8, 18).

Reaching the open web is the point in this pipeline where a wrong answer stops
being embarrassing and starts being harmful: a fabricated government URL looks
official, and someone travels on it. So the tests here are about the two rules
that make it safe rather than about whether search works.

A URL is never constructed. Trust belongs to the domain, not the content.
"""

from __future__ import annotations

import pytest

from app.services import websearch


class TestTrustTier:
    @pytest.mark.parametrize(
        "url",
        [
            "https://pmvishwakarma.gov.in/en/scheme",
            "https://www.myscheme.gov.in/schemes/pmajay",
            "https://nic.in/page",
            "https://mail.gov.in/inbox",
        ],
    )
    def test_government_domains_are_tier_one(self, url):
        assert websearch.tier_for(url) == 1

    @pytest.mark.parametrize(
        "url",
        [
            "https://notgov.in/fake",
            "https://gov.in.example.com/phish",
            "https://govin.example/page",
            "https://example.com/schemes",
        ],
    )
    def test_lookalike_domains_are_not(self, url):
        """The failure that matters.

        `gov.in.example.com` ends in example.com and merely contains "gov.in".
        Substring matching would trust it, which is precisely why someone would
        register it. Matching is anchored on a dot boundary.
        """
        assert websearch.tier_for(url) != 1

    def test_a_malformed_url_is_never_trusted(self):
        for url in ["", "not a url", "ftp://gov.in/x", "javascript:alert(1)"]:
            assert websearch.tier_for(url) != 1


class TestUrlsAreNeverInvented:
    def test_only_absolute_http_urls_survive_parsing(self):
        """Section 8: URLs come from the API, and are never repaired into shape.

        A result whose URL needs fixing is a result we would be guessing at, so
        it is dropped rather than mended.
        """
        source = websearch.__loader__.get_source("app.services.websearch")
        assert 'url.startswith(("http://", "https://"))' in source

    def test_no_prompt_in_this_module_asks_a_model_for_a_url(self):
        """No model is consulted here at all, which is the strongest version
        of "never generate a URL": there is nothing to generate it with."""
        source = websearch.__loader__.get_source("app.services.websearch")
        for forbidden in ("llm.", "complete_json", "INTENT_SYSTEM"):
            assert forbidden not in source


class TestDegradation:
    def test_offline_without_a_key(self, monkeypatch):
        """Section 20: no provider is a state, not an error.

        The corpus already ingested still answers; only the widening stops.
        """
        from app.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "search_provider", "offline")
        assert websearch.is_available() is False

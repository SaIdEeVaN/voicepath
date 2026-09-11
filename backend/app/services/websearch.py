"""Finding scheme pages the local corpus does not have (PRD section 7).

The ingested guidelines answer what they cover and nothing else. Someone asking
about a scheme we never fetched a PDF for gets an honest "not in the documents",
which is correct and unhelpful when the page exists on a government portal.

This searches for it, fetches the page, and puts it through the same pipeline as
a PDF: chunk, embed, store, retrieve with a citation. Nothing about how an answer
is produced changes -- only how a document arrives.

Two rules shape everything here.

**A URL is never generated.** PRD section 8. Every address shown to a person
comes from what the search API returned, stored as-is and passed through
unchanged. A model is never asked for one and never gets the chance to assemble
something plausible. A wrong government URL looks official and sends people
somewhere real.

**Trust is a property of the domain, not the content.** A page on a .gov.in host
is Tier 1 and usable. Anything else lands as ``pending_verification``, which
retrieval will not read, until an admin has looked at it. The point is that
searching the web cannot silently widen what the system will assert.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.services import db

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"


class SearchUnavailable(RuntimeError):
    """No search provider is configured or reachable."""


@dataclass(frozen=True)
class SearchResult:
    """One page, as the search API described it. Nothing here is inferred."""

    title: str
    url: str
    domain: str
    # The API's extract. Enough to decide whether the page is worth fetching,
    # not enough to answer from.
    snippet: str
    trust_tier: int
    # The provider's own extraction of the page, when it returned one. Their
    # crawler renders JavaScript; a plain GET does not, and the main Indian
    # scheme portal is a single-page app that serves an empty shell to one.
    raw_content: str = ""

    @property
    def is_official(self) -> bool:
        return self.trust_tier == 1


def is_available() -> bool:
    return get_settings().search_provider != "offline"


def provider_name() -> str:
    return get_settings().search_provider


def _domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def tier_for(url: str) -> int:
    """Trust tier from the domain alone.

    Suffix matching, anchored on a dot, so ``mail.gov.in`` counts and
    ``notgov.in`` does not -- the latter is exactly the shape someone would
    register to be mistaken for the former.
    """
    # The scheme is part of the question. A gov.in host reached over ftp:, or
    # a javascript: URL that merely mentions one, is not a government web page
    # and must not inherit a government domain's trust.
    if not url.lower().startswith(("http://", "https://")):
        return 3

    domain = _domain_of(url)
    if not domain:
        return 3
    for trusted in get_settings().trusted_domain_list:
        if domain == trusted or domain.endswith("." + trusted):
            return 1
    return 3


async def _cached(query: str) -> list[SearchResult] | None:
    """A previous answer to this question, if it is still fresh.

    Two jobs: not re-billing the API for a repeated question, and still
    answering when the API is unreachable (PRD section 20).
    """
    if not db.is_available():
        return None
    settings = get_settings()
    row = await db.fetchrow(
        "select results, created_at from search_cache where query = $1", query
    )
    if row is None:
        return None
    age = datetime.now(timezone.utc) - row["created_at"]
    if age > timedelta(hours=settings.search_cache_hours):
        return None
    return [SearchResult(**entry) for entry in (row["results"] or [])]


async def _remember(query: str, results: list[SearchResult]) -> None:
    if not db.is_available():
        return
    await db.execute(
        """
        insert into search_cache (query, results, provider)
        values ($1, $2, $3)
        on conflict (query) do update
          set results = excluded.results,
              provider = excluded.provider,
              created_at = now()
        """,
        query,
        # The pool registers a jsonb codec, so a list of dicts goes straight in.
        [r.__dict__ for r in results],
        provider_name(),
    )


async def search(query: str, *, official_only: bool = True) -> list[SearchResult]:
    """Find pages for a query, preferring official ones.

    ``official_only`` keeps the result set to Tier 1 domains. That is the
    default because everything else needs review before it can be answered
    from, and returning results nobody can use yet reads as a broken feature.
    """
    clean = (query or "").strip()
    if not clean:
        return []

    cached = await _cached(clean)
    if cached is not None:
        return [r for r in cached if r.is_official] if official_only else cached

    settings = get_settings()
    if settings.search_provider == "offline":
        raise SearchUnavailable(
            "No search provider is configured. Set TAVILY_API_KEY, or rely on "
            "the documents already ingested."
        )

    payload = {
        "api_key": settings.tavily_api_key,
        "query": clean,
        "max_results": settings.search_result_limit,
        "search_depth": "basic",
        # Ask for the page text alongside the result. Without it every
        # myscheme.gov.in page came back as "Something went wrong" -- the shell
        # a browser would have filled in -- and was correctly discarded, which
        # made the whole feature find nothing.
        "include_raw_content": True,
        # Ask the API to stay on government domains rather than filtering
        # afterwards, so the result budget is not spent on pages we discard.
        "include_domains": settings.searchable_domain_list if official_only else [],
    }

    try:
        async with httpx.AsyncClient(timeout=settings.search_timeout_seconds) as client:
            response = await client.post(TAVILY_URL, json=payload)
    except httpx.HTTPError as exc:
        raise SearchUnavailable(f"Search request failed: {exc}") from exc

    if response.status_code >= 400:
        raise SearchUnavailable(
            f"Search returned {response.status_code}: {response.text[:200]}"
        )

    results: list[SearchResult] = []
    for entry in (response.json().get("results") or []):
        url = (entry.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            # Never repaired into one. A URL we had to fix is a URL we invented.
            continue
        results.append(
            SearchResult(
                title=(entry.get("title") or url).strip(),
                url=url,
                domain=_domain_of(url),
                snippet=(entry.get("content") or "").strip()[:600],
                trust_tier=tier_for(url),
                raw_content=(entry.get("raw_content") or "").strip(),
            )
        )

    await _remember(clean, results)
    return [r for r in results if r.is_official] if official_only else results


async def fetch_page(url: str) -> str:
    """Readable text from a page.

    Deliberately plain. A government page that needs a headless browser to read
    is a page whose content lives somewhere else, and guessing at it is worse
    than saying we do not have it.
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(
            timeout=settings.search_timeout_seconds, follow_redirects=True
        ) as client:
            response = await client.get(url, headers={"User-Agent": "VoicePath/1.0"})
    except httpx.HTTPError as exc:
        raise SearchUnavailable(f"Could not fetch {url}: {exc}") from exc

    if response.status_code >= 400:
        raise SearchUnavailable(f"{url} returned {response.status_code}")

    return _readable(response.text)


# Phrases that mean the page never rendered. A site that builds its content in
# the browser returns a shell, and the shell is long enough to look like a
# document: myscheme.gov.in comes back as "Something went wrong. Please try
# again later." at 616 characters, which would otherwise be stored as policy.
_NOT_A_PAGE = (
    "something went wrong",
    "please enable javascript",
    "you need to enable javascript",
    "loading...",
    "page not found",
    "access denied",
    "are you sure you want to sign out",
)


def looks_rendered(text: str) -> bool:
    """Is this the page, or the shell a browser would have filled in?

    Length alone cannot tell: an error shell clears 400 characters easily.
    What separates them is variety -- a real document uses hundreds of distinct
    words, a shell repeats a handful of interface strings.
    """
    stripped = text.strip()
    if len(stripped) < 400:
        return False

    lowered = stripped.lower()
    if any(phrase in lowered for phrase in _NOT_A_PAGE):
        return False

    # Roughly a paragraph's worth of distinct vocabulary. Measured: the
    # myscheme shell has under 60 unique words, the PM Vishwakarma page has
    # several hundred.
    return len({word for word in lowered.split() if len(word) > 3}) >= 80


def _readable(html: str) -> str:
    """Strip markup to text, keeping paragraph boundaries.

    The chunker splits on blank lines, so collapsing block elements into them
    is what lets it find section boundaries rather than cutting mid-clause.
    """
    import re

    # Script and style hold no prose and plenty of braces that survive tag
    # stripping and read as garbage.
    html = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)

    # html.unescape handles the numeric forms too. Hand-listing named entities
    # left &#x201C; and &#x27; sitting in the text of a real government page,
    # which then got embedded and quoted back to people as written.
    import html as _html

    text = _html.unescape(text)

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


async def search_and_ingest(query: str, *, limit: int = 3) -> list[dict]:
    """Search, fetch what was found, and put it through the RAG pipeline.

    Returns one record per page with what happened to it, so a caller can say
    which sources are answerable now and which are waiting on review.

    A page that cannot be fetched or yields too little text is reported and
    skipped. The alternative -- storing a navigation menu as though it were
    policy -- is how a confident answer gets built on nothing.
    """
    from app.services import retrieval

    results = await search(query, official_only=True)
    outcomes: list[dict] = []

    for result in results[:limit]:
        record = {
            "title": result.title,
            "url": result.url,
            "domain": result.domain,
            "trust_tier": result.trust_tier,
        }
        # Prefer what the provider extracted: their crawler renders the page,
        # ours does not. Fetching ourselves is the fallback for a result that
        # arrived without it.
        text = result.raw_content
        if not looks_rendered(text):
            try:
                text = await fetch_page(result.url)
            except SearchUnavailable as exc:
                outcomes.append(
                    {**record, "status": "unreachable", "detail": str(exc)[:160]}
                )
                continue

        # A page that did not render is worse than a page that failed to load:
        # it looks like a document and says nothing. Storing one would put an
        # error message into the corpus that answers people.
        if not looks_rendered(text):
            outcomes.append({**record, "status": "not_rendered", "chunks": 0})
            continue

        # Tier 1 is answerable immediately; the domain is the trust signal.
        # Anything else waits for an admin (PRD section 18).
        status = "active" if result.is_official else "pending_verification"
        try:
            _, chunks = await retrieval.ingest(
                title=result.title,
                source=result.url,
                text=text,
                source_url=result.url,
                source_domain=result.domain,
                trust_tier=result.trust_tier,
                status=status,
            )
        except Exception as exc:  # noqa: BLE001 - one bad page must not stop the rest
            logger.warning("Could not ingest %s: %s", result.url, exc)
            outcomes.append({**record, "status": "failed", "detail": str(exc)[:160]})
            continue

        outcomes.append({**record, "status": status, "chunks": chunks})

    return outcomes

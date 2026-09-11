"""Load scheme documents into the retrieval corpus.

    cd backend
    python -m app.scripts.ingest_documents data/scheme_docs
    python -m app.scripts.ingest_documents data/scheme_docs/guidelines.pdf

Accepts .txt and .md directly. PDFs need ``pypdf`` (``pip install pypdf``).

Re-running replaces a document's chunks rather than adding to them, so fixing
the extraction and running again is safe.

A note on PDFs, because it is where retrieval quality is usually lost: read the
extracted text before trusting it. A two-column government PDF interleaves the
columns into nonsense, and a scanned one yields nothing at all without OCR. Pass
--show to print what was actually extracted. Bad text in is bad retrieval out,
and no amount of tuning downstream recovers it.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

from app.config import get_settings
from app.services import db, retrieval

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("ingest_documents")

TEXT_SUFFIXES = {".txt", ".md"}
PDF_SUFFIXES = {".pdf"}

# Running headers and footers -- "P a g e 1 | 16", "3 | P a g e". Extractors
# emit these on every page, so left alone they appear in most chunks and dilute
# the embedding of each one with text that carries no meaning.
_PAGE_FURNITURE = re.compile(
    r"(?im)^\s*(?:p\s*a\s*g\s*e\s*\d+\s*\|\s*\d+|\d+\s*\|\s*p\s*a\s*g\s*e)\s*$"
)


def _strip_page_furniture(text: str) -> str:
    """Drop running headers and footers, and collapse the gaps they leave."""
    text = _PAGE_FURNITURE.sub("", text)
    # Inline occurrences, where extraction ran the footer into the body text.
    text = re.sub(
        r"(?i)\s*(?:p\s*a\s*g\s*e\s*\d+\s*\|\s*\d+|\d+\s*\|\s*p\s*a\s*g\s*e)\s*",
        " ", text,
    )
    return re.sub(r"\n{3,}", "\n\n", text)


def read_text(path: Path) -> str:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")

    if path.suffix.lower() in PDF_SUFFIXES:
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover - depends on install
            raise RuntimeError(
                "Reading PDFs needs pypdf. Run `pip install pypdf`, or convert "
                "the file to .txt first."
            ) from exc
        reader = PdfReader(str(path))
        # Page breaks become paragraph breaks so the chunker sees a boundary
        # rather than one continuous wall of text.
        return _strip_page_furniture(
            "\n\n".join((page.extract_text() or "") for page in reader.pages)
        )

    raise RuntimeError(f"{path.name}: unsupported type {path.suffix}")


async def main(target: Path, language: str, show: bool) -> int:
    settings = get_settings()
    if not settings.database_url:
        logger.error("DATABASE_URL is not set. Nothing to write to.")
        return 1
    if settings.embedding_provider == "offline":
        logger.error(
            "EMBEDDING_PROVIDER is offline. Hash vectors are not comparable "
            "with the ones retrieval will query against -- set hf_api or local."
        )
        return 1

    if target.is_dir():
        paths = sorted(
            p for p in target.iterdir()
            if p.suffix.lower() in TEXT_SUFFIXES | PDF_SUFFIXES
        )
    else:
        paths = [target]

    if not paths:
        logger.error("No .txt, .md or .pdf files found in %s", target)
        return 1

    await db.init_pool()
    try:
        total = 0
        for path in paths:
            try:
                text = read_text(path)
            except RuntimeError as exc:
                logger.error("%s", exc)
                continue

            if len(text.strip()) < 200:
                logger.warning(
                    "%s: only %d characters extracted -- scanned PDF, or needs "
                    "OCR. Skipping.", path.name, len(text.strip()),
                )
                continue

            if show:
                logger.info("---- %s, first 600 characters ----", path.name)
                print(text.strip()[:600])
                print("----")

            _, chunks = await retrieval.ingest(
                title=path.stem.replace("_", " ").replace("-", " ").strip(),
                source=path.name,
                text=text,
                language=language,
            )
            logger.info("%-40s %d chunks", path.name, chunks)
            total += chunks

        logger.info("Corpus now holds %d chunks from this run.", total)
        ready = await retrieval.is_ready()
        logger.info("Retrieval ready: %s", ready)
        return 0
    finally:
        await db.close_pool()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="A file, or a directory of them")
    parser.add_argument("--language", default="en", help="ta | hi | en")
    parser.add_argument(
        "--show", action="store_true",
        help="Print the start of the extracted text. Use it the first time.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.path, args.language, args.show)))

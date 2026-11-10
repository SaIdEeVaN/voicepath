"""Download multilingual-e5-small (int8 ONNX) into ``models/e5-small``.

    cd backend
    python -m app.scripts.fetch_embedding_model

Two files, about 123 MB. Run by the deploy build: Render's build command runs
``app.scripts.fetch_voices``, which ends by calling this, so the build command
itself did not have to change.

Each file is pinned twice over: to one commit of its repository, and to the
SHA-256 Hugging Face publishes for it. A file that does not match is deleted
and the build fails -- the running version stays live -- rather than serving
vectors from a model nobody chose. Already-present files that match are left
alone, so this is safe to re-run.

Licences: multilingual-e5-small is MIT (intfloat). The ONNX export is
Xenova's conversion of it; the tokenizer file is intfloat's own.
"""

from __future__ import annotations

import hashlib
import logging
import sys
import time
from pathlib import Path

from app.config import get_settings
from app.scripts.fetch_voices import ATTEMPTS, _download

logger = logging.getLogger("fetch_embedding_model")

# (url, file name, sha256)
FILES: tuple[tuple[str, str, str], ...] = (
    (
        "https://huggingface.co/Xenova/multilingual-e5-small/resolve/"
        "761b726dd34fb83930e26aab4e9ac3899aa1fa78/onnx/model_quantized.onnx",
        "model_quantized.onnx",
        "f80102d3f2a1229f387d3c81909990d8945513e347b0eab049f7de3c6f98c193",
    ),
    (
        "https://huggingface.co/intfloat/multilingual-e5-small/resolve/"
        "614241f622f53c4eeff9890bdc4f31cfecc418b3/sentencepiece.bpe.model",
        "sentencepiece.bpe.model",
        "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    dest = Path(get_settings().embedding_model_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for url, name, expected in FILES:
        target = dest / name
        if target.is_file() and _sha256(target) == expected:
            logger.info("%s already present", name)
            continue
        for attempt in range(1, ATTEMPTS + 1):
            try:
                _download(url, target)
                found = _sha256(target)
                if found != expected:
                    target.unlink(missing_ok=True)
                    raise ValueError(f"SHA-256 {found}, expected {expected}")
                break
            except Exception as exc:  # noqa: BLE001 - retry, then fail the build
                logger.warning("%s attempt %d/%d failed (%s)", name, attempt, ATTEMPTS, exc)
                if attempt == ATTEMPTS:
                    logger.error("%s could not be downloaded", name)
                    return 1
                time.sleep(5 * attempt)
        logger.info("%s  %.1f MB", name, target.stat().st_size / 1e6)
    logger.info("Embedding model is in %s", dest.resolve())
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    sys.exit(main())

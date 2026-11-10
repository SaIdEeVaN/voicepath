"""Download the Piper voices into ``models/piper``.

    cd backend
    python -m app.scripts.fetch_voices

About 190MB for the three. Already-present files are left alone, so this is
safe to re-run.

Licensing is not uniform and the difference matters if you ship this:

* Hindi and English come from the Piper project itself and are **MIT**.
* Tamil is a community voice trained on AI4Bharat Rasa and is **CC-BY-4.0**,
  which obliges you to attribute it. There is no Tamil voice in the official
  Piper repository at all, so this is the only open option for the language
  this app is primarily built for.
"""

from __future__ import annotations

import logging
import sys
import time
import urllib.request
from pathlib import Path

from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("fetch_voices")

RHASSPY = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
TINISOFT = "https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium/resolve/main/"

VOICES: dict[str, tuple[str, str, str]] = {
    # language: (base url, file stem, licence)
    "ta": (TINISOFT, "ta_IN-rasa_female-medium", "CC-BY-4.0 (attribution required)"),
    "hi": (RHASSPY + "hi/hi_IN/priyamvada/medium/", "hi_IN-priyamvada-medium", "MIT"),
    "en": (RHASSPY + "en/en_GB/alba/medium/", "en_GB-alba-medium", "MIT"),
}


# A download used to have only a 600-second *socket* timeout: it fired after
# ten minutes of total silence, never on a slow trickle. On 2026-11-05 a Render
# build hung on the Hindi voice for over fifteen minutes and every deploy
# queued behind it. Now each file has a ceiling for the whole download, any
# 60 seconds of silence ends an attempt, and three attempts are made. A file
# is written under a temporary name and renamed when complete, so a cut-off
# download is never mistaken for a present one.
PER_FILE_SECONDS = 300
SILENCE_SECONDS = 60
ATTEMPTS = 3
CHUNK_BYTES = 1 << 20


def _download(url: str, target: Path) -> None:
    partial = target.with_name(target.name + ".part")
    deadline = time.monotonic() + PER_FILE_SECONDS
    request = urllib.request.Request(url, headers={"User-Agent": "voicepath"})
    try:
        with urllib.request.urlopen(request, timeout=SILENCE_SECONDS) as response, \
                partial.open("wb") as out:
            while chunk := response.read(CHUNK_BYTES):
                out.write(chunk)
                if time.monotonic() > deadline:
                    raise TimeoutError(f"not finished after {PER_FILE_SECONDS}s")
        if partial.stat().st_size == 0:
            raise ValueError("empty download")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def main() -> int:
    dest = Path(get_settings().piper_voice_dir)
    dest.mkdir(parents=True, exist_ok=True)

    for language, (base, stem, licence) in VOICES.items():
        for suffix in (".onnx", ".onnx.json"):
            target = dest / (stem + suffix)
            if target.is_file() and target.stat().st_size > 0:
                logger.info("%s: %s already present", language, target.name)
                continue
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    _download(base + stem + suffix, target)
                    break
                except Exception as exc:  # noqa: BLE001 - retry, then fail the build
                    logger.warning(
                        "%s: %s attempt %d/%d failed (%s)",
                        language, target.name, attempt, ATTEMPTS, exc,
                    )
                    if attempt == ATTEMPTS:
                        # Failing the build keeps the running version live.
                        logger.error("%s: %s could not be downloaded", language, target.name)
                        return 1
                    time.sleep(5 * attempt)
            logger.info(
                "%s: %s  %.1f MB  [%s]",
                language, target.name, target.stat().st_size / 1e6, licence,
            )

    logger.info("Voices are in %s", dest.resolve())

    # The deploy's build command runs this script and nothing else, so the
    # embedding model (2026-11-10) is fetched from here too, and then every
    # model's weights are moved to a file the server maps instead of loading:
    # a voice is ~105 MB of heap and the embedder ~180, and together they did
    # not fit in 512 MB (see scripts/map_weights.py).
    from pathlib import Path as _Path

    from app.scripts import fetch_embedding_model, map_weights

    code = fetch_embedding_model.main()
    if code:
        return code
    models = sorted(dest.glob("*.onnx")) + [
        _Path(get_settings().embedding_model_dir) / fetch_embedding_model.FILES[0][1]
    ]
    return map_weights.main([str(m) for m in models])


if __name__ == "__main__":
    sys.exit(main())

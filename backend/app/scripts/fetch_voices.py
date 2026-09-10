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


def main() -> int:
    dest = Path(get_settings().piper_voice_dir)
    dest.mkdir(parents=True, exist_ok=True)

    for language, (base, stem, licence) in VOICES.items():
        for suffix in (".onnx", ".onnx.json"):
            target = dest / (stem + suffix)
            if target.is_file() and target.stat().st_size > 0:
                logger.info("%s: %s already present", language, target.name)
                continue
            request = urllib.request.Request(
                base + stem + suffix, headers={"User-Agent": "voicepath"}
            )
            try:
                with urllib.request.urlopen(request, timeout=600) as response:
                    target.write_bytes(response.read())
            except Exception as exc:  # noqa: BLE001 - report and keep going
                logger.error("%s: %s failed (%s)", language, target.name, exc)
                return 1
            logger.info(
                "%s: %s  %.1f MB  [%s]",
                language, target.name, target.stat().st_size / 1e6, licence,
            )

    logger.info("Voices are in %s", dest.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())

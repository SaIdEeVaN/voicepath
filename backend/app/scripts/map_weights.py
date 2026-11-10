"""Let an ONNX model's weights stay on disk instead of in memory.

    python -m app.scripts.map_weights models/piper/*.onnx models/e5-small/model_quantized.onnx

Run by the deploy build, after the models are downloaded. It moves each
model's large weights out of the ``.onnx`` file into a sidecar ``<name>.onnx.data``
next to it. onnxruntime finds the sidecar by itself and *maps* the file into
memory, instead of reading the weights onto the heap: pages of the file are
brought in as the model touches them and are given back by the kernel when
memory is short, where heap memory is not.

Why (2026-11-10): the container has 512 MB, and the models together did not
fit as heap -- each Piper voice holds ~105 MB resident and the embedding model
~180 MB, so Tamil + Hindi + English voices and the embedder came to 690 MB and
Render killed the process (``oomKilled``), over and over, at startup. Mapped,
the unreclaimable part is a fraction of that (see STATUS.md for the figures).

Nothing about the model changes: the same bytes, the same arithmetic. The
build checks it -- ``tests/test_map_weights.py`` compares the outputs before
and after, and the vectors the embedder makes are bit-for-bit identical.

Needs the ``onnx`` package, which only this script imports -- the running API
never does, so it adds nothing to the server's memory.

Safe to re-run: a model already converted is left alone. Files are written
beside the model under temporary names and renamed into place, the sidecar
first, so a build cut off halfway leaves the model as it was.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger("map_weights")

# Tensors smaller than this stay inside the .onnx file. Mapping a tensor of a
# few hundred bytes costs more than it saves.
THRESHOLD_BYTES = 4096


def sidecar(model: Path) -> Path:
    return model.with_name(model.name + ".data")


def looks_mapped(model: Path) -> bool:
    """Cheap guess without onnx: a sidecar bigger than the model beside it."""
    data = sidecar(model)
    return (
        model.is_file()
        and data.is_file()
        and data.stat().st_size > model.stat().st_size
    )


def is_mapped(model: Path) -> bool:
    """True when the model already keeps its large weights in a sidecar."""
    import onnx
    from onnx import TensorProto

    proto = onnx.load(str(model), load_external_data=False)
    return any(
        t.data_location == TensorProto.EXTERNAL for t in proto.graph.initializer
    )


def map_weights(model: Path, *, threshold: int = THRESHOLD_BYTES) -> bool:
    """Convert ``model`` in place. Returns False if it already was converted."""
    import onnx
    from onnx.external_data_helper import convert_model_to_external_data

    if is_mapped(model):
        if not sidecar(model).is_file() or sidecar(model).stat().st_size == 0:
            # The model points at weights that are not there: it cannot load.
            raise RuntimeError(
                f"{model.name} is converted but {sidecar(model).name} is missing; "
                "delete the model and fetch it again"
            )
        return False

    proto = onnx.load(str(model))  # weights read in, once, at build time
    staging = model.with_name(model.name + ".mapping")
    staging.mkdir(exist_ok=True)
    try:
        staged = staging / model.name
        convert_model_to_external_data(
            proto,
            all_tensors_to_one_file=True,
            location=sidecar(model).name,
            size_threshold=threshold,
            convert_attribute=False,
        )
        onnx.save_model(proto, str(staged))
        # The sidecar first: until the model is replaced, the old one (weights
        # inline) simply ignores it.
        os.replace(staging / sidecar(model).name, sidecar(model))
        os.replace(staged, model)
        # onnx writes the sidecar owner-only; the server may run as another user.
        os.chmod(sidecar(model), 0o644)
        os.chmod(model, 0o644)
    finally:
        for leftover in staging.glob("*"):
            leftover.unlink(missing_ok=True)
        staging.rmdir()
    return True


def main(paths: list[str]) -> int:
    if not paths:
        logger.error("No models given.")
        return 2
    failed = 0
    for name in paths:
        model = Path(name)
        if not model.is_file():
            logger.error("%s is not a file", model)
            failed += 1
            continue
        before = model.stat().st_size
        try:
            changed = map_weights(model)
        except Exception as exc:  # noqa: BLE001 - say which model, fail the build
            logger.error("%s: %s", model, exc)
            failed += 1
            continue
        if changed:
            logger.info(
                "%s: %.1f MB -> %.1f MB + %.1f MB mapped",
                model.name, before / 1e6, model.stat().st_size / 1e6,
                sidecar(model).stat().st_size / 1e6,
            )
        else:
            logger.info("%s already mapped", model.name)
    return 1 if failed else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
    sys.exit(main(sys.argv[1:]))

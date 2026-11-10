"""Model weights stay on disk, mapped, instead of on the heap (2026-11-10).

The embedding model switched on in production did not fit beside the three
speech voices in 512 MB, and Render killed the process three times in three
minutes. Each model's weights now live in a sidecar file the server maps
(scripts/map_weights.py). These hold that the conversion changes nothing about
what a model computes, that it is safe to re-run and to interrupt, and that
the build does not fetch a model again just because it was converted.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

onnx = pytest.importorskip("onnx")
ort = pytest.importorskip("onnxruntime")
np = pytest.importorskip("numpy")

from onnx import TensorProto, helper, numpy_helper  # noqa: E402

from app.scripts import fetch_embedding_model, map_weights  # noqa: E402


def build_model(path: Path) -> np.ndarray:
    """y = x @ W + b with a 4 MB W and a one-number b; returns W."""
    rng = np.random.default_rng(7)
    weights = rng.standard_normal((1024, 1024)).astype(np.float32)
    bias = rng.standard_normal((1,)).astype(np.float32)
    graph = helper.make_graph(
        [
            helper.make_node("MatMul", ["x", "W"], ["xw"]),
            helper.make_node("Add", ["xw", "b"], ["y"]),
        ],
        "tiny",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 1024])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 1024])],
        initializer=[numpy_helper.from_array(weights, "W"), numpy_helper.from_array(bias, "b")],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 9
    onnx.save_model(model, str(path))
    return weights


def run(path: Path) -> np.ndarray:
    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    x = np.linspace(-1, 1, 1024, dtype=np.float32).reshape(1, 1024)
    return session.run(None, {"x": x})[0]


@pytest.fixture
def model(tmp_path):
    path = tmp_path / "tiny.onnx"
    build_model(path)
    return path


class TestTheConversion:
    def test_large_weights_move_to_a_sidecar_and_the_model_shrinks(self, model):
        before = model.stat().st_size
        assert map_weights.map_weights(model) is True
        sidecar = map_weights.sidecar(model)
        assert sidecar.name == "tiny.onnx.data"
        assert sidecar.stat().st_size >= 4 * 1024 * 1024
        assert model.stat().st_size < before / 10

    def test_what_the_model_computes_is_exactly_the_same(self, model, tmp_path):
        original = tmp_path / "copy" / "tiny.onnx"
        original.parent.mkdir()
        shutil.copy(model, original)
        expected = run(original)
        map_weights.map_weights(model)
        assert np.array_equal(run(model), expected)

    def test_small_tensors_stay_inside_the_model(self, model):
        map_weights.map_weights(model)
        proto = onnx.load(str(model), load_external_data=False)
        by_name = {t.name: t for t in proto.graph.initializer}
        assert by_name["W"].data_location == TensorProto.EXTERNAL
        assert by_name["b"].data_location != TensorProto.EXTERNAL  # 4 bytes: kept inline

    def test_it_is_safe_to_run_again(self, model):
        assert map_weights.map_weights(model) is True
        sidecar_bytes = map_weights.sidecar(model).read_bytes()
        assert map_weights.map_weights(model) is False
        assert map_weights.sidecar(model).read_bytes() == sidecar_bytes

    def test_nothing_is_left_behind_and_both_files_are_readable_by_the_server(self, model):
        map_weights.map_weights(model)
        assert sorted(p.name for p in model.parent.iterdir()) == ["tiny.onnx", "tiny.onnx.data"]
        for path in (model, map_weights.sidecar(model)):
            assert path.stat().st_mode & 0o044 == 0o044

    def test_a_converted_model_whose_sidecar_is_gone_is_an_error_not_a_silent_skip(self, model):
        map_weights.map_weights(model)
        map_weights.sidecar(model).unlink()
        with pytest.raises(RuntimeError, match="missing"):
            map_weights.map_weights(model)


class TestRecognisingAMappedModel:
    def test_a_plain_model_is_not_mapped(self, model):
        assert not map_weights.looks_mapped(model)
        assert not map_weights.is_mapped(model)

    def test_a_converted_one_is(self, model):
        map_weights.map_weights(model)
        assert map_weights.looks_mapped(model)
        assert map_weights.is_mapped(model)


class TestTheBuildStep:
    def test_main_converts_every_model_given(self, tmp_path):
        paths = []
        for name in ("a.onnx", "b.onnx"):
            build_model(tmp_path / name)
            paths.append(str(tmp_path / name))
        assert map_weights.main(paths) == 0
        assert all(map_weights.looks_mapped(Path(p)) for p in paths)

    def test_a_missing_model_fails_the_build(self, tmp_path):
        assert map_weights.main([str(tmp_path / "nope.onnx")]) == 1

    def test_no_models_is_a_mistake(self):
        assert map_weights.main([]) == 2

    def test_the_embedding_download_does_not_refetch_a_converted_model(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EMBEDDING_MODEL_DIR", str(tmp_path))
        from app.config import reload_settings

        reload_settings()
        name = fetch_embedding_model.FILES[0][1]
        (tmp_path / name).write_bytes(b"x" * 100)                       # converted: small
        (tmp_path / (name + ".data")).write_bytes(b"y" * 1000)          # sidecar: bigger
        # the other file is present and matches nothing -- only the first is under test
        monkeypatch.setattr(fetch_embedding_model, "FILES", fetch_embedding_model.FILES[:1])

        def refuse(*_args, **_kwargs):
            raise AssertionError("downloaded a model that was already fetched and converted")

        monkeypatch.setattr(fetch_embedding_model, "_download", refuse)
        assert fetch_embedding_model.main() == 0
        reload_settings()

    def test_the_voices_script_ends_by_mapping_every_model(self):
        import inspect

        from app.scripts import fetch_voices

        source = inspect.getsource(fetch_voices.main)
        assert "map_weights.main" in source and 'dest.glob("*.onnx")' in source

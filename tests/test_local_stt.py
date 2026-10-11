"""Local speech-to-text: hardware plans and the GPU-to-CPU fallback."""
import types

import pytest

from services import local_stt
from services.local_stt import Hardware, Plan


def hw(vram=0, cuda=False, cpu=8):
    return Hardware(gpu_name="GPU" if vram else None, vram_mb=vram, cuda_available=cuda, cpu_threads=cpu)


@pytest.mark.parametrize("vram,cuda,expected", [
    (8192, True, ("large-v3", "cuda", "float16")),      # RTX 4060
    (6144, True, ("large-v3", "cuda", "int8_float16")),
    (4096, True, ("medium", "cuda", "int8_float16")),
    (2048, True, ("small", "cuda", "int8_float16")),
    (1024, True, ("small", "cpu", "int8")),              # too weak: CPU
    (8192, False, ("small", "cpu", "int8")),             # GPU present but CUDA unusable
    (0, False, ("small", "cpu", "int8")),
])
def test_recommendation_scales_with_hardware(vram, cuda, expected):
    plan = local_stt.recommend(hw(vram, cuda))
    assert (plan.model, plan.device, plan.compute_type) == expected


def test_weak_cpu_gets_base_model():
    assert local_stt.recommend(hw(0, False, cpu=2)).model == "base"


def test_resolve_plan_honours_user_choices():
    gpu = hw(8192, True)
    assert local_stt.resolve_plan("auto", "auto", gpu).device == "cuda"
    assert local_stt.resolve_plan("large", "cpu", gpu) == Plan("large-v3", "cpu", "int8")  # legacy 'large'
    assert local_stt.resolve_plan("tiny", "auto", hw(0, False)).device == "cpu"
    assert local_stt.resolve_plan("bogus", "cpu", gpu).model == "small"




class FakeModel:
    def __init__(self, fail=False):
        self.fail = fail

    def transcribe(self, path, **kwargs):
        assert kwargs["language"] == "hu" and kwargs["condition_on_previous_text"] is False
        if self.fail:
            raise RuntimeError("Library cublas64_12.dll is not found")
        segs = [types.SimpleNamespace(start=0.0, end=1.0, text=" Szia "),
                types.SimpleNamespace(start=1.0, end=2.0, text="  ")]
        return iter(segs), types.SimpleNamespace(duration=2.0)


def test_gpu_failure_falls_back_to_cpu(monkeypatch):
    calls = []

    def fake_load(plan, status=None):
        calls.append(plan.device)
        return FakeModel(fail=plan.device == "cuda")

    monkeypatch.setattr(local_stt, "load_model", fake_load)
    messages = []
    segments, used = local_stt.transcribe_file(
        "x.wav", Plan("small", "cuda", "float16"), language="hu-HU", status=messages.append)
    assert calls == ["cuda", "cpu"] and used.device == "cpu"
    assert [s.text for s in segments] == ["Szia"]
    assert any("CPU" in m for m in messages)


def test_cpu_failure_is_reported_not_hidden(monkeypatch):
    monkeypatch.setattr(local_stt, "load_model", lambda plan, status=None: FakeModel(fail=True))
    with pytest.raises(RuntimeError):
        local_stt.transcribe_file("x.wav", Plan("small", "cpu", "int8"), language="hu")


def test_cancel_stops_transcription(monkeypatch):
    monkeypatch.setattr(local_stt, "load_model", lambda plan, status=None: FakeModel())
    with pytest.raises(local_stt.TranscriptionCancelled):
        local_stt.transcribe_file("x.wav", Plan("small", "cpu", "int8"), language="hu",
                                  should_stop=lambda: True)


def test_language_codes_are_normalised():
    assert local_stt.normalize_language("hu-HU") == "hu"
    assert local_stt.normalize_language("auto") is None and local_stt.normalize_language("") is None


def test_pyav_19_metadata_errors_error_uses_own_decoder(monkeypatch):
    """faster-whisper 1.2.x passes av.open(metadata_errors=...), which PyAV 19 removed."""
    seen = []

    class OldDecoderModel:
        def transcribe(self, audio, **kwargs):
            seen.append(audio)
            if isinstance(audio, str):
                raise TypeError("open() got an unexpected keyword argument 'metadata_errors'")
            segs = [types.SimpleNamespace(start=0.0, end=1.0, text="Szia")]
            return iter(segs), types.SimpleNamespace(duration=1.0)

    monkeypatch.setattr(local_stt, "load_model", lambda plan, status=None: OldDecoderModel())
    monkeypatch.setattr(local_stt, "_decode_audio_compat", lambda path: [0.0])
    segments, _used = local_stt.transcribe_file("x.wav", Plan("small", "cpu", "int8"), language="hu")
    assert [s.text for s in segments] == ["Szia"]
    assert seen[0] == "x.wav" and seen[1] == [0.0]


def test_unrelated_type_error_is_not_swallowed(monkeypatch):
    class BrokenModel:
        def transcribe(self, audio, **kwargs):
            raise TypeError("something else")

    monkeypatch.setattr(local_stt, "load_model", lambda plan, status=None: BrokenModel())
    with pytest.raises(TypeError):
        local_stt.transcribe_file("x.wav", Plan("small", "cpu", "int8"), language="hu")


@pytest.fixture(autouse=True)
def _fresh_gpu_state():
    local_stt._cuda_broken = False
    yield
    local_stt._cuda_broken = False


def test_failed_gpu_is_not_retried_on_the_next_recording(monkeypatch):
    calls = []

    def fake_load(plan, status=None):
        calls.append(plan.device)
        return FakeModel(fail=plan.device == "cuda")

    monkeypatch.setattr(local_stt, "load_model", fake_load)
    gpu = Plan("small", "cuda", "float16")
    local_stt.transcribe_file("x.wav", gpu, language="hu")
    local_stt.transcribe_file("x.wav", gpu, language="hu")
    assert calls == ["cuda", "cpu", "cpu"]

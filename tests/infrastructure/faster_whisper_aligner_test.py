import sys
from types import SimpleNamespace

from src.infrastructure.subtitles.faster_whisper_aligner import FasterWhisperWordAligner


def test_faster_whisper_aligner_extracts_word_timestamps(monkeypatch):
    aligner = FasterWhisperWordAligner(model_size="small", compute_type="int8", language="en")

    class FakeModel:
        @staticmethod
        def transcribe(*_args, **_kwargs):
            return (
                [
                    SimpleNamespace(
                        words=[
                            SimpleNamespace(word=" Hello", start=0.1, end=0.3, probability=0.9),
                            SimpleNamespace(word="world ", start=0.32, end=0.6, probability=0.8),
                        ]
                    )
                ],
                SimpleNamespace(language="en"),
            )

    monkeypatch.setattr(aligner, "_load_model", lambda: FakeModel())

    payload = aligner.align("input.mp4")

    assert payload["metadata"]["aligner"] == "faster_whisper"
    assert payload["metadata"]["model"] == "small"
    assert payload["words"][0]["text"] == "Hello"
    assert payload["words"][0]["normalized_text"] == "hello"
    assert payload["words"][1]["start_ms"] == 320
    assert payload["words"][1]["end_ms"] == 600


def test_faster_whisper_aligner_skips_invalid_words_and_fixes_zero_length_segments(
    monkeypatch,
):
    aligner = FasterWhisperWordAligner(language=None)

    class FakeModel:
        @staticmethod
        def transcribe(*_args, **_kwargs):
            return (
                [
                    SimpleNamespace(
                        words=[
                            SimpleNamespace(word=" valid ", start=0.4, end=0.4, probability=None),
                            SimpleNamespace(word="", start=0.5, end=0.6, probability=0.5),
                            SimpleNamespace(
                                word="missing-start",
                                start=None,
                                end=0.8,
                                probability=0.6,
                            ),
                        ]
                    )
                ],
                SimpleNamespace(language="es"),
            )

    monkeypatch.setattr(aligner, "_load_model", lambda: FakeModel())

    payload = aligner.align("input.mp4")

    assert payload["metadata"]["language"] == "es"
    assert payload["words"] == [
        {
            "text": "valid",
            "normalized_text": "valid",
            "start_ms": 400,
            "end_ms": 401,
            "confidence": 0.0,
        }
    ]


def test_faster_whisper_aligner_loads_model_once(monkeypatch):
    created_models: list[object] = []

    class FakeWhisperModel:
        def __init__(self, model_size, compute_type):
            self.model_size = model_size
            self.compute_type = compute_type
            created_models.append(self)

    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        SimpleNamespace(WhisperModel=FakeWhisperModel),
    )

    aligner = FasterWhisperWordAligner(model_size="small", compute_type="float16")

    first_model = aligner._load_model()
    second_model = aligner._load_model()

    assert first_model is second_model
    assert len(created_models) == 1
    assert first_model.model_size == "small"
    assert first_model.compute_type == "float16"


def test_faster_whisper_aligner_uses_expected_defaults_and_transcribe_arguments(
    monkeypatch,
):
    aligner = FasterWhisperWordAligner()
    captured = {}

    class FakeModel:
        @staticmethod
        def transcribe(media_filepath, **kwargs):
            captured["media_filepath"] = media_filepath
            captured["kwargs"] = kwargs
            return ([], SimpleNamespace(language="pt"))

    monkeypatch.setattr(aligner, "_load_model", lambda: FakeModel())

    payload = aligner.align("clip.wav")

    assert aligner.model_size == "base"
    assert aligner.compute_type == "int8"
    assert aligner.language is None
    assert aligner.beam_size == 5
    assert aligner.vad_filter is True
    assert captured == {
        "media_filepath": "clip.wav",
        "kwargs": {
            "beam_size": 5,
            "language": None,
            "vad_filter": True,
            "word_timestamps": True,
        },
    }
    assert payload["metadata"]["aligner"] == "faster_whisper"
    assert payload["metadata"]["model"] == "base"
    assert payload["metadata"]["compute_type"] == "int8"
    assert payload["metadata"]["language"] == "pt"
    assert payload["words"] == []

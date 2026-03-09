from src.domain.subtitle_models import SubtitleCue
from src.domain.value_objects import TimeInterval
from src.infrastructure.subtitle_processor import SubtitleProcessor
from src.infrastructure.subtitles.faster_whisper_aligner import FasterWhisperWordAligner
from tests.infrastructure.alignment_support_test import build_fake_alignment_payload


def _make_cue(
    text: str = "Hello world",
    start_ms: int = 0,
    end_ms: int = 1000,
    cue_id: str = "cue-1",
) -> SubtitleCue:
    return SubtitleCue(
        cue_id=cue_id,
        speaker="Speaker 1",
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
    )


def test_subtitle_processor_builds_word_aligner_from_config(monkeypatch):
    settings = {
        "backend": "faster_whisper",
        "model_size": "small",
        "compute_type": "float16",
        "language": "en",
        "beam_size": 3,
        "vad_filter": False,
    }
    calls = []

    monkeypatch.setattr(
        "src.infrastructure.subtitle_processor.ConfigManager.get_alignment_setting",
        lambda _self, key, default=None: calls.append((key, default)) or settings.get(key, default),
    )

    aligner = SubtitleProcessor._build_word_aligner()

    assert isinstance(aligner, FasterWhisperWordAligner)
    assert aligner.model_size == "small"
    assert aligner.compute_type == "float16"
    assert aligner.language == "en"
    assert aligner.beam_size == 3
    assert aligner.vad_filter is False
    assert calls == [
        ("backend", "faster_whisper"),
        ("model_size", "base"),
        ("compute_type", "int8"),
        ("language", None),
        ("beam_size", 5),
        ("vad_filter", True),
    ]


def test_subtitle_processor_alignment_helpers_and_deserializers_handle_invalid_inputs(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    interval = TimeInterval(0.0, 1.0)

    monkeypatch.setattr(
        "src.infrastructure.subtitle_processor.ConfigManager.get_alignment_setting",
        lambda _self, key, default=None: {
            "enabled": True,
            "backend": "unsupported",
        }.get(key, default),
    )

    assert processor._build_word_aligner() is None
    assert (
        processor._resolve_timed_cues(
            [],
            interval,
            "input.srt",
            str(tmp_path / "output.ass"),
            "input.mp4",
        )
        == []
    )
    assert processor._deserialize_aligned_words("invalid") == []
    assert processor._deserialize_reconciled_cues("invalid") == []


def test_subtitle_processor_falls_back_when_alignment_is_unavailable_or_invalid(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    interval = TimeInterval(0.0, 1.0)
    cue = _make_cue()

    monkeypatch.setattr(
        "src.infrastructure.subtitle_processor.ConfigManager.get_alignment_setting",
        lambda _self, key, default=None: {"enabled": True}.get(key, default),
    )

    monkeypatch.setattr(processor, "_build_word_aligner", lambda: None)
    approximate_when_aligner_missing = processor._resolve_timed_cues(
        [cue],
        interval,
        "input.srt",
        str(tmp_path / "missing-aligner.ass"),
        "input.mp4",
    )
    assert approximate_when_aligner_missing[0].timing_mode == "approximate"

    class NoWordsAligner:
        aligner_name = "fake"
        model_size = "tiny"
        compute_type = "int8"
        language = "en"

        @staticmethod
        def align(_media_filepath):
            return {"metadata": {}, "words": []}

    monkeypatch.setattr(processor, "_build_word_aligner", lambda: NoWordsAligner())
    approximate_when_no_words = processor._resolve_timed_cues(
        [cue],
        interval,
        "input.srt",
        str(tmp_path / "no-words.ass"),
        "input.mp4",
    )
    assert approximate_when_no_words[0].timing_mode == "approximate"

    class FailingAligner(NoWordsAligner):
        model_size = "broken"

        @staticmethod
        def align(_media_filepath):
            raise RuntimeError("alignment failed")

    monkeypatch.setattr(processor, "_build_word_aligner", lambda: FailingAligner())
    approximate_when_exception = processor._resolve_timed_cues(
        [cue],
        interval,
        "input.srt",
        str(tmp_path / "failing-aligner.ass"),
        "input.mp4",
    )
    assert approximate_when_exception[0].timing_mode == "approximate"

    assert processor._build_approximate_cues([_make_cue(text="", end_ms=500)], interval) == []


def test_subtitle_processor_uses_default_components_and_alignment_toggle(monkeypatch):
    processor = SubtitleProcessor()

    assert processor.approximate_aligner is not None
    assert processor.approximate_aligner.__class__.__name__ == "ApproximateWordAligner"
    assert processor._should_use_alignment(None) is False

    calls = []
    monkeypatch.setattr(
        "src.infrastructure.subtitle_processor.ConfigManager.get_alignment_setting",
        lambda _self, key, default=None: calls.append((key, default)) or "yes",
    )

    assert processor._should_use_alignment("clip.mp4") is True
    assert calls == [("enabled", True)]


def test_subtitle_processor_builds_reconciled_payload_with_expected_keys(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    cue = _make_cue()
    interval = TimeInterval(0.0, 1.0)

    monkeypatch.setattr(
        "src.infrastructure.subtitle_processor.ConfigManager.get_alignment_setting",
        lambda _self, key, default=None: {"enabled": True}.get(key, default),
    )

    class FakeAligner:
        aligner_name = "fake"
        model_size = "tiny"
        compute_type = "int8"
        language = "en"

        @staticmethod
        def align(media_filepath):
            assert media_filepath == "input.mp4"
            return build_fake_alignment_payload()

    class FakeCache:
        def __init__(self):
            self.saved_raw = []
            self.saved_reconciled = []

        def build_raw_key(self, **kwargs):
            self.raw_kwargs = kwargs
            return "raw-key"

        @staticmethod
        def load_raw(raw_key):
            assert raw_key == "raw-key"
            return None

        def save_raw(self, raw_key, payload):
            self.saved_raw.append((raw_key, payload))

        def build_reconciled_key(self, **kwargs):
            self.reconciled_kwargs = kwargs
            return "reconciled-key"

        @staticmethod
        def load_reconciled(reconciled_key):
            assert reconciled_key == "reconciled-key"
            return None

        def save_reconciled(self, reconciled_key, payload):
            self.saved_reconciled.append((reconciled_key, payload))

    fake_cache = FakeCache()
    monkeypatch.setattr(processor, "_build_word_aligner", lambda: FakeAligner())
    monkeypatch.setattr(
        "src.infrastructure.subtitle_processor.AlignmentCache.from_output_filepath",
        lambda output_ass_filepath: fake_cache,
    )

    timed_cues = processor._resolve_timed_cues(
        [cue],
        interval,
        "input.srt",
        str(tmp_path / "output.ass"),
        "input.mp4",
    )

    assert fake_cache.raw_kwargs == {
        "media_filepath": "input.mp4",
        "aligner_name": "fake",
        "model_name": "tiny",
        "compute_type": "int8",
        "language": "en",
    }
    assert fake_cache.saved_raw == [
        (
            "raw-key",
            build_fake_alignment_payload(),
        )
    ]
    assert fake_cache.reconciled_kwargs == {
        "subtitle_filepath": "input.srt",
        "raw_key": "raw-key",
        "reconciliation_version": "v1",
    }
    reconciled_payload = fake_cache.saved_reconciled[0][1]
    assert fake_cache.saved_reconciled[0][0] == "reconciled-key"
    assert reconciled_payload["raw_key"] == "raw-key"
    assert list(reconciled_payload["quality"]) == [
        "global_score",
        "matched_word_ratio",
        "exact_match_ratio",
        "fallback_cue_ratio",
    ]
    assert reconciled_payload["cues"] == [timed_cues[0].to_dict()]
    assert timed_cues[0].timing_mode == "reconciled_asr"


def test_subtitle_processor_builds_exact_approximate_cue_payload():
    processor = SubtitleProcessor()
    cues = [
        _make_cue(text="alpha beta", start_ms=0, end_ms=200, cue_id="cue-1"),
        _make_cue(text="", start_ms=0, end_ms=200, cue_id="cue-2"),
    ]

    timed_cues = processor._build_approximate_cues(cues, TimeInterval(0.0, 1.0))

    assert len(timed_cues) == 1
    timed_cue = timed_cues[0]
    assert timed_cue.cue_id == "cue-1"
    assert timed_cue.quality_score == 0.0
    assert timed_cue.timing_mode == "approximate"
    assert [word.display_text for word in timed_cue.words] == ["alpha", "beta"]
    assert [word.start_ms for word in timed_cue.words] == [0, 100]
    assert [word.end_ms for word in timed_cue.words] == [100, 200]
    assert all(word.confidence == 0.0 for word in timed_cue.words)
    assert all(word.source == "approximate" for word in timed_cue.words)
    assert all(word.match_method == "approximate" for word in timed_cue.words)
    assert all(word.fallback_used is True for word in timed_cue.words)


def test_subtitle_processor_continues_after_empty_approximate_cue():
    processor = SubtitleProcessor()
    cues = [
        _make_cue(text="", start_ms=0, end_ms=100, cue_id="cue-empty"),
        _make_cue(text="kept cue", start_ms=100, end_ms=300, cue_id="cue-kept"),
    ]

    timed_cues = processor._build_approximate_cues(cues, TimeInterval(0.0, 1.0))

    assert [cue.cue_id for cue in timed_cues] == ["cue-kept"]

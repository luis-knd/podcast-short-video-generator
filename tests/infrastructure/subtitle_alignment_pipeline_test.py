from src.domain.value_objects import TimeInterval
from src.infrastructure.subtitle_processor import SubtitleProcessor
from tests.infrastructure.alignment_support_test import build_fake_alignment_payload


def test_process_subtitles_uses_two_level_cache_for_alignment(tmp_path, monkeypatch):
    media_file = tmp_path / "video.mp4"
    media_file.write_bytes(b"video-bytes")
    srt_file = tmp_path / "video.srt"
    srt_file.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nSpeaker 1: Hello world\n",
        encoding="utf-8",
    )
    ass_file = tmp_path / "short.ass"

    processor = SubtitleProcessor()

    class FakeAligner:
        aligner_name = "fake"
        model_size = "tiny"
        compute_type = "int8"
        language = "en"

        def __init__(self):
            self.calls = 0

        def align(self, _media_filepath):
            self.calls += 1
            return build_fake_alignment_payload()

    fake_aligner = FakeAligner()
    monkeypatch.setattr(processor, "_build_word_aligner", lambda: fake_aligner)

    reconcile_calls = {"count": 0}
    original_reconcile = processor.reconciler.reconcile

    def capture_reconcile(cues, aligned_words):
        reconcile_calls["count"] += 1
        return original_reconcile(cues, aligned_words)

    monkeypatch.setattr(processor.reconciler, "reconcile", capture_reconcile)

    first_result = processor.process_subtitles(
        str(srt_file),
        TimeInterval(0.0, 1.0),
        str(ass_file),
        media_filepath=str(media_file),
    )
    second_result = processor.process_subtitles(
        str(srt_file),
        TimeInterval(0.0, 1.0),
        str(ass_file),
        media_filepath=str(media_file),
    )

    assert fake_aligner.calls == 1
    assert reconcile_calls["count"] == 1
    assert first_result == second_result

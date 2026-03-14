"""Tests for IntervalSubtitleProjector targeting surviving mutants."""

import pytest

from src.domain.subtitle_models import ReconciledCue, ReconciledWord
from src.domain.value_objects import TimeInterval
from src.infrastructure.subtitles.projector import IntervalSubtitleProjector


def _word(text: str, start_ms: int, end_ms: int) -> ReconciledWord:
    return ReconciledWord(
        display_text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        confidence=0.9,
        source="reconciled",
        match_method="exact_normalized",
        fallback_used=False,
    )


def _cue(cue_id: str, start_ms: int, end_ms: int, words: list[ReconciledWord]) -> ReconciledCue:
    return ReconciledCue(
        cue_id=cue_id,
        speaker="Speaker 1",
        original_text=" ".join(w.display_text for w in words),
        source_cue_start_ms=start_ms,
        source_cue_end_ms=end_ms,
        timing_mode="reconciled_asr",
        quality_score=0.9,
        words=tuple(words),
    )


def test_projector_default_words_per_phrase_is_six():
    """Kills mutmut_1: words_per_phrase default=6 → 7."""
    projector = IntervalSubtitleProjector()
    words = [_word(f"w{i}", i * 200, i * 200 + 200) for i in range(7)]
    cue = _cue("c1", 0, 1400, words)
    interval = TimeInterval.from_string("00:00 - 00:02")

    segments = projector.project([cue], interval)

    # With default words_per_phrase=6, 7 words → 2 phrases (6 + 1)
    assert len(segments) == 2
    assert segments[0]["phrase_text"] == "w0 w1 w2 w3 w4 w5"
    assert segments[1]["phrase_text"] == "w6"


@pytest.mark.parametrize(
    ("cue_end_ms", "cue_start_ms", "interval_start", "interval_end", "should_include"),
    [
        # cue ends at exactly interval_start → excluded (cue.end_ms <= interval_start_ms)
        (5000, 3000, 5000, 10000, False),
        # cue ends one ms after interval_start → included
        (5001, 3000, 5000, 10000, True),
        # cue starts at exactly interval_end → excluded (cue.start_ms >= interval_end_ms)
        (8000, 10000, 5000, 10000, False),
        # cue starts one ms before interval_end → included
        (11000, 9999, 5000, 10000, True),
    ],
)
def test_projector_interval_boundary_filtering(cue_end_ms, cue_start_ms, interval_start, interval_end, should_include):
    """Kills mutmut_13 (or→and), mutmut_14 (<=→<), mutmut_15 (>=→>)."""
    projector = IntervalSubtitleProjector()
    w = _word("hello", cue_start_ms, cue_end_ms)
    cue = _cue("c1", cue_start_ms, cue_end_ms, [w])
    interval = TimeInterval(interval_start / 1000, interval_end / 1000)

    segments = projector.project([cue], interval)

    if should_include:
        assert len(segments) >= 1
    else:
        assert len(segments) == 0


def test_projector_continue_skips_out_of_range_words_without_stopping_other_cues():
    """Kills mutmut_44: continue → break in the word loop."""
    projector = IntervalSubtitleProjector()
    interval = TimeInterval(2.0, 5.0)  # 2000-5000ms

    words_cue1 = [
        _word("early", 0, 500),  # before interval — should be skipped
        _word("valid", 2500, 3000),  # inside interval
    ]
    words_cue2 = [
        _word("also-valid", 3500, 4000),  # inside interval, different cue
    ]
    cues = [
        _cue("cue1", 0, 3000, words_cue1),
        _cue("cue2", 3500, 4000, words_cue2),
    ]

    segments = projector.project(cues, interval)

    texts = [seg["phrase_text"] for seg in segments]
    assert "valid" in texts
    assert "also-valid" in texts


def test_projector_projects_words_relative_to_interval_start():
    projector = IntervalSubtitleProjector()
    interval = TimeInterval(2.0, 4.0)  # 2000-4000ms

    words = [_word("hello", 2200, 2700), _word("world", 2800, 3200)]
    cue = _cue("c", 2200, 3200, words)

    segments = projector.project([cue], interval)

    assert len(segments) == 1
    word_times = segments[0]["words"]
    # projected start = 2200 - 2000 = 200ms
    assert word_times[0]["start"] == 200
    assert word_times[0]["end"] == 700


def test_projector_custom_words_per_phrase_splits_correctly():
    projector = IntervalSubtitleProjector()
    words = [_word(f"w{i}", i * 300, i * 300 + 300) for i in range(4)]
    cue = _cue("c", 0, 1200, words)
    interval = TimeInterval(0.0, 2.0)

    segments = projector.project([cue], interval, words_per_phrase=2)

    assert len(segments) == 2
    assert segments[0]["phrase_text"] == "w0 w1"
    assert segments[1]["phrase_text"] == "w2 w3"

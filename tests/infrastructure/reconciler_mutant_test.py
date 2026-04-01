import inspect

import pytest

from src.domain.subtitle_models import AlignedWord, SubtitleCue
from src.infrastructure.subtitles.reconciler import TranscriptReconciler
from tests.infrastructure.reconciler_support_test import run_reconcile_with_watchdog


def _cue(
    text: str,
    *,
    cue_id: str = "cue-1",
    start_ms: int = 0,
    end_ms: int = 1000,
    speaker: str = "Speaker 1",
) -> SubtitleCue:
    return SubtitleCue(cue_id=cue_id, speaker=speaker, text=text, start_ms=start_ms, end_ms=end_ms)


def _word(text: str, start_ms: int, end_ms: int, confidence: float = 0.9) -> AlignedWord:
    return AlignedWord(text=text, normalized_text=text.lower(), start_ms=start_ms, end_ms=end_ms, confidence=confidence)


def test_reconciler_init_default_parameter_values_are_exact():
    sig = inspect.signature(TranscriptReconciler.__init__)
    params = sig.parameters

    assert params["match_window_ms"].default == 1000
    assert params["minimum_match_ratio"].default == 0.6
    assert params["fuzzy_threshold"].default == 0.86


def test_reconciler_fallback_cue_ratio_is_zero_when_no_cues_are_fallback():
    reconciler = TranscriptReconciler()
    cue = _cue("hello world", end_ms=800)
    aligned = [_word("hello", 100, 250), _word("world", 300, 500)]

    _, quality = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    assert quality["fallback_cue_ratio"] == 0.0


def test_reconciler_fallback_cue_ratio_is_zero_on_empty_cue_list():
    reconciler = TranscriptReconciler()

    _, quality = run_reconcile_with_watchdog(reconciler, [], [])

    assert quality["fallback_cue_ratio"] == 0.0


def test_reconciler_empty_cue_returns_zero_matched_and_exact_stats():
    reconciler = TranscriptReconciler()
    empty = _cue("", cue_id="empty")

    reconciled_cues, quality = run_reconcile_with_watchdog(reconciler, [empty], [])

    assert quality["matched_word_ratio"] == 0.0
    assert quality["exact_match_ratio"] == 0.0
    assert quality["global_score"] == 0.0


def test_reconciler_match_ratio_uses_division_not_multiplication():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.5)
    cue = _cue("alpha beta gamma delta", end_ms=2000)
    aligned = [_word("alpha", 100, 300)]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    assert reconciled_cues[0].timing_mode == "approximate"


def test_reconciler_match_ratio_empty_expected_returns_zero_not_one():
    reconciler = TranscriptReconciler()
    cue = SubtitleCue(cue_id="c", speaker="S", text="!!! ???", start_ms=0, end_ms=500)

    reconciled_cues, quality = run_reconcile_with_watchdog(reconciler, [cue], [])

    assert reconciled_cues[0].timing_mode == "approximate"


def test_reconciler_find_candidate_match_respects_cursor_start():
    reconciler = TranscriptReconciler()
    candidates = [
        _word("alpha", 100, 200),
        _word("alpha", 300, 400),
        _word("beta", 500, 600),
    ]

    index, method = reconciler._find_candidate_match("alpha", candidates, cursor=1)

    assert index == 1
    assert method == "exact_normalized"


def test_reconciler_interpolation_word_start_uses_multiplication_not_division():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.3)
    cue = _cue("a b c d e", start_ms=0, end_ms=500)
    aligned = [_word("a", 0, 100), _word("e", 400, 500)]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    words = reconciled_cues[0].words
    assert words[1].display_text == "b"
    assert words[1].start_ms == 100
    assert words[1].end_ms == 200


def test_reconciler_interpolation_word_end_formula_is_correct():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.3)
    cue = _cue("a b c", start_ms=0, end_ms=300)
    aligned = [_word("a", 0, 100), _word("c", 200, 300)]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    words = reconciled_cues[0].words
    assert words[1].display_text == "b"
    assert words[1].start_ms == 100
    assert words[1].end_ms == 200


def test_reconciler_interpolation_word_end_is_always_greater_than_start():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.3)
    cue = _cue("a b c", start_ms=0, end_ms=1000)
    aligned = [
        _word("a", 500, 500),
        _word("c", 500, 500),
    ]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    interpolated = [w for w in reconciled_cues[0].words if w.source == "interpolated"]
    assert len(interpolated) >= 1
    for word in interpolated:
        assert word.end_ms > word.start_ms


def test_reconciler_interpolated_words_have_confidence_zero_and_fallback_false():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.3)
    cue = _cue("a b c", start_ms=0, end_ms=600)
    aligned = [_word("a", 0, 200), _word("c", 400, 600)]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    b = next(w for w in reconciled_cues[0].words if w.display_text == "b")
    assert b.confidence == 0.0
    assert b.fallback_used is False
    assert b.source == "interpolated"


def test_reconciler_build_words_run_end_tracking_is_correct():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.3)
    cue = _cue("a b c d e f", start_ms=0, end_ms=600)
    aligned = [_word("a", 0, 100), _word("f", 500, 600)]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    words = reconciled_cues[0].words
    assert len(words) == 6
    assert words[0].display_text == "a"
    assert words[5].display_text == "f"
    assert all(w.source == "interpolated" for w in words[1:5])
    assert [w.display_text for w in words] == ["a", "b", "c", "d", "e", "f"]


@pytest.mark.parametrize(
    ("run_length", "expected_texts"),
    [
        (1, ["a", "b", "c"]),
        (2, ["a", "b", "c", "d"]),
        (3, ["a", "b", "c", "d", "e"]),
    ],
)
def test_reconciler_run_end_extends_to_cover_all_consecutive_nones(run_length, expected_texts):
    reconciler = TranscriptReconciler(minimum_match_ratio=0.3)
    words_text = " ".join(expected_texts)
    cue = _cue(words_text, start_ms=0, end_ms=len(expected_texts) * 100)
    first_word = expected_texts[0].lower()
    last_word = expected_texts[-1].lower()
    aligned = [
        _word(first_word, 0, 100),
        _word(last_word, (len(expected_texts) - 1) * 100, len(expected_texts) * 100),
    ]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned)

    assert len(reconciled_cues[0].words) == len(expected_texts)

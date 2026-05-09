from src.domain.subtitle_models import AlignedWord, SubtitleCue
from src.infrastructure.subtitles.reconciler import TranscriptReconciler
from tests.infrastructure.reconciler_support_test import run_reconcile_with_watchdog


def _cue(
    text: str, *, cue_id: str = "cue-1", speaker: str = "Speaker 1", start_ms: int = 0, end_ms: int = 1000
) -> SubtitleCue:
    return SubtitleCue(
        cue_id=cue_id,
        speaker=speaker,
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
    )


def _word(
    text: str,
    start_ms: int,
    end_ms: int,
    *,
    normalized_text: str | None = None,
    confidence: float = 0.9,
) -> AlignedWord:
    return AlignedWord(
        text=text,
        normalized_text=normalized_text or text.lower(),
        start_ms=start_ms,
        end_ms=end_ms,
        confidence=confidence,
    )


def test_reconciler_uses_exact_default_window_boundaries():
    reconciler = TranscriptReconciler()
    cue = _cue("alpha beta", start_ms=1000, end_ms=2000)
    aligned_words = [
        _word("too-early", 0, 499, normalized_text="tooearly"),
        _word("left-edge", 100, 500, normalized_text="leftedge"),
        _word("alpha", 600, 900),
        _word("beta", 1900, 2200),
        _word("right-edge", 2500, 2600, normalized_text="rightedge"),
        _word("too-late", 2501, 2600, normalized_text="toolate"),
    ]

    candidates = reconciler._candidate_words_for_cue(cue, aligned_words)

    assert [word.text for word in candidates] == [
        "too-early",
        "left-edge",
        "alpha",
        "beta",
        "right-edge",
        "too-late",
    ]


def test_reconciler_default_thresholds_allow_partial_fuzzy_match_without_fallback():
    reconciler = TranscriptReconciler()
    cue = _cue("alpha beta gamma", end_ms=900)
    aligned_words = [
        _word("alpha", 100, 200),
        _word("betaa", 250, 400),
        _word("noise", 500, 650),
    ]

    reconciled_cues, quality = run_reconcile_with_watchdog(reconciler, [cue], aligned_words)

    assert reconciled_cues[0].timing_mode == "reconciled_asr"
    assert [word.match_method for word in reconciled_cues[0].words] == [
        "exact_normalized",
        "fuzzy_normalized",
        "interpolated",
    ]
    assert quality["matched_word_ratio"] == 2 / 3
    assert quality["fallback_cue_ratio"] == 0.0


def test_reconciler_counts_each_approximate_cue_and_preserves_generated_words():
    reconciler = TranscriptReconciler()
    cues = [
        _cue("one two", cue_id="cue-1", speaker="Speaker 1", start_ms=0, end_ms=400),
        _cue("three four", cue_id="cue-2", speaker="Speaker 2", start_ms=500, end_ms=900),
    ]

    reconciled_cues, quality = run_reconcile_with_watchdog(reconciler, cues, aligned_words=[])

    assert [cue.timing_mode for cue in reconciled_cues] == ["approximate", "approximate"]
    assert [cue.cue_id for cue in reconciled_cues] == ["cue-1", "cue-2"]
    assert [cue.speaker for cue in reconciled_cues] == ["Speaker 1", "Speaker 2"]
    assert [len(cue.words) for cue in reconciled_cues] == [2, 2]
    assert all(word.fallback_used for cue in reconciled_cues for word in cue.words)
    assert all(word.source == "approximate" for cue in reconciled_cues for word in cue.words)
    assert quality == {
        "global_score": 0.0,
        "matched_word_ratio": 0.0,
        "exact_match_ratio": 0.0,
        "fallback_cue_ratio": 1.0,
    }


def test_reconciler_empty_cue_fallback_keeps_identity_and_zero_quality():
    reconciler = TranscriptReconciler()
    cue = _cue("", cue_id="empty", speaker="Narrator", start_ms=120, end_ms=180)

    reconciled_cues, quality = run_reconcile_with_watchdog(reconciler, [cue], aligned_words=[])

    reconciled_cue = reconciled_cues[0]
    assert reconciled_cue.cue_id == "empty"
    assert reconciled_cue.speaker == "Narrator"
    assert reconciled_cue.original_text == ""
    assert reconciled_cue.start_ms == 120
    assert reconciled_cue.end_ms == 180
    assert reconciled_cue.timing_mode == "approximate"
    assert reconciled_cue.quality_score == 0.0
    assert reconciled_cue.words == ()
    assert quality == {
        "global_score": 0.0,
        "matched_word_ratio": 0.0,
        "exact_match_ratio": 0.0,
        "fallback_cue_ratio": 1.0,
    }


def test_reconciler_uses_next_matching_occurrence_for_repeated_tokens():
    reconciler = TranscriptReconciler()
    cue = _cue("alpha alpha", end_ms=800)
    aligned_words = [
        _word("alpha", 100, 180),
        _word("alpha", 300, 360),
        _word("alpha", 700, 760),
    ]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned_words)

    assert [(word.start_ms, word.end_ms) for word in reconciled_cues[0].words] == [
        (100, 180),
        (300, 360),
    ]


def test_reconciler_interpolates_consecutive_gap_with_integer_segments():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.4)
    cue = _cue("start mid-a mid-b mid-c end", end_ms=600)
    aligned_words = [
        _word("start", 100, 200),
        _word("end", 205, 260),
    ]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned_words)
    words = reconciled_cues[0].words

    assert [(word.display_text, word.start_ms, word.end_ms, word.fallback_used) for word in words] == [
        ("start", 100, 200, False),
        ("mid-a", 200, 201, False),
        ("mid-b", 201, 202, False),
        ("mid-c", 202, 205, False),
        ("end", 205, 260, False),
    ]
    assert [word.source for word in words] == [
        "reconciled",
        "interpolated",
        "interpolated",
        "interpolated",
        "reconciled",
    ]


def test_reconciler_matches_leading_word_when_srt_cue_starts_late():
    reconciler = TranscriptReconciler()
    cue = _cue("we scream now", start_ms=1000, end_ms=1600)
    aligned_words = [
        _word("we", 200, 400),
        _word("scream", 600, 800),
        _word("now", 900, 1100),
    ]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned_words)
    words = reconciled_cues[0].words

    assert reconciled_cues[0].timing_mode == "reconciled_asr"
    assert [word.display_text for word in words] == ["we", "scream", "now"]
    assert [word.source for word in words] == ["reconciled", "reconciled", "reconciled"]
    assert [(word.start_ms, word.end_ms) for word in words] == [
        (200, 400),
        (600, 800),
        (900, 1100),
    ]


def test_reconciler_places_unmatched_leading_word_before_next_resolved_word():
    reconciler = TranscriptReconciler()
    cue = _cue("alpha beta gamma", start_ms=1000, end_ms=1600)
    aligned_words = [
        _word("beta", 600, 800),
        _word("gamma", 900, 1100),
    ]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, [cue], aligned_words)
    words = reconciled_cues[0].words

    assert reconciled_cues[0].timing_mode == "reconciled_asr"
    assert [word.display_text for word in words] == ["alpha", "beta", "gamma"]
    assert words[0].source == "interpolated"
    assert words[0].end_ms <= words[1].start_ms
    assert [word.start_ms for word in words] == sorted(word.start_ms for word in words)


def test_reconciler_keeps_whisper_timing_for_syllabified_subtitle_words():
    reconciler = TranscriptReconciler()
    cue = _cue(
        "NU-ance. NU-ance. Two syllables, stress on",
        cue_id="cue-syllables",
        start_ms=193460,
        end_ms=196064,
    )
    aligned_words = [
        _word("New", 194060, 194240),
        _word("ounce.", 194240, 194680, normalized_text="ounce"),
        _word("New", 195260, 195420),
        _word("ounce.", 195420, 195780, normalized_text="ounce"),
        _word("Two", 196300, 196480),
        _word("syllables", 196480, 196820),
        _word("stress", 196820, 197400),
        _word("on", 197400, 197600),
    ]

    reconciled_cues, quality = run_reconcile_with_watchdog(reconciler, [cue], aligned_words)

    assert reconciled_cues[0].timing_mode == "reconciled_asr"
    assert [(word.display_text, word.start_ms, word.end_ms) for word in reconciled_cues[0].words] == [
        ("NU-ance.", 194060, 194680),
        ("NU-ance.", 195260, 195780),
        ("Two", 196300, 196480),
        ("syllables,", 196480, 196820),
        ("stress", 196820, 197400),
        ("on", 197400, 197600),
    ]
    assert quality["matched_word_ratio"] == 1.0
    assert quality["fallback_cue_ratio"] == 0.0


def test_reconciler_does_not_reuse_aligned_word_occurrence_across_adjacent_cues():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.5)
    cues = [
        _cue(
            "need to understand the nuances of",
            cue_id="cue-110",
            start_ms=199982,
            end_ms=202590,
        ),
        _cue(
            'the language."',
            cue_id="cue-111",
            start_ms=202590,
            end_ms=203460,
        ),
    ]
    aligned_words = [
        _word("need", 201000, 201200, normalized_text="need"),
        _word("to", 201200, 201380, normalized_text="to"),
        _word("understand", 201380, 201880, normalized_text="understand"),
        _word("the", 201880, 202080, normalized_text="the"),
        _word("nuances", 202080, 202440, normalized_text="nuances"),
        _word("of", 202440, 202880, normalized_text="of"),
        _word("the", 202880, 202980, normalized_text="the"),
        _word("language.", 202980, 203320, normalized_text="language"),
    ]

    reconciled_cues, _ = run_reconcile_with_watchdog(reconciler, cues, aligned_words)

    assert [(word.display_text, word.start_ms) for word in reconciled_cues[0].words] == [
        ("need", 201000),
        ("to", 201200),
        ("understand", 201380),
        ("the", 201880),
        ("nuances", 202080),
        ("of", 202440),
    ]
    assert [(word.display_text, word.start_ms) for word in reconciled_cues[1].words] == [
        ("the", 202880),
        ('language."', 202980),
    ]

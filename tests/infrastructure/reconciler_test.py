from src.domain.subtitle_models import AlignedWord, SubtitleCue
from src.infrastructure.subtitles.reconciler import TranscriptReconciler


def test_reconciler_preserves_display_text_and_uses_aligned_times():
    reconciler = TranscriptReconciler()
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="Hello, world",
        start_ms=0,
        end_ms=1000,
    )
    aligned_words = [
        AlignedWord("Hello", "hello", 100, 300, 0.9),
        AlignedWord("world", "world", 320, 600, 0.95),
    ]

    reconciled_cues, quality = reconciler.reconcile([cue], aligned_words)

    assert len(reconciled_cues) == 1
    assert reconciled_cues[0].timing_mode == "reconciled_asr"
    assert reconciled_cues[0].words[0].display_text == "Hello,"
    assert reconciled_cues[0].words[0].start_ms == 100
    assert reconciled_cues[0].words[1].display_text == "world"
    assert quality["matched_word_ratio"] == 1.0


def test_reconciler_falls_back_to_approximate_when_match_ratio_is_low():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.75)
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="Hello world again",
        start_ms=0,
        end_ms=900,
    )
    aligned_words = [AlignedWord("noise", "noise", 100, 200, 0.1)]

    reconciled_cues, quality = reconciler.reconcile([cue], aligned_words)

    assert reconciled_cues[0].timing_mode == "approximate"
    assert all(word.fallback_used for word in reconciled_cues[0].words)
    assert quality["fallback_cue_ratio"] == 1.0


def test_reconciler_interpolates_unmatched_words_and_uses_fuzzy_matches():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.5, fuzzy_threshold=0.7)
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="Hello ... world",
        start_ms=0,
        end_ms=900,
    )
    aligned_words = [
        AlignedWord("Hello", "hello", 100, 250, 0.9),
        AlignedWord("wurld", "wurld", 500, 780, 0.7),
    ]

    reconciled_cues, quality = reconciler.reconcile([cue], aligned_words)
    words = reconciled_cues[0].words

    assert reconciled_cues[0].timing_mode == "reconciled_asr"
    assert words[0].match_method == "exact_normalized"
    assert words[1].source == "interpolated"
    assert words[1].display_text == "..."
    assert words[1].start_ms == 250
    assert words[1].end_ms == 500
    assert words[2].match_method == "fuzzy_normalized"
    assert quality["matched_word_ratio"] == 2 / 3
    assert quality["exact_match_ratio"] == 1 / 3


def test_reconciler_handles_empty_and_edge_interpolation_spans():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.3)
    empty_cue = SubtitleCue(
        cue_id="empty",
        speaker="Speaker 1",
        text="",
        start_ms=0,
        end_ms=100,
    )

    reconciled_cues, quality = reconciler.reconcile([empty_cue], [])

    assert reconciled_cues[0].timing_mode == "approximate"
    assert reconciled_cues[0].words == ()
    assert quality["global_score"] == 0.0

    edge_cue = SubtitleCue(
        cue_id="edge",
        speaker="Speaker 1",
        text="mystery hello ending",
        start_ms=0,
        end_ms=1000,
    )
    aligned_words = [AlignedWord("hello", "hello", 0, 1000, 0.8)]

    edge_reconciled, _ = reconciler.reconcile([edge_cue], aligned_words)
    edge_words = edge_reconciled[0].words

    assert edge_words[0].source == "interpolated"
    assert edge_words[0].start_ms == 0
    assert edge_words[0].end_ms == 1
    assert edge_words[2].source == "interpolated"
    assert edge_words[2].start_ms == 1000
    assert edge_words[2].end_ms == 1001


def test_reconciler_defaults_candidate_window_and_quality_contract():
    reconciler = TranscriptReconciler()

    assert reconciler.version == "v1"
    assert reconciler.match_window_ms == 500
    assert reconciler.minimum_match_ratio == 0.6
    assert reconciler.fuzzy_threshold == 0.86

    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="alpha beta",
        start_ms=1000,
        end_ms=2000,
    )
    aligned_words = [
        AlignedWord("before-edge", "beforeedge", 200, 500, 0.1),
        AlignedWord("alpha", "alpha", 500, 1200, 0.9),
        AlignedWord("beta", "beta", 1800, 2500, 0.8),
        AlignedWord("after-edge", "afteredge", 2500, 2600, 0.1),
        AlignedWord("outside", "outside", 2601, 2700, 0.1),
    ]

    candidates = reconciler._candidate_words_for_cue(cue, aligned_words)
    assert [word.text for word in candidates] == [
        "before-edge",
        "alpha",
        "beta",
        "after-edge",
    ]

    reconciled_cues, quality = reconciler.reconcile([cue], aligned_words)

    assert reconciled_cues[0].quality_score == 1.0
    assert quality == {
        "global_score": 1.0,
        "matched_word_ratio": 1.0,
        "exact_match_ratio": 1.0,
        "fallback_cue_ratio": 0.0,
    }
    assert reconciler._find_candidate_match("gamma", candidates, 0) == (
        None,
        "unmatched",
    )
    assert reconciler._compute_quality(0, 0, 0) == 0.0
    assert reconciler._compute_quality(1, 1, 2) == 0.6


def test_reconciler_accumulates_quality_across_multiple_cues():
    reconciler = TranscriptReconciler(minimum_match_ratio=0.5)
    cues = [
        SubtitleCue(
            cue_id="cue-1",
            speaker="Speaker 1",
            text="hello world",
            start_ms=0,
            end_ms=800,
        ),
        SubtitleCue(
            cue_id="cue-2",
            speaker="Speaker 2",
            text="missing token",
            start_ms=1000,
            end_ms=1800,
        ),
    ]
    aligned_words = [
        AlignedWord("hello", "hello", 100, 250, 0.9),
        AlignedWord("world", "world", 260, 450, 0.85),
    ]

    reconciled_cues, quality = reconciler.reconcile(cues, aligned_words)

    assert [cue.timing_mode for cue in reconciled_cues] == [
        "reconciled_asr",
        "approximate",
    ]
    assert quality == {
        "global_score": 0.6,
        "matched_word_ratio": 0.5,
        "exact_match_ratio": 0.5,
        "fallback_cue_ratio": 0.5,
    }


def test_reconciler_accepts_fuzzy_match_exactly_at_threshold():
    reconciler = TranscriptReconciler(fuzzy_threshold=0.8)
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="world",
        start_ms=0,
        end_ms=500,
    )
    aligned_words = [AlignedWord("wurld", "wurld", 100, 250, 0.7)]

    reconciled_cues, _ = reconciler.reconcile([cue], aligned_words)

    assert reconciled_cues[0].timing_mode == "reconciled_asr"
    assert reconciled_cues[0].words[0].match_method == "fuzzy_normalized"

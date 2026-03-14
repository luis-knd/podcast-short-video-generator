from src.domain.subtitle_models import AlignedWord, SubtitleCue
from src.infrastructure.subtitles.reconciler import TranscriptReconciler
from tests.infrastructure.reconciler_support_test import watchdog


def test_build_reconciled_words_advances_past_resolved_slots():
    reconciler = TranscriptReconciler()
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="alpha beta",
        start_ms=0,
        end_ms=500,
    )
    matches = [
        (0, AlignedWord("alpha", "alpha", 50, 150, 0.9), "exact_normalized"),
        (1, AlignedWord("beta", "beta", 200, 320, 0.85), "exact_normalized"),
    ]

    with watchdog():
        words = reconciler._build_reconciled_words(cue, list(cue.words), matches)

    assert [(word.display_text, word.start_ms, word.end_ms) for word in words] == [
        ("alpha", 50, 150),
        ("beta", 200, 320),
    ]


def test_build_reconciled_words_finishes_full_interpolation_runs():
    reconciler = TranscriptReconciler()
    cue = SubtitleCue(
        cue_id="cue-2",
        speaker="Speaker 1",
        text="gap-a gap-b gap-c",
        start_ms=0,
        end_ms=600,
    )

    with watchdog():
        words = reconciler._build_reconciled_words(cue, list(cue.words), [None, None, None])

    assert [(word.display_text, word.start_ms, word.end_ms, word.source) for word in words] == [
        ("gap-a", 0, 200, "interpolated"),
        ("gap-b", 200, 400, "interpolated"),
        ("gap-c", 400, 600, "interpolated"),
    ]

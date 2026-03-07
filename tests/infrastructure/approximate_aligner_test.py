from src.domain.subtitle_models import SubtitleCue
from src.infrastructure.subtitles.approximate_aligner import ApproximateWordAligner


def test_approximate_aligner_builds_reconciled_cues_with_exact_defaults():
    aligner = ApproximateWordAligner()
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 3",
        text="one two",
        start_ms=100,
        end_ms=300,
    )

    reconciled_cues = aligner.build_cues([cue])

    assert len(reconciled_cues) == 1
    reconciled_cue = reconciled_cues[0]
    assert reconciled_cue.cue_id == "cue-1"
    assert reconciled_cue.speaker == "Speaker 3"
    assert reconciled_cue.original_text == "one two"
    assert reconciled_cue.timing_mode == "approximate"
    assert reconciled_cue.quality_score == 0.0
    assert [word.display_text for word in reconciled_cue.words] == ["one", "two"]
    assert all(word.confidence == 0.0 for word in reconciled_cue.words)
    assert all(word.source == "approximate" for word in reconciled_cue.words)
    assert all(word.match_method == "approximate" for word in reconciled_cue.words)
    assert all(word.fallback_used is True for word in reconciled_cue.words)


def test_approximate_aligner_skips_cues_without_words():
    aligner = ApproximateWordAligner()
    cue = SubtitleCue(
        cue_id="cue-empty",
        speaker="Speaker 0",
        text="",
        start_ms=0,
        end_ms=1000,
    )

    assert aligner.build_cues([cue]) == []

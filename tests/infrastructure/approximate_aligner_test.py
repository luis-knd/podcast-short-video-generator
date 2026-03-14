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


def test_approximate_aligner_sets_start_ms_and_end_ms_from_word_payload():
    aligner = ApproximateWordAligner()
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="hello world",
        start_ms=1000,
        end_ms=3000,
    )

    reconciled_cues = aligner.build_cues([cue])

    words = reconciled_cues[0].words
    assert words[0].start_ms == 1000
    assert words[0].end_ms == 2000
    assert words[1].start_ms == 2000
    assert words[1].end_ms == 3000
    assert isinstance(words[0].start_ms, int)
    assert isinstance(words[0].end_ms, int)


def test_approximate_aligner_continue_skips_empty_cue_without_stopping_subsequent_cues():
    aligner = ApproximateWordAligner()
    cues = [
        SubtitleCue(cue_id="empty", speaker="S1", text="", start_ms=0, end_ms=500),
        SubtitleCue(cue_id="cue-2", speaker="S1", text="hello world", start_ms=1000, end_ms=3000),
        SubtitleCue(cue_id="cue-3", speaker="S2", text="foo bar", start_ms=4000, end_ms=5000),
    ]

    result = aligner.build_cues(cues)

    assert len(result) == 2
    assert result[0].cue_id == "cue-2"
    assert result[1].cue_id == "cue-3"


def test_approximate_aligner_sets_source_cue_start_ms_and_end_ms():
    aligner = ApproximateWordAligner()
    cue = SubtitleCue(
        cue_id="cue-timing",
        speaker="Speaker 2",
        text="one two three",
        start_ms=4000,
        end_ms=7000,
    )

    reconciled_cues = aligner.build_cues([cue])

    reconciled = reconciled_cues[0]
    assert reconciled.source_cue_start_ms == 4000
    assert reconciled.source_cue_end_ms == 7000

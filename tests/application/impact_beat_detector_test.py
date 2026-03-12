from src.application.broll.impact_beat_detector import ImpactBeatDetector
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline


def test_impact_beat_detector_finds_visual_high_confidence_beats():
    detector = ImpactBeatDetector()
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="",
                start_ms=1000,
                end_ms=2900,
                timing_mode="reconciled_asr",
                quality_score=0.86,
                words=(
                    ProjectedWord("Suddenly", 1000, 1260, 0.88, "reconciled", "exact_normalized"),
                    ProjectedWord("launch", 1260, 1520, 0.81, "reconciled", "exact_normalized"),
                    ProjectedWord("brutal", 1520, 1780, 0.85, "reconciled", "exact_normalized"),
                    ProjectedWord("urgent", 1780, 2040, 0.79, "reconciled", "exact_normalized"),
                    ProjectedWord("crash", 2040, 2300, 0.79, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 2300, 2600, 0.86, "reconciled", "exact_normalized"),
                    ProjectedWord("office!", 2600, 2900, 0.86, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.86,
    )

    beats = detector.detect(timeline)

    assert len(beats) == 1
    assert beats[0].beat_id == "beat-0001"
    assert beats[0].scores.total >= 0.68
    assert "visual anchors" in beats[0].reasons[0]


def test_impact_beat_detector_discards_low_confidence_or_too_short_windows():
    detector = ImpactBeatDetector()
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=4000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="",
                start_ms=100,
                end_ms=500,
                timing_mode="approximate",
                quality_score=0.0,
                words=(
                    ProjectedWord("esto", 100, 250, 0.0, "approximate", "approximate", True),
                    ProjectedWord("es", 250, 350, 0.0, "approximate", "approximate", True),
                    ProjectedWord("algo", 350, 500, 0.0, "approximate", "approximate", True),
                ),
            ),
        ),
        segments=(),
        quality_score=0.0,
    )

    assert detector.detect(timeline) == []


def test_impact_beat_detector_detects_confusing_negative_phrase_as_beat():
    detector = ImpactBeatDetector()
    timeline = _build_single_cue_timeline("It's so confusing with all those negatives.")

    beats = detector.detect(timeline)

    assert len(beats) == 1
    assert beats[0].scores.total >= 0.68
    assert beats[0].text == "It's so confusing with all those negatives."


def test_impact_beat_detector_detects_negative_thoughts_phrase_as_beat():
    detector = ImpactBeatDetector()
    timeline = _build_single_cue_timeline("Your mind's polluted with negative thoughts.")

    beats = detector.detect(timeline)

    assert len(beats) == 1
    assert beats[0].scores.total >= 0.68
    assert beats[0].scores.visualizability >= 0.6


def test_impact_beat_detector_keeps_generic_explanatory_phrase_below_threshold():
    detector = ImpactBeatDetector()
    timeline = _build_single_cue_timeline("This is a B2 level sentence.")

    beats = detector.detect(timeline)

    assert beats == []


def test_impact_beat_detector_promotes_only_high_salience_near_miss_when_needed():
    detector = ImpactBeatDetector(minimum_score=0.75)
    timeline = _build_single_cue_timeline("It's so confusing with all those negatives.")

    beats = detector.detect(timeline)

    assert len(beats) == 1
    assert any("near-miss" in reason for reason in beats[0].reasons)


def test_impact_beat_detector_does_not_promote_generic_near_miss():
    detector = ImpactBeatDetector(minimum_score=0.75)
    timeline = _build_single_cue_timeline("This is a B2 level sentence.")

    assert detector.detect(timeline) == []


def _build_single_cue_timeline(
    text: str,
    start_ms: int = 1000,
    word_duration_ms: int = 280,
    word_confidence: float = 0.93,
    cue_quality_score: float = 0.95,
) -> SubtitleTimeline:
    words = text.split()
    projected_words = tuple(
        ProjectedWord(
            text=word,
            start_ms=start_ms + index * word_duration_ms,
            end_ms=start_ms + (index + 1) * word_duration_ms,
            confidence=word_confidence,
            source="reconciled",
            match_method="exact_normalized",
        )
        for index, word in enumerate(words)
    )
    cue = ProjectedCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        original_text=text,
        start_ms=projected_words[0].start_ms,
        end_ms=projected_words[-1].end_ms,
        timing_mode="reconciled_asr",
        quality_score=cue_quality_score,
        words=projected_words,
    )
    return SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(cue,),
        segments=(),
        quality_score=cue_quality_score,
    )

from src.application.broll.impact_beat_detector import ImpactBeatDetector
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
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


def test_impact_beat_detector_keeps_scored_beats_before_near_miss_fallback(monkeypatch):
    detector = ImpactBeatDetector(minimum_score=0.7)
    accepted_beat = _build_impact_beat(
        text="launch product office",
        total_score=0.82,
        reasons=("contains concrete or visual anchors",),
    )
    promoted_near_miss = _build_impact_beat(
        text="confusing negatives",
        total_score=0.61,
        reasons=("promoted near-miss high-salience beat",),
    )
    monkeypatch.setattr(detector, "detect_candidates", lambda timeline: [accepted_beat, promoted_near_miss])

    beats = detector.detect(_build_single_cue_timeline("placeholder"))

    assert len(beats) == 1
    assert beats[0].text == "launch product office"


def test_impact_beat_detector_accepts_score_exactly_on_threshold(monkeypatch):
    detector = ImpactBeatDetector(minimum_score=0.7)
    threshold_beat = _build_impact_beat(
        text="launch product office",
        total_score=0.7,
        reasons=("contains concrete or visual anchors",),
    )
    monkeypatch.setattr(detector, "detect_candidates", lambda timeline: [threshold_beat])

    beats = detector.detect(_build_single_cue_timeline("placeholder"))

    assert len(beats) == 1
    assert beats[0].text == "launch product office"


def test_impact_beat_detector_does_not_promote_generic_near_miss():
    detector = ImpactBeatDetector(minimum_score=0.75)
    timeline = _build_single_cue_timeline("This is a B2 level sentence.")

    assert detector.detect(timeline) == []


def test_impact_beat_detector_splits_windows_on_markers_and_punctuation():
    detector = ImpactBeatDetector()
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="Launch product office then crash market city!",
                start_ms=1000,
                end_ms=3100,
                timing_mode="reconciled_asr",
                quality_score=0.9,
                words=(
                    ProjectedWord("Launch", 1000, 1300, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 1300, 1600, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("office", 1600, 1900, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("then", 1900, 2200, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("crash", 2200, 2500, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("market", 2500, 2800, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("city!", 2800, 3100, 0.9, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.9,
    )

    beats = detector.detect_candidates(timeline)

    assert [beat.beat_id for beat in beats] == ["beat-0001", "beat-0002"]
    assert {beat.text for beat in beats} == {"Launch product office then", "crash market city!"}


def test_impact_beat_detector_keeps_two_word_window_closed_by_punctuation():
    detector = ImpactBeatDetector()
    cue = ProjectedCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        original_text="Launch office!",
        start_ms=1000,
        end_ms=1600,
        timing_mode="reconciled_asr",
        quality_score=0.9,
        words=(
            ProjectedWord("Launch", 1000, 1300, 0.9, "reconciled", "exact_normalized"),
            ProjectedWord("office!", 1300, 1600, 0.9, "reconciled", "exact_normalized"),
        ),
    )

    windows = detector._build_windows(cue)

    assert len(windows) == 1
    assert [word.text for word in windows[0]] == ["Launch", "office!"]


def test_impact_beat_detector_closes_three_word_window_on_narrative_marker_only():
    detector = ImpactBeatDetector()
    words = [
        ProjectedWord("Launch", 1000, 1300, 0.9, "reconciled", "exact_normalized"),
        ProjectedWord("product", 1300, 1600, 0.9, "reconciled", "exact_normalized"),
        ProjectedWord("then", 1600, 1900, 0.9, "reconciled", "exact_normalized"),
    ]

    assert detector._should_close_window(words[:2]) is False
    assert detector._should_close_window(words) is True


def test_impact_beat_detector_closes_two_word_window_on_period_punctuation():
    detector = ImpactBeatDetector()
    words = [
        ProjectedWord("Launch", 1000, 1300, 0.9, "reconciled", "exact_normalized"),
        ProjectedWord("office.", 1300, 1600, 0.9, "reconciled", "exact_normalized"),
    ]

    assert detector._should_close_window(words) is True


def test_impact_beat_detector_blocks_promotion_when_timeline_quality_is_invalid():
    detector = ImpactBeatDetector(minimum_score=0.75)
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=_build_single_cue_timeline("It's so confusing with all those negatives.").cues,
        segments=(),
        quality_score="not-a-number",
    )

    assert detector.detect(timeline) == []


def test_impact_beat_detector_adds_queryable_anchor_reason_for_numeric_and_visual_tokens():
    detector = ImpactBeatDetector()
    timeline = _build_single_cue_timeline("Budget 2025 launch")

    beats = detector.detect_candidates(timeline)

    assert len(beats) == 1
    assert "has strong queryable anchors" in beats[0].reasons


def test_impact_beat_detector_averages_only_positive_word_confidences():
    detector = ImpactBeatDetector()
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=8000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="Launch product office",
                start_ms=1000,
                end_ms=2200,
                timing_mode="reconciled_asr",
                quality_score=0.95,
                words=(
                    ProjectedWord("Launch", 1000, 1400, 0.0, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 1400, 1800, 0.5, "reconciled", "exact_normalized"),
                    ProjectedWord("office", 1800, 2200, 1.0, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.95,
    )

    beats = detector.detect_candidates(timeline)

    assert len(beats) == 1
    assert beats[0].word_confidence_avg == 0.75


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


def _build_impact_beat(text: str, total_score: float, reasons: tuple[str, ...]) -> ImpactBeat:
    return ImpactBeat(
        beat_id="",
        text=text,
        start_ms=1000,
        end_ms=2200,
        duration_ms=1200,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.92,
        cue_quality_score=0.95,
        scores=BeatScoreBreakdown(
            total=total_score,
            visualizability=0.7,
            emotional_load=0.1,
            contrast=0.1,
            narrative_turn=0.1,
            verbal_force=0.2,
            duration_fit=1.0,
            timing_confidence=0.9,
            semantic_salience=0.7,
        ),
        reasons=reasons,
    )

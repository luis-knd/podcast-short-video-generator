import pytest

from src.application.broll.impact_beat_detector import ImpactBeatDetector
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline


def test_impact_beat_detector_uses_expected_defaults():
    detector = ImpactBeatDetector()

    assert detector.minimum_score == 0.68
    assert detector.minimum_visualizability == 0.35
    assert detector.minimum_timing_confidence == 0.55
    assert detector.min_duration_ms == 700
    assert detector.max_duration_ms == 3000
    assert detector.fallback_minimum_score == 0.58
    assert detector.fallback_minimum_semantic_salience == 0.55
    assert detector.minimum_timeline_quality_for_fallback == 0.85


def test_impact_beat_detector_detect_candidates_orders_scores_descending(monkeypatch):
    detector = ImpactBeatDetector()
    low = _build_beat("low", 0.61)
    high = _build_beat("high", 0.93)
    timeline = SubtitleTimeline(0, 5000, cues=("cue-1", "cue-2"), segments=(), quality_score=0.95)

    monkeypatch.setattr(detector, "_build_windows", lambda cue: [(cue,)])
    monkeypatch.setattr(
        detector,
        "_score_impact_beat",
        lambda words, cue: high if cue == "cue-1" else low,
    )
    monkeypatch.setattr(detector, "_promote_near_miss_beats", lambda ranked_beats, timeline: [])

    beats = detector.detect_candidates(timeline)

    assert [beat.text for beat in beats] == ["high", "low"]
    assert [beat.beat_id for beat in beats] == ["beat-0001", "beat-0002"]


def test_impact_beat_detector_build_windows_keeps_two_word_tail_window():
    detector = ImpactBeatDetector()
    cue = ProjectedCue(
        cue_id="cue-tail",
        speaker="Speaker 1",
        original_text="Launch office",
        start_ms=1000,
        end_ms=1600,
        timing_mode="reconciled_asr",
        quality_score=0.9,
        words=_build_words(("Launch", "office")),
    )

    windows = detector._build_windows(cue)

    assert len(windows) == 1
    assert [word.text for word in windows[0]] == ["Launch", "office"]


@pytest.mark.parametrize(
    ("word_count", "word_duration_ms", "expected"),
    [
        (8, 200, True),
        (7, 200, False),
        (3, 800, True),
    ],
)
def test_impact_beat_detector_closes_window_on_exact_boundaries(word_count, word_duration_ms, expected):
    detector = ImpactBeatDetector()
    words = _build_words(tuple(f"word-{index}" for index in range(word_count)), duration_ms=word_duration_ms)

    assert detector._should_close_window(words) is expected


def test_impact_beat_detector_exclamation_closes_window_before_following_word():
    detector = ImpactBeatDetector()
    cue = ProjectedCue(
        cue_id="cue-punctuation",
        speaker="Speaker 1",
        original_text="Launch office! market",
        start_ms=1000,
        end_ms=1900,
        timing_mode="reconciled_asr",
        quality_score=0.9,
        words=_build_words(("Launch", "office!", "market")),
    )

    windows = detector._build_windows(cue)

    assert len(windows) == 1
    assert [word.text for word in windows[0]] == ["Launch", "office!"]


def _build_words(texts: tuple[str, ...], start_ms: int = 1000, duration_ms: int = 300) -> tuple[ProjectedWord, ...]:
    return tuple(
        ProjectedWord(
            text=text,
            start_ms=start_ms + (index * duration_ms),
            end_ms=start_ms + ((index + 1) * duration_ms),
            confidence=0.9,
            source="reconciled",
            match_method="exact_normalized",
        )
        for index, text in enumerate(texts)
    )


def _build_beat(text: str, total: float) -> ImpactBeat:
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
            total=total,
            visualizability=0.8,
            emotional_load=0.3,
            contrast=0.1,
            narrative_turn=0.1,
            verbal_force=0.2,
            duration_fit=1.0,
            timing_confidence=0.9,
            semantic_salience=0.7,
        ),
        reasons=("contains concrete or visual anchors",),
    )

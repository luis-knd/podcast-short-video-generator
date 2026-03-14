import pytest

from src.application.broll.impact_beat_detector import ImpactBeatDetector
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
from src.domain.subtitle_models import ProjectedCue, ProjectedWord


def test_impact_beat_detector_uses_expected_defaults_when_none_is_provided():
    detector = ImpactBeatDetector(
        minimum_score=None,
        minimum_visualizability=None,
        minimum_timing_confidence=None,
        min_duration_ms=None,
        max_duration_ms=None,
        fallback_minimum_score=None,
        fallback_minimum_semantic_salience=None,
        minimum_timeline_quality_for_fallback=None,
    )

    assert detector.minimum_score == 0.68
    assert detector.minimum_visualizability == 0.35
    assert detector.minimum_timing_confidence == 0.55
    assert detector.min_duration_ms == 700
    assert detector.max_duration_ms == 3000
    assert detector.fallback_minimum_score == 0.58
    assert detector.fallback_minimum_semantic_salience == 0.55
    assert detector.minimum_timeline_quality_for_fallback == 0.85


def test_impact_beat_detector_rejects_low_visual_window_even_with_high_timing_confidence():
    detector = ImpactBeatDetector()
    words = _build_words(("the", "and", "to", "for"), confidences=(0.99, 0.99, 0.99, 0.99))
    cue = _build_cue(words, quality_score=0.99)

    beat = detector._score_impact_beat(words, cue)

    assert beat is None


def test_impact_beat_detector_counts_embedded_digits_as_numeric_visual_signal():
    detector = ImpactBeatDetector()
    words = _build_words(("B2B", "office"))

    score = detector._score_visualizability(words, ["b2b", "office"])

    assert score == 0.45


def test_impact_beat_detector_rejects_window_longer_than_max_duration_even_with_high_scores():
    detector = ImpactBeatDetector()
    words = _build_words(("Boss", "team", "work"), duration_ms=1100)
    cue = _build_cue(words, quality_score=0.99)

    beat = detector._score_impact_beat(words, cue)

    assert beat is None


def test_impact_beat_detector_accepts_high_semantic_window_even_when_visualizability_is_low():
    detector = ImpactBeatDetector()
    words = _build_words(("Boss", "team", "work"), duration_ms=400)
    cue = _build_cue(words, quality_score=0.95)

    beat = detector._score_impact_beat(words, cue)

    assert beat is not None
    assert beat.scores.visualizability == 0.1
    assert beat.scores.semantic_salience == 0.88


@pytest.mark.parametrize("duration_ms", (850, 2600))
def test_impact_beat_detector_keeps_penalty_boundaries_exclusive(duration_ms):
    detector = ImpactBeatDetector()

    penalty = detector._compute_penalties(["budget", "launch"], duration_ms, 0.70)

    assert penalty == 0.0


def test_impact_beat_detector_adds_contrast_reason_at_threshold():
    detector = ImpactBeatDetector()

    reasons = detector._build_reasons(
        ["but", "launch"],
        1200,
        visualizability=0.60,
        semantic_salience=0.60,
        emotional_load=0.50,
        contrast=0.50,
    )

    assert reasons == (
        "contains concrete or visual anchors",
        "contains abstract but visually reinforceable language",
        "contains emotional or urgency language",
        "contains contrast or narrative shift markers",
        "duration within ideal range",
    )


def test_impact_beat_detector_returns_no_promotion_when_timeline_has_no_quality_score():
    detector = ImpactBeatDetector()
    beat = ImpactBeat(
        beat_id="",
        text="friend wrong",
        start_ms=1000,
        end_ms=2200,
        duration_ms=1200,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.9,
        cue_quality_score=0.95,
        scores=BeatScoreBreakdown(
            total=detector.fallback_minimum_score,
            visualizability=0.2,
            emotional_load=0.2,
            contrast=0.0,
            narrative_turn=0.0,
            verbal_force=0.0,
            duration_fit=1.0,
            timing_confidence=0.9,
            semantic_salience=detector.fallback_minimum_semantic_salience,
        ),
        reasons=("contains abstract but visually reinforceable language",),
    )

    assert detector._promote_near_miss_beats([beat], object()) == []


def _build_words(
    texts: tuple[str, ...],
    start_ms: int = 1000,
    duration_ms: int = 300,
    confidences: tuple[float, ...] | None = None,
) -> tuple[ProjectedWord, ...]:
    values = confidences or tuple(0.9 for _ in texts)
    return tuple(
        ProjectedWord(
            text=text,
            start_ms=start_ms + index * duration_ms,
            end_ms=start_ms + (index + 1) * duration_ms,
            confidence=values[index],
            source="reconciled",
            match_method="exact_normalized",
        )
        for index, text in enumerate(texts)
    )


def _build_cue(words: tuple[ProjectedWord, ...], quality_score: float) -> ProjectedCue:
    return ProjectedCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        original_text=" ".join(word.text for word in words),
        start_ms=words[0].start_ms,
        end_ms=words[-1].end_ms,
        timing_mode="reconciled_asr",
        quality_score=quality_score,
        words=words,
    )

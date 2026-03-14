import pytest

from src.application.broll.impact_beat_detector import ImpactBeatDetector
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline


@pytest.mark.parametrize(
    ("first_spec", "second_spec"),
    [
        (
            ("same text", 1000, 1600, 0.82),
            ("same text", 2200, 2800, 0.64),
        ),
        (
            ("first text", 1000, 1600, 0.82),
            ("second text", 1000, 1600, 0.64),
        ),
    ],
)
def test_impact_beat_detector_replaces_only_the_exact_promoted_near_miss(first_spec, second_spec, monkeypatch):
    detector = ImpactBeatDetector()
    first_beat = _build_beat(*first_spec)
    second_beat = _build_beat(*second_spec)
    promoted_beat = _build_beat(
        first_beat.text,
        first_beat.start_ms,
        first_beat.end_ms,
        0.61,
        reasons=first_beat.reasons + ("promoted near-miss high-salience beat",),
    )
    timeline = SubtitleTimeline(0, 4000, cues=("cue-1", "cue-2"), segments=(), quality_score=0.95)

    monkeypatch.setattr(detector, "_build_windows", lambda cue: [(cue,)])
    monkeypatch.setattr(
        detector,
        "_score_impact_beat",
        lambda words, cue: first_beat if cue == "cue-1" else second_beat,
    )
    monkeypatch.setattr(detector, "_promote_near_miss_beats", lambda ranked_beats, _: [promoted_beat])

    beats = detector.detect_candidates(timeline)

    assert [(beat.text, beat.start_ms, beat.end_ms) for beat in beats] == [
        (first_beat.text, first_beat.start_ms, first_beat.end_ms),
        (second_beat.text, second_beat.start_ms, second_beat.end_ms),
    ]
    assert beats[0].reasons[-1] == "promoted near-miss high-salience beat"


@pytest.mark.parametrize("suffix", ("?", ";", ":"))
def test_impact_beat_detector_closes_window_on_supported_terminal_punctuation(suffix):
    detector = ImpactBeatDetector()
    words = _build_words(("Launch", f"office{suffix}"))

    assert detector._should_close_window(list(words)) is True


def test_impact_beat_detector_scores_visualizability_from_concrete_numeric_and_proper_case_signals():
    detector = ImpactBeatDetector()
    words = _build_words(("Budget", "2025", "office"))

    score = detector._score_visualizability(words, ["budget", "2025", "office"])

    assert score == 0.7


def test_impact_beat_detector_returns_zero_semantic_salience_for_empty_tokens():
    detector = ImpactBeatDetector()

    assert detector._score_semantic_salience([]) == 0.0


def test_impact_beat_detector_scores_semantic_salience_from_unique_terms_and_patterns():
    detector = ImpactBeatDetector()

    score = detector._score_semantic_salience(["friend", "friend", "wrong", "budget"])

    assert score == 0.82


def test_impact_beat_detector_returns_zero_timing_confidence_for_approximate_cue():
    detector = ImpactBeatDetector()
    words = _build_words(("Launch", "office"))
    cue = _build_cue(("Launch", "office"), timing_mode="approximate")

    assert detector._score_timing_confidence(words, cue) == 0.0


def test_impact_beat_detector_weights_timing_confidence_from_cue_and_word_confidence():
    detector = ImpactBeatDetector()
    words = _build_words(("Launch", "office"), confidences=(0.4, 0.8))
    cue = _build_cue(("Launch", "office"), quality_score=0.8)

    score = detector._score_timing_confidence(words, cue)

    assert score == 0.73


@pytest.mark.parametrize(
    ("tokens", "duration_ms", "cue_quality_score", "expected"),
    [
        (["thing"], 2700, 0.65, 0.32),
        (["the", "and"], 800, 0.65, 0.45),
    ],
)
def test_impact_beat_detector_adds_only_applicable_penalties(tokens, duration_ms, cue_quality_score, expected):
    detector = ImpactBeatDetector()

    penalty = detector._compute_penalties(tokens, duration_ms, cue_quality_score)

    assert penalty == pytest.approx(expected)


def test_impact_beat_detector_marks_exact_near_miss_thresholds_as_promotable():
    detector = ImpactBeatDetector()
    beat = _build_beat(
        "budget launch",
        1000,
        2200,
        detector.fallback_minimum_score,
        semantic_salience=detector.fallback_minimum_semantic_salience,
    )

    assert detector._is_promotable_near_miss(beat) is True


def test_impact_beat_detector_promotes_first_eligible_near_miss_at_quality_boundary():
    detector = ImpactBeatDetector()
    low_score = _build_beat("budget launch", 1000, 2200, detector.fallback_minimum_score - 0.01)
    promoted = _build_beat(
        "friend wrong",
        2500,
        3700,
        detector.fallback_minimum_score,
        semantic_salience=detector.fallback_minimum_semantic_salience,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=5000,
        cues=(),
        segments=(),
        quality_score=detector.minimum_timeline_quality_for_fallback,
    )

    beats = detector._promote_near_miss_beats([low_score, promoted], timeline)

    assert len(beats) == 1
    assert beats[0].text == "friend wrong"
    assert "promoted near-miss high-salience beat" in beats[0].reasons


def test_impact_beat_detector_scores_complete_high_salience_window_consistently():
    detector = ImpactBeatDetector()
    words = _build_words(("Confusing", "negative", "budget", "launch"), confidences=(0.9, 0.9, 0.9, 0.9))
    cue = _build_cue(("Confusing", "negative", "budget", "launch"), quality_score=0.8)

    beat = detector._score_impact_beat(words, cue)

    assert beat is not None
    assert beat.text == "Confusing negative budget launch"
    assert beat.duration_ms == 1200
    assert beat.scores == BeatScoreBreakdown(
        total=0.7602,
        visualizability=1.0,
        emotional_load=0.6667,
        contrast=0.0,
        narrative_turn=0.0,
        verbal_force=0.3333,
        duration_fit=1.0,
        timing_confidence=0.835,
        semantic_salience=1.0,
    )
    assert beat.reasons == (
        "contains concrete or visual anchors",
        "contains abstract but visually reinforceable language",
        "contains emotional or urgency language",
        "duration within ideal range",
        "has strong queryable anchors",
    )


def _build_words(
    texts: tuple[str, ...],
    start_ms: int = 1000,
    duration_ms: int = 300,
    confidences: tuple[float, ...] | None = None,
) -> tuple[ProjectedWord, ...]:
    confidence_values = confidences or tuple(0.9 for _ in texts)
    return tuple(
        ProjectedWord(
            text=text,
            start_ms=start_ms + (index * duration_ms),
            end_ms=start_ms + ((index + 1) * duration_ms),
            confidence=confidence_values[index],
            source="reconciled",
            match_method="exact_normalized",
        )
        for index, text in enumerate(texts)
    )


def _build_cue(
    texts: tuple[str, ...],
    timing_mode: str = "reconciled_asr",
    quality_score: float = 0.9,
) -> ProjectedCue:
    words = _build_words(texts)
    return ProjectedCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        original_text=" ".join(texts),
        start_ms=words[0].start_ms,
        end_ms=words[-1].end_ms,
        timing_mode=timing_mode,
        quality_score=quality_score,
        words=words,
    )


def _build_beat(
    text: str,
    start_ms: int,
    end_ms: int,
    total: float,
    semantic_salience: float = 0.7,
    reasons: tuple[str, ...] = ("contains concrete or visual anchors",),
) -> ImpactBeat:
    return ImpactBeat(
        beat_id="",
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.9,
        cue_quality_score=0.95,
        scores=BeatScoreBreakdown(
            total=total,
            visualizability=0.7,
            emotional_load=0.2,
            contrast=0.0,
            narrative_turn=0.0,
            verbal_force=0.2,
            duration_fit=1.0,
            timing_confidence=0.9,
            semantic_salience=semantic_salience,
        ),
        reasons=reasons,
    )

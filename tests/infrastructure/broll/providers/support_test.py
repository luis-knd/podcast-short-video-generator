from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat


def build_provider_test_beat(text: str = "The market crash hit hard") -> ImpactBeat:
    return ImpactBeat(
        beat_id="beat-1",
        text=text,
        start_ms=1000,
        end_ms=2800,
        duration_ms=1800,
        timing_mode="aligned",
        word_confidence_avg=0.92,
        cue_quality_score=0.95,
        scores=BeatScoreBreakdown(
            total=0.91,
            visualizability=0.9,
            emotional_load=0.8,
            contrast=0.7,
            narrative_turn=0.8,
            verbal_force=0.75,
            duration_fit=0.9,
            timing_confidence=0.95,
        ),
        reasons=("high_visualizability",),
    )

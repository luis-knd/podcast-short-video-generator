from src.application.broll.broll_query_generator import BrollQueryGenerator
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat


def test_query_generator_builds_exact_visual_and_fallback_queries():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("the budget app riesgo"))

    assert queries == (
        "budget app riesgo",
        "money spreadsheet phone screen",
        "money spreadsheet",
    )


def test_query_generator_deduplicates_queries_when_visual_and_fallback_match():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("phone"))

    assert queries == ("phone",)


def test_query_generator_returns_normalized_text_when_no_query_can_be_built():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("..."))

    assert queries == ("",)


def test_query_generator_adds_semantic_fallback_for_confusion_language():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("It's so confusing with all those negatives."))

    assert "confusing negatives" in queries
    assert "confused person complex text" in queries


def test_query_generator_filters_truncated_or_contextless_queries():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("bad or negative thoughts."))

    assert "bad negative thoughts" in queries
    assert "stressed person thinking alone" in queries
    assert "bad or" not in queries


def _build_beat(text: str) -> ImpactBeat:
    return ImpactBeat(
        beat_id="beat-1",
        text=text,
        start_ms=1000,
        end_ms=2000,
        duration_ms=1000,
        timing_mode="aligned",
        word_confidence_avg=0.9,
        cue_quality_score=0.9,
        scores=BeatScoreBreakdown(
            total=0.9,
            visualizability=0.8,
            emotional_load=0.7,
            contrast=0.6,
            narrative_turn=0.5,
            verbal_force=0.6,
            duration_fit=0.8,
            timing_confidence=0.95,
            semantic_salience=0.8,
        ),
        reasons=("query",),
    )

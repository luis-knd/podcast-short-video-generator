import pytest

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
    assert "confused person negative spiral" in queries


def test_query_generator_filters_truncated_or_contextless_queries():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("bad or negative thoughts."))

    assert "bad negative thoughts" in queries
    assert "stressed person thinking alone" in queries
    assert "bad or" not in queries


def test_query_generator_limits_exact_query_to_four_content_tokens():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("budget app riesgo tiempo mercado"))

    assert queries[0] == "budget app riesgo tiempo"
    assert "budget app riesgo tiempo mercado" not in queries


def test_query_generator_limits_semantic_query_to_four_tokens():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("boss friend presentation work"))

    assert "office manager friends talking" in queries
    assert "office manager friends talking office" not in queries


def test_query_generator_adds_semantic_fallback_for_polluted_mind_language():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("My polluted mind keeps racing"))

    assert "stressed person thinking alone" in queries


def test_query_generator_accepts_exactly_two_meaningful_tokens():
    generator = BrollQueryGenerator()

    assert generator._is_useful_query("budget app") is True


def test_query_generator_rejects_queries_made_only_of_generic_tokens():
    generator = BrollQueryGenerator()

    assert generator._is_useful_query("person song") is False


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["confusing", "negative"], ["confused", "person", "negative", "spiral"]),
        (["confusing", "negatives"], ["confused", "person", "negative", "spiral"]),
        (["confusing"], ["confused", "person"]),
        (["polluted", "mind"], ["stressed", "person", "thinking", "alone"]),
        (["polluted", "mind's"], ["stressed", "person", "thinking", "alone"]),
        (["polluted"], ["overwhelmed", "face"]),
        (["negative", "thoughts"], ["stressed", "person", "thinking", "alone"]),
        (["thoughts"], ["thinking", "alone"]),
        (["negative"], ["stressed", "person"]),
    ],
)
def test_semantic_tokens_exact_branch_conditions(tokens, expected):
    generator = BrollQueryGenerator()

    result = generator._semantic_tokens(tokens)

    assert result == expected


def test_semantic_tokens_confusing_requires_negative_or_negatives_not_just_confusing():
    generator = BrollQueryGenerator()

    only_confusing = generator._semantic_tokens(["confusing"])
    confusing_and_negative = generator._semantic_tokens(["confusing", "negative"])

    assert only_confusing != ["confused", "person", "negative", "spiral"]
    assert confusing_and_negative == ["confused", "person", "negative", "spiral"]


def test_semantic_tokens_polluted_requires_mind_not_just_polluted():
    generator = BrollQueryGenerator()

    only_polluted = generator._semantic_tokens(["polluted"])
    polluted_and_mind = generator._semantic_tokens(["polluted", "mind"])

    assert only_polluted != ["stressed", "person", "thinking", "alone"]
    assert polluted_and_mind == ["stressed", "person", "thinking", "alone"]


def test_semantic_tokens_negative_thoughts_requires_both_tokens():
    generator = BrollQueryGenerator()

    only_negative = generator._semantic_tokens(["negative"])
    only_thoughts = generator._semantic_tokens(["thoughts"])
    both = generator._semantic_tokens(["negative", "thoughts"])

    assert only_negative != ["stressed", "person", "thinking", "alone"]
    assert only_thoughts != ["stressed", "person", "thinking", "alone"]
    assert both == ["stressed", "person", "thinking", "alone"]


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

from src.application.broll.broll_query_generator import BrollQueryGenerator
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat


def test_broll_query_generator_semantic_tokens_treats_negatives_as_confusion_pattern():
    generator = BrollQueryGenerator()

    tokens = generator._semantic_tokens(["confusing", "negatives"])

    assert tokens == ["confused", "person", "negative", "spiral"]


def test_broll_query_generator_semantic_tokens_treats_negative_thoughts_as_overwhelm_pattern():
    generator = BrollQueryGenerator()

    tokens = generator._semantic_tokens(["negative", "thoughts"])

    assert tokens == ["stressed", "person", "thinking", "alone"]


def test_broll_query_generator_generate_keeps_semantic_query_for_negative_thoughts_phrase():
    generator = BrollQueryGenerator()

    queries = generator.generate(_build_beat("bad or negative thoughts"))

    assert queries == (
        "bad negative thoughts",
        "stressed person thinking alone",
        "bad negative",
    )


def test_broll_query_generator_content_tokens_falls_back_to_normalized_stopwords_when_needed():
    generator = BrollQueryGenerator()

    tokens = generator._content_tokens("The or and")

    assert tokens == ["the", "or", "and"]


def test_broll_query_generator_visual_tokens_expands_aliases_and_keeps_non_aliased_tokens():
    generator = BrollQueryGenerator()

    tokens = generator._visual_tokens(["budget", "plain"])

    assert tokens == ["money", "spreadsheet", "plain"]


def test_broll_query_generator_fallback_tokens_prefers_first_two_visual_aliases():
    generator = BrollQueryGenerator()

    tokens = generator._fallback_tokens(["budget", "app", "plain"])

    assert tokens == ["money", "spreadsheet"]


def test_broll_query_generator_fallback_tokens_returns_first_two_original_tokens_without_aliases():
    generator = BrollQueryGenerator()

    tokens = generator._fallback_tokens(["plain", "words", "extra"])

    assert tokens == ["plain", "words"]


def test_broll_query_generator_is_useful_query_normalizes_case_and_punctuation():
    generator = BrollQueryGenerator()

    assert generator._is_useful_query("Budget, APP!") is True
    assert generator._is_useful_query("Person, song!") is False


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

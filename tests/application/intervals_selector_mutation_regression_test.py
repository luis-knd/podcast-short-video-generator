from src.application.intervals.models import IntervalCandidate, ScoredIntervalCandidate, ViralityScoreBreakdown
from src.application.intervals.selector import DiversityAwareIntervalSelector

EMPTY_BREAKDOWN = ViralityScoreBreakdown(
    hook_strength=0.0,
    narrative_tension=0.0,
    practical_utility=0.0,
    emotional_charge=0.0,
    payoff_strength=0.0,
    context_independence=0.0,
    duration_fit=1.0,
    intro_outro_penalty=0.0,
    cta_penalty=0.0,
    genericity_penalty=0.0,
)


def _candidate(start_ms: int, end_ms: int, total_score: float, opening_text: str) -> ScoredIntervalCandidate:
    candidate = IntervalCandidate(
        start_ms=start_ms,
        end_ms=end_ms,
        cue_ids=(f"cue-{start_ms}",),
        text=opening_text,
        word_count=24,
        speaker_count=1,
        opening_text=opening_text,
        closing_text=opening_text,
    )
    return ScoredIntervalCandidate(
        candidate=candidate, breakdown=EMPTY_BREAKDOWN, total_score=total_score, reasons=("x",)
    )


def test_diversity_selector_respects_threshold_edges_and_target_count_without_breaking_early():
    selector = DiversityAwareIntervalSelector(target_count=2, minimum_score=0.5, max_overlap_ratio=0.6)
    candidates = [
        _candidate(0, 10_000, 0.9, "Hook alpha"),
        _candidate(30_000, 40_000, 0.5, "Distinct beta"),
        _candidate(60_000, 70_000, 0.49, "Distinct gamma"),
        _candidate(90_000, 100_000, 0.8, "Distinct delta"),
    ]

    selected = selector.select(candidates)

    assert [item.total_score for item in selected] == [0.9, 0.8]


def test_diversity_selector_keeps_exact_overlap_boundary_but_skips_exact_opening_similarity_boundary():
    selector = DiversityAwareIntervalSelector(target_count=3, minimum_score=0.28, max_overlap_ratio=0.6)
    kept = _candidate(0, 10_000, 0.9, "alpha beta gamma delta")
    overlap_boundary = _candidate(4_000, 14_000, 0.85, "gamma delta")
    similarity_boundary = _candidate(20_000, 30_000, 0.8, "alpha beta gamma delta omega")
    distinct = _candidate(40_000, 50_000, 0.79, "omega sigma")

    selected = selector.select([kept, overlap_boundary, similarity_boundary, distinct])

    assert [item.candidate.start_ms for item in selected] == [0, 4_000, 40_000]
    assert DiversityAwareIntervalSelector._overlap_ratio(kept, overlap_boundary) == 0.6
    assert DiversityAwareIntervalSelector._opening_similarity(kept, similarity_boundary) == 0.8


def test_diversity_selector_opening_similarity_returns_zero_when_any_side_has_no_tokens():
    first = _candidate(0, 10_000, 0.9, "")
    second = _candidate(20_000, 30_000, 0.8, "meaningful words")

    assert DiversityAwareIntervalSelector._opening_similarity(first, second) == 0.0

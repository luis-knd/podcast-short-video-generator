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


def _scored_candidate(start_ms: int, end_ms: int, total_score: float, text: str) -> ScoredIntervalCandidate:
    return ScoredIntervalCandidate(
        candidate=IntervalCandidate(
            start_ms=start_ms,
            end_ms=end_ms,
            cue_ids=(f"cue-{start_ms}",),
            text=text,
            word_count=30,
            speaker_count=1,
            opening_text=text,
            closing_text=text,
        ),
        breakdown=EMPTY_BREAKDOWN,
        total_score=total_score,
        reasons=("test",),
    )


def test_diversity_aware_interval_selector_skips_heavy_overlap_in_favor_of_next_best_distinct_candidate():
    selector = DiversityAwareIntervalSelector(target_count=2, max_overlap_ratio=0.55)
    candidates = [
        _scored_candidate(180_000, 208_000, 0.92, "Why this phrase can backfire at work"),
        _scored_candidate(188_000, 214_000, 0.89, "Why this phrase can backfire at work, alternate cut"),
        _scored_candidate(455_000, 482_000, 0.83, "Your mind is polluted is too strong for a friend"),
    ]

    selected = selector.select(candidates)

    assert [item.total_score for item in selected] == [0.92, 0.83]
    assert selected[0].candidate.start_ms == 180_000
    assert selected[1].candidate.start_ms == 455_000

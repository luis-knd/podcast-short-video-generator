from src.application.intervals.models import IntervalCandidate, ViralityScoreBreakdown
from src.application.intervals.virality_scorer import IntervalViralityScorer


def _candidate(**overrides) -> IntervalCandidate:
    payload = {
        "start_ms": 180_000,
        "end_ms": 206_000,
        "cue_ids": ("cue-1", "cue-2", "cue-3"),
        "text": (
            "Why is this phrase dangerous at work? Because it sounds romantic in the song but rude in real life. "
            "Instead, you could say let's stay in touch."
        ),
        "word_count": 29,
        "speaker_count": 1,
        "opening_text": "Why is this phrase dangerous at work?",
        "closing_text": "Instead, you could say let's stay in touch.",
    }
    payload.update(overrides)
    return IntervalCandidate(**payload)


def test_interval_virality_scorer_returns_exact_breakdown_for_a_strong_candidate():
    scorer = IntervalViralityScorer()

    scored = scorer.score(_candidate(), episode_duration_ms=720_000)

    assert scored.breakdown.hook_strength == 0.75
    assert scored.breakdown.narrative_tension == 0.75
    assert scored.breakdown.practical_utility == 0.95
    assert scored.breakdown.emotional_charge == 0.5
    assert scored.breakdown.payoff_strength == 0.95
    assert scored.breakdown.context_independence == 0.9
    assert scored.breakdown.duration_fit == 1.0
    assert scored.breakdown.intro_outro_penalty == 0.0
    assert scored.breakdown.cta_penalty == 0.0
    assert scored.breakdown.genericity_penalty == 0.0
    assert scored.total_score == 0.8365
    assert scored.reasons == (
        "strong opening hook",
        "contains contrast or tension",
        "contains practical takeaway",
        "ends with payoff or safe swap",
    )


def test_interval_virality_scorer_helper_branches_cover_question_you_and_duration_boundaries():
    scorer = IntervalViralityScorer()

    assert scorer._duration_fit(24_000) == 1.0
    assert scorer._duration_fit(32_000) == 1.0
    assert scorer._duration_fit(12_000) == 0.5
    assert scorer._duration_fit(36_000) == 0.5
    assert scorer._duration_fit(48_000) == 0.0
    assert (
        scorer._hook_strength(_candidate(opening_text="You should avoid this?"), ["you", "should", "avoid", "this"])
        == 0.85
    )
    assert (
        scorer._hook_strength(_candidate(opening_text="How can you fix this"), ["how", "can", "you", "fix", "this"])
        == 0.35
    )


def test_interval_virality_scorer_practical_payoff_and_density_helpers_cover_exact_scores():
    scorer = IntervalViralityScorer()
    tokens = ["work", "friend", "safe", "swap", "bonus"]
    closing_tokens = ["instead", "better", "say", "touch"]

    assert scorer._tokens("Dangerous, rude?  ") == ["dangerous", "rude"]
    assert scorer._token_density([], scorer.HOOK_MARKERS) == 0.0
    assert scorer._token_density(tokens, {"work", "friend", "safe", "swap", "bonus"}) == 1.0
    assert scorer._practical_utility(tokens, closing_tokens) == 1.0
    assert scorer._payoff_strength(closing_tokens) == 1.0


def test_interval_virality_scorer_context_intro_cta_and_genericity_branches_are_distinguishable():
    scorer = IntervalViralityScorer()

    weak_opener_candidate = _candidate(opening_text="Because this sounds wrong", start_ms=10_000, end_ms=700_000)
    assert scorer._context_independence(weak_opener_candidate, ["because", "this", "sounds", "wrong"]) == 0.2
    assert (
        scorer._context_independence(_candidate(opening_text="What does this mean?"), ["what", "does", "this", "mean"])
        == 0.9
    )
    assert scorer._context_independence(_candidate(opening_text="This is useful"), ["this", "is", "useful"]) == 0.45
    assert (
        scorer._context_independence(
            _candidate(opening_text="This is useful context here"), ["this", "is", "useful", "context", "here"]
        )
        == 0.65
    )
    assert scorer._context_independence(_candidate(opening_text=""), []) == 0.0

    intro_outro_candidate = _candidate(
        start_ms=30_000,
        end_ms=700_000,
        opening_text="Welcome back and remember",
    )
    assert (
        scorer._intro_outro_penalty(
            intro_outro_candidate,
            ["welcome", "back", "and", "remember"],
            episode_duration_ms=720_000,
        )
        == 1.0
    )
    assert scorer._cta_penalty(["welcome", "subscribe", "podcast", "episode"]) == 1.0
    assert scorer._genericity_penalty([], 0) == 1.0
    assert scorer._genericity_penalty(["plain", "generic", "words"], 10) == 0.5
    assert scorer._genericity_penalty(["plain", "generic", "words"], 25) == 0.25
    assert scorer._genericity_penalty(["dangerous", "plain"], 10) == 0.0


def test_interval_virality_scorer_build_reasons_includes_penalty_reason_when_threshold_is_reached():
    breakdown = ViralityScoreBreakdown(
        hook_strength=0.6,
        narrative_tension=0.3,
        practical_utility=0.35,
        emotional_charge=0.0,
        payoff_strength=0.35,
        context_independence=0.0,
        duration_fit=1.0,
        intro_outro_penalty=0.5,
        cta_penalty=0.0,
        genericity_penalty=0.0,
    )

    assert IntervalViralityScorer._build_reasons(breakdown) == (
        "strong opening hook",
        "contains contrast or tension",
        "contains practical takeaway",
        "ends with payoff or safe swap",
        "intro or outro penalty applied",
    )

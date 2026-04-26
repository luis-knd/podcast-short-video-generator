from src.application.intervals.models import IntervalCandidate
from src.application.intervals.virality_scorer import IntervalViralityScorer


def test_interval_virality_scorer_prefers_hook_tension_and_payoff_over_intro_boilerplate():
    intro_candidate = IntervalCandidate(
        start_ms=0,
        end_ms=24_000,
        cue_ids=("cue-1", "cue-2"),
        text=(
            "Welcome back to the podcast. Today we are breaking down another song and looking at the charts. "
            "Stay with us until the end."
        ),
        word_count=25,
        speaker_count=1,
        opening_text="Welcome back to the podcast.",
        closing_text="Stay with us until the end.",
    )
    viral_candidate = IntervalCandidate(
        start_ms=180_000,
        end_ms=206_000,
        cue_ids=("cue-30", "cue-31", "cue-32"),
        text=(
            "Why is this phrase dangerous at work? Because it sounds romantic in the song but rude in real life. "
            "Instead, you could say let's stay in touch."
        ),
        word_count=29,
        speaker_count=1,
        opening_text="Why is this phrase dangerous at work?",
        closing_text="Instead, you could say let's stay in touch.",
    )

    scorer = IntervalViralityScorer()

    scored_intro = scorer.score(intro_candidate, episode_duration_ms=720_000)
    scored_viral = scorer.score(viral_candidate, episode_duration_ms=720_000)

    assert scored_viral.total_score > scored_intro.total_score
    assert scored_viral.breakdown.hook_strength > 0
    assert scored_viral.breakdown.practical_utility > 0
    assert scored_viral.breakdown.payoff_strength > 0
    assert scored_intro.breakdown.intro_outro_penalty > 0

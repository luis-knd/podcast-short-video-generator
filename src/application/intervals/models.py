from dataclasses import dataclass


@dataclass(frozen=True)
class IntervalCandidate:
    start_ms: int
    end_ms: int
    cue_ids: tuple[str, ...]
    text: str
    word_count: int
    speaker_count: int
    opening_text: str
    closing_text: str

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass(frozen=True)
class ViralityScoreBreakdown:
    hook_strength: float
    narrative_tension: float
    practical_utility: float
    emotional_charge: float
    payoff_strength: float
    context_independence: float
    duration_fit: float
    intro_outro_penalty: float
    cta_penalty: float
    genericity_penalty: float


@dataclass(frozen=True)
class ScoredIntervalCandidate:
    candidate: IntervalCandidate
    breakdown: ViralityScoreBreakdown
    total_score: float
    reasons: tuple[str, ...]

from src.application.intervals.models import IntervalCandidate, ScoredIntervalCandidate, ViralityScoreBreakdown
from src.domain.text_utils import normalize_token


class IntervalViralityScorer:
    HOOK_MARKERS = frozenset({"why", "how", "what", "imagine", "careful", "problem", "dangerous"})
    CONTRAST_MARKERS = frozenset({"but", "however", "instead", "wrong", "problem", "rude"})
    UTILITY_MARKERS = frozenset({"example", "instead", "better", "work", "interview", "friend", "safe", "swap", "use"})
    EMOTIONAL_MARKERS = frozenset(
        {"stupid", "wrong", "rude", "grave", "dead", "funeral", "polluted", "negative", "dangerous"}
    )
    CTA_MARKERS = frozenset({"subscribe", "podcast", "welcome", "episode", "charts"})
    OUTRO_MARKERS = frozenset({"goodbye", "see", "again", "remember", "listen", "shadow"})
    CONTEXT_WEAK_OPENERS = frozenset({"and", "but", "so", "because", "then"})

    @staticmethod
    def _duration_fit(duration_ms: int) -> float:
        if 24_000 <= duration_ms <= 32_000:
            return 1.0
        if duration_ms < 24_000:
            return round(max(0.0, duration_ms / 24_000), 4)
        return round(max(0.0, 1 - ((duration_ms - 32_000) / 8_000)), 4)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return [normalized for normalized in (normalize_token(part) for part in text.split()) if normalized]

    @staticmethod
    def _token_density(tokens: list[str], markers: frozenset[str] | set[str]) -> float:
        if not tokens:
            return 0.0
        hits = sum(1 for token in tokens if token in markers)
        return round(min(1.0, hits / max(1, min(4, len(tokens)))), 4)

    @staticmethod
    def _build_reasons(breakdown: ViralityScoreBreakdown) -> tuple[str, ...]:
        reasons: list[str] = []
        if breakdown.hook_strength >= 0.6:
            reasons.append("strong opening hook")
        if breakdown.narrative_tension >= 0.3:
            reasons.append("contains contrast or tension")
        if breakdown.practical_utility >= 0.35:
            reasons.append("contains practical takeaway")
        if breakdown.payoff_strength >= 0.35:
            reasons.append("ends with payoff or safe swap")
        if breakdown.intro_outro_penalty >= 0.5:
            reasons.append("intro or outro penalty applied")
        return tuple(reasons)

    def score(self, candidate: IntervalCandidate, episode_duration_ms: int) -> ScoredIntervalCandidate:
        tokens = self._tokens(candidate.text)
        opening_tokens = self._tokens(candidate.opening_text)
        closing_tokens = self._tokens(candidate.closing_text)

        hook_strength = self._hook_strength(candidate, opening_tokens)
        narrative_tension = self._token_density(tokens, self.CONTRAST_MARKERS)
        practical_utility = self._practical_utility(tokens, closing_tokens)
        emotional_charge = self._token_density(tokens, self.EMOTIONAL_MARKERS)
        payoff_strength = self._payoff_strength(closing_tokens)
        context_independence = self._context_independence(candidate, opening_tokens)
        duration_fit = self._duration_fit(candidate.duration_ms)
        intro_outro_penalty = self._intro_outro_penalty(candidate, opening_tokens, episode_duration_ms)
        cta_penalty = self._cta_penalty(tokens)
        genericity_penalty = self._genericity_penalty(tokens, candidate.word_count)

        total_score = max(
            0.0,
            min(
                1.0,
                round(
                    (
                        0.19 * hook_strength
                        + 0.14 * narrative_tension
                        + 0.20 * practical_utility
                        + 0.11 * emotional_charge
                        + 0.16 * payoff_strength
                        + 0.08 * context_independence
                        + 0.12 * duration_fit
                        - 0.24 * intro_outro_penalty
                        - 0.12 * cta_penalty
                        - 0.10 * genericity_penalty
                    ),
                    4,
                ),
            ),
        )

        breakdown = ViralityScoreBreakdown(
            hook_strength=hook_strength,
            narrative_tension=narrative_tension,
            practical_utility=practical_utility,
            emotional_charge=emotional_charge,
            payoff_strength=payoff_strength,
            context_independence=context_independence,
            duration_fit=duration_fit,
            intro_outro_penalty=intro_outro_penalty,
            cta_penalty=cta_penalty,
            genericity_penalty=genericity_penalty,
        )
        return ScoredIntervalCandidate(
            candidate=candidate,
            breakdown=breakdown,
            total_score=total_score,
            reasons=self._build_reasons(breakdown),
        )

    def _hook_strength(self, candidate: IntervalCandidate, opening_tokens: list[str]) -> float:
        score = self._token_density(opening_tokens, self.HOOK_MARKERS)
        if "?" in candidate.opening_text:
            score = max(score, 0.75)
        if any(token == "you" for token in opening_tokens):
            score += 0.10
        return min(1.0, round(score, 4))

    def _practical_utility(self, tokens: list[str], closing_tokens: list[str]) -> float:
        score = self._token_density(tokens, self.UTILITY_MARKERS)
        if {"work", "interview"} & set(tokens):
            score += 0.20
        if {"instead", "better"} & set(closing_tokens):
            score += 0.25
        return min(1.0, round(score, 4))

    def _payoff_strength(self, closing_tokens: list[str]) -> float:
        payoff_terms = {"instead", "better", "say", "safe", "swap", "touch", "yourself"}
        return min(
            1.0, round(self._token_density(closing_tokens, payoff_terms) + 0.20 * ("instead" in closing_tokens), 4)
        )

    def _context_independence(self, candidate: IntervalCandidate, opening_tokens: list[str]) -> float:
        if not opening_tokens:
            return 0.0
        if opening_tokens[0] in self.CONTEXT_WEAK_OPENERS:
            return 0.20
        if "?" in candidate.opening_text:
            return 0.90
        return 0.65 if len(opening_tokens) >= 4 else 0.45

    def _intro_outro_penalty(
        self, candidate: IntervalCandidate, opening_tokens: list[str], episode_duration_ms: int
    ) -> float:
        score = 0.0
        token_set = set(opening_tokens)
        if candidate.start_ms < min(120_000, int(episode_duration_ms * 0.16)):
            score += 0.85
        if candidate.end_ms > max(episode_duration_ms - 75_000, int(episode_duration_ms * 0.88)):
            score += 0.65
        if token_set & self.CTA_MARKERS:
            score += 0.35
        if token_set & self.OUTRO_MARKERS:
            score += 0.35
        return min(1.0, round(score, 4))

    def _cta_penalty(self, tokens: list[str]) -> float:
        return min(1.0, round(self._token_density(tokens, self.CTA_MARKERS), 4))

    def _genericity_penalty(self, tokens: list[str], word_count: int) -> float:
        if not tokens:
            return 1.0
        useful_terms = self.HOOK_MARKERS | self.CONTRAST_MARKERS | self.UTILITY_MARKERS | self.EMOTIONAL_MARKERS
        if set(tokens) & useful_terms:
            return 0.0
        return 0.5 if word_count < 22 else 0.25

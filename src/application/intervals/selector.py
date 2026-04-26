from src.application.intervals.models import ScoredIntervalCandidate
from src.domain.text_utils import normalize_token


class DiversityAwareIntervalSelector:
    DEFAULT_TARGET_COUNT = 11
    DEFAULT_MINIMUM_SCORE = 0.28
    DEFAULT_MAX_OVERLAP_RATIO = 0.60

    def __init__(
        self,
        target_count: int | None = None,
        minimum_score: float | None = None,
        max_overlap_ratio: float | None = None,
    ):
        self.target_count = self.DEFAULT_TARGET_COUNT if target_count is None else target_count
        self.minimum_score = self.DEFAULT_MINIMUM_SCORE if minimum_score is None else minimum_score
        self.max_overlap_ratio = self.DEFAULT_MAX_OVERLAP_RATIO if max_overlap_ratio is None else max_overlap_ratio

    def select(self, candidates: list[ScoredIntervalCandidate]) -> list[ScoredIntervalCandidate]:
        selected: list[ScoredIntervalCandidate] = []
        ranked_candidates = sorted(candidates, key=lambda item: item.total_score, reverse=True)

        for candidate in ranked_candidates:
            if candidate.total_score < self.minimum_score:
                continue
            if any(self._overlap_ratio(candidate, chosen) > self.max_overlap_ratio for chosen in selected):
                continue
            if any(self._opening_similarity(candidate, chosen) >= 0.80 for chosen in selected):
                continue
            selected.append(candidate)
            if len(selected) >= self.target_count:
                break

        return selected

    @staticmethod
    def _overlap_ratio(first: ScoredIntervalCandidate, second: ScoredIntervalCandidate) -> float:
        overlap_start = max(first.candidate.start_ms, second.candidate.start_ms)
        overlap_end = min(first.candidate.end_ms, second.candidate.end_ms)
        overlap_ms = max(0, overlap_end - overlap_start)
        if overlap_ms == 0:
            return 0.0
        shortest_duration = min(first.candidate.duration_ms, second.candidate.duration_ms)
        return overlap_ms / shortest_duration if shortest_duration else 0.0

    @staticmethod
    def _opening_similarity(first: ScoredIntervalCandidate, second: ScoredIntervalCandidate) -> float:
        first_tokens = {
            token for token in (normalize_token(part) for part in first.candidate.opening_text.split()) if token
        }
        second_tokens = {
            token for token in (normalize_token(part) for part in second.candidate.opening_text.split()) if token
        }
        if not first_tokens or not second_tokens:
            return 0.0
        shared = len(first_tokens & second_tokens)
        total = len(first_tokens | second_tokens)
        return shared / total if total else 0.0

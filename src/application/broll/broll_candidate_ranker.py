from dataclasses import replace
from urllib.parse import urlparse

from src.domain.broll_models import BrollCandidate, ImpactBeat
from src.domain.text_utils import normalize_token


class BrollCandidateRanker:
    def rank(
        self,
        beat: ImpactBeat,
        queries: tuple[str, ...],
        candidates: list[BrollCandidate],
    ) -> list[BrollCandidate]:
        ranked_candidates = [self._score_candidate(beat, queries, candidate) for candidate in candidates]
        return sorted(ranked_candidates, key=lambda candidate: candidate.total_score, reverse=True)

    def _score_candidate(
        self,
        beat: ImpactBeat,
        queries: tuple[str, ...],
        candidate: BrollCandidate,
    ) -> BrollCandidate:
        semantic_match = self._semantic_match(beat, queries, candidate)
        visual_fit = self._visual_fit(candidate)
        duration_fit = self._duration_fit(beat, candidate)
        orientation_fit = self._orientation_fit(candidate)
        diversity_bonus = 0.10 if candidate.tags else 0.05
        technical_quality = self._technical_quality(candidate)
        source_preference_bonus = self._source_preference_bonus(candidate)
        total_score = round(
            (
                0.40 * semantic_match
                + 0.20 * visual_fit
                + 0.15 * duration_fit
                + 0.10 * orientation_fit
                + 0.10 * diversity_bonus
                + 0.05 * technical_quality
                + source_preference_bonus
            ),
            4,
        )
        return replace(
            candidate,
            semantic_match=semantic_match,
            visual_fit=visual_fit,
            duration_fit=duration_fit,
            orientation_fit=orientation_fit,
            diversity_bonus=diversity_bonus,
            technical_quality=technical_quality,
            total_score=total_score,
        )

    @staticmethod
    def _semantic_match(
        beat: ImpactBeat,
        queries: tuple[str, ...],
        candidate: BrollCandidate,
    ) -> float:
        reference_tokens = {normalize_token(token) for token in beat.text.split() if normalize_token(token)}
        for query in queries:
            reference_tokens.update(normalize_token(token) for token in query.split() if normalize_token(token))

        candidate_text = " ".join(
            [
                candidate.title,
                " ".join(candidate.tags),
                urlparse(candidate.asset_url).path.rsplit("/", 1)[-1],
            ]
        )
        candidate_tokens = {
            normalize_token(token)
            for token in candidate_text.replace("-", " ").replace("_", " ").split()
            if normalize_token(token)
        }
        if not reference_tokens or not candidate_tokens:
            return 0.0

        overlap = len(reference_tokens & candidate_tokens)
        return round(min(1.0, overlap / max(1, min(len(reference_tokens), 4))), 4)

    @staticmethod
    def _visual_fit(candidate: BrollCandidate) -> float:
        base_score = 0.80 if candidate.asset_type == "video" else 0.60
        if candidate.orientation == "vertical":
            base_score += 0.15
        elif candidate.orientation == "square":
            base_score += 0.08
        elif candidate.orientation == "landscape":
            base_score += 0.02
        return round(min(1.0, base_score), 4)

    @staticmethod
    def _duration_fit(beat: ImpactBeat, candidate: BrollCandidate) -> float:
        if candidate.asset_type == "image":
            return 0.70
        if candidate.duration_ms <= 0:
            return 0.65 if candidate.local_path else 0.0
        if candidate.duration_ms >= beat.duration_ms:
            return 1.0

        coverage_ratio = candidate.duration_ms / max(beat.duration_ms, 1)
        return round(max(0.0, min(1.0, coverage_ratio)), 4)

    @staticmethod
    def _orientation_fit(candidate: BrollCandidate) -> float:
        return {
            "vertical": 1.0,
            "square": 0.75,
            "landscape": 0.55,
        }.get(candidate.orientation, 0.40)

    @staticmethod
    def _technical_quality(candidate: BrollCandidate) -> float:
        if candidate.width <= 0 or candidate.height <= 0:
            return 0.40 if candidate.local_path else 0.25

        area = candidate.width * candidate.height
        if area >= 1920 * 1080:
            return 1.0
        if area >= 1280 * 720:
            return 0.80
        if area >= 720 * 720:
            return 0.60
        return 0.40

    @staticmethod
    def _source_preference_bonus(candidate: BrollCandidate) -> float:
        if candidate.provider == "pexels" and candidate.orientation == "vertical":
            return 0.03
        if candidate.provider == "pixabay" and candidate.orientation == "landscape":
            return -0.01
        return 0.0

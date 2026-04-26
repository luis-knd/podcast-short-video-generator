from src.application.intervals import DiversityAwareIntervalSelector, IntervalCandidateGenerator, IntervalViralityScorer
from src.domain.ports import ISubtitleIntervalGenerator
from src.infrastructure.subtitles.parser import SubtitleParser


class ViralSubtitleIntervalGenerator(ISubtitleIntervalGenerator):
    def __init__(
        self,
        subtitle_parser: SubtitleParser | None = None,
        candidate_generator: IntervalCandidateGenerator | None = None,
        virality_scorer: IntervalViralityScorer | None = None,
        selector: DiversityAwareIntervalSelector | None = None,
    ):
        self.subtitle_parser = subtitle_parser or SubtitleParser()
        self.candidate_generator = candidate_generator or IntervalCandidateGenerator()
        self.virality_scorer = virality_scorer or IntervalViralityScorer()
        self.selector = selector or DiversityAwareIntervalSelector()

    def generate(self, subtitles_filepath: str) -> list[dict[str, str]]:
        cues = self.subtitle_parser.parse(subtitles_filepath)
        if not cues:
            return []

        episode_duration_ms = max(cue.end_ms for cue in cues)
        candidates = self.candidate_generator.generate(cues)
        scored_candidates = [
            self.virality_scorer.score(candidate, episode_duration_ms=episode_duration_ms) for candidate in candidates
        ]
        selected_candidates = self.selector.select(scored_candidates)
        if not selected_candidates:
            selected_candidates = sorted(scored_candidates, key=lambda item: item.total_score, reverse=True)[:3]

        return [
            self._serialize_interval(candidate.candidate.start_ms, candidate.candidate.end_ms)
            for candidate in sorted(selected_candidates, key=lambda item: item.candidate.start_ms)
        ]

    def _serialize_interval(self, start_ms: int, end_ms: int) -> dict[str, str]:
        return {
            "time": f"{self._format_ms(start_ms)} - {self._format_ms(end_ms)}",
        }

    @staticmethod
    def _format_ms(total_ms: int) -> str:
        hours, remaining_ms = divmod(total_ms, 3_600_000)
        minutes, remaining_ms = divmod(remaining_ms, 60_000)
        seconds, milliseconds = divmod(remaining_ms, 1_000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


class HeuristicSubtitleIntervalGenerator(ViralSubtitleIntervalGenerator):
    pass

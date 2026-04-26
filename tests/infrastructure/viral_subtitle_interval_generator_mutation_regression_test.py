from dataclasses import dataclass
from typing import cast

from src.application.intervals import DiversityAwareIntervalSelector, IntervalCandidateGenerator, IntervalViralityScorer
from src.application.intervals.models import IntervalCandidate, ScoredIntervalCandidate, ViralityScoreBreakdown
from src.infrastructure.subtitles.interval_generator import ViralSubtitleIntervalGenerator
from src.infrastructure.subtitles.parser import SubtitleParser


@dataclass(frozen=True)
class _Candidate:
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class _SelectedCandidate:
    candidate: _Candidate
    total_score: float


class _ParserStub:
    def __init__(self, cues):
        self.cues = cues

    def parse(self, subtitles_filepath: str):
        del subtitles_filepath
        return self.cues


class _CandidateGeneratorStub:
    def __init__(self, candidates):
        self.candidates = candidates

    def generate(self, cues):
        del cues
        return self.candidates


class _ScorerStub:
    def __init__(self, scored_candidates):
        self.scored_candidates = scored_candidates

    def score(self, candidate, episode_duration_ms: int):
        del episode_duration_ms
        return self.scored_candidates[candidate]


class _SelectorStub:
    def __init__(self, selected):
        self.selected = selected

    def select(self, scored_candidates):
        self.last_scored_candidates = scored_candidates
        return self.selected


def test_viral_subtitle_interval_generator_falls_back_to_top_scores_when_selector_returns_empty():
    cues = [
        type("Cue", (), {"end_ms": 60_000})(),
        type("Cue", (), {"end_ms": 90_000})(),
    ]
    candidate_a = IntervalCandidate(0, 20_000, ("cue-1",), "a", 10, 1, "open a", "close a")
    candidate_b = IntervalCandidate(20_000, 45_000, ("cue-2",), "b", 10, 1, "open b", "close b")
    candidate_c = IntervalCandidate(45_000, 70_000, ("cue-3",), "c", 10, 1, "open c", "close c")
    candidate_d = IntervalCandidate(70_000, 95_000, ("cue-4",), "d", 10, 1, "open d", "close d")
    scored = {
        candidate_a: ScoredIntervalCandidate(candidate_a, ViralityScoreBreakdown(*([0.0] * 10)), 0.4, ()),
        candidate_b: ScoredIntervalCandidate(candidate_b, ViralityScoreBreakdown(*([0.0] * 10)), 0.9, ()),
        candidate_c: ScoredIntervalCandidate(candidate_c, ViralityScoreBreakdown(*([0.0] * 10)), 0.7, ()),
        candidate_d: ScoredIntervalCandidate(candidate_d, ViralityScoreBreakdown(*([0.0] * 10)), 0.8, ()),
    }
    generator = ViralSubtitleIntervalGenerator(
        subtitle_parser=cast(SubtitleParser, _ParserStub(cues)),
        candidate_generator=cast(
            IntervalCandidateGenerator,
            _CandidateGeneratorStub([candidate_a, candidate_b, candidate_c, candidate_d]),
        ),
        virality_scorer=cast(IntervalViralityScorer, _ScorerStub(scored)),
        selector=cast(DiversityAwareIntervalSelector, _SelectorStub([])),
    )

    intervals = generator.generate("episode.srt")

    assert intervals == [
        {"time": "00:00:20,000 - 00:00:45,000"},
        {"time": "00:00:45,000 - 00:01:10,000"},
        {"time": "00:01:10,000 - 00:01:35,000"},
    ]

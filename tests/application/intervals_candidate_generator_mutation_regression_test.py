from src.application.intervals.candidate_generator import IntervalCandidateGenerator
from src.domain.subtitle_models import SubtitleCue


def _cue(cue_id: str, start_ms: int, end_ms: int, text: str) -> SubtitleCue:
    return SubtitleCue(cue_id=cue_id, speaker="Speaker 1", text=text, start_ms=start_ms, end_ms=end_ms)


def test_interval_candidate_generator_defaults_and_ideal_window_boundaries_are_exact():
    generator = IntervalCandidateGenerator()

    assert generator.min_duration_ms == 18_000
    assert generator.ideal_duration_ms == 28_000
    assert generator.max_duration_ms == 34_000
    assert generator.max_gap_ms == 1_500
    assert generator._is_close_to_ideal(22_000) is True
    assert generator._is_close_to_ideal(34_000) is True
    assert generator._is_close_to_ideal(21_999) is False
    assert generator._is_close_to_ideal(34_001) is False


def test_interval_candidate_generator_gap_and_duration_boundaries_only_stop_after_crossing_limits():
    generator = IntervalCandidateGenerator(max_gap_ms=1_500, max_duration_ms=28_000)
    first = _cue("cue-1", 0, 10_000, "First line.")
    second = _cue("cue-2", 11_500, 20_000, "Second line.")
    third = _cue("cue-3", 20_000, 28_000, "Third line.")
    fourth = _cue("cue-4", 20_001, 28_001, "Fourth line.")

    assert generator._should_stop_window([], second) is False
    assert generator._should_stop_window([first], second) is False
    assert generator._should_stop_window([first], _cue("cue-x", 11_501, 20_000, "Gap too large.")) is True
    assert generator._window_exceeds_max_duration([first, third]) is False
    assert generator._window_exceeds_max_duration([first, fourth]) is True


def test_interval_candidate_generator_requires_boundary_or_ideal_window_until_the_last_cue():
    generator = IntervalCandidateGenerator(ideal_duration_ms=28_000)
    cues = [
        _cue("cue-1", 0, 8_000, "No punctuation here"),
        _cue("cue-2", 8_000, 16_000, "Still going without a stop"),
        _cue("cue-3", 16_000, 24_000, "Another unfinished thought"),
        _cue("cue-4", 24_000, 32_000, "Finally a full ending."),
    ]

    assert generator._should_keep_window(cues, 1, cues[1], cues[:2]) is False
    assert generator._should_keep_window(cues, 2, cues[2], cues[:3]) is True
    assert generator._should_keep_window(cues, 3, cues[3], cues) is True


def test_interval_candidate_generator_does_not_append_duplicate_ranges_twice():
    generator = IntervalCandidateGenerator()
    cues = [_cue("cue-1", 0, 10_000, "Hello."), _cue("cue-2", 10_000, 20_000, "Bye.")]
    window = cues[:]
    candidates = []
    seen_ranges: set[tuple[int, int]] = set()

    generator._append_candidate_if_new(window, candidates, seen_ranges)
    generator._append_candidate_if_new(window, candidates, seen_ranges)

    assert len(candidates) == 1
    assert seen_ranges == {(0, 20_000)}


def test_interval_candidate_generator_collect_candidates_keeps_scanning_after_non_ideal_non_boundary_windows():
    generator = IntervalCandidateGenerator(min_duration_ms=18_000, ideal_duration_ms=40_000, max_duration_ms=34_000)
    cues = [
        _cue("cue-1", 0, 9_000, "Open thought without punctuation"),
        _cue("cue-2", 9_000, 18_000, "Still building the same idea"),
        _cue("cue-3", 18_000, 27_000, "Now we finally land the full point."),
    ]
    candidates = []
    seen_ranges: set[tuple[int, int]] = set()

    generator._collect_candidates_from_start(cues, 0, candidates, seen_ranges)

    assert [candidate.cue_ids for candidate in candidates] == [("cue-1", "cue-2", "cue-3")]

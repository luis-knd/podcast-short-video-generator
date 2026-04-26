from src.application.intervals.candidate_generator import IntervalCandidateGenerator
from src.domain.subtitle_models import SubtitleCue


def _build_cue(cue_id: str, start_ms: int, end_ms: int, text: str) -> SubtitleCue:
    return SubtitleCue(
        cue_id=cue_id,
        speaker="Speaker 1",
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
    )


def test_interval_candidate_generator_creates_overlapping_deterministic_candidates():
    cues = [
        _build_cue("cue-1", 0, 7000, "Why does this phrase sound rude at work?"),
        _build_cue("cue-2", 7000, 14000, "Because the lyric is dramatic but real life is different."),
        _build_cue("cue-3", 14000, 21000, "Here is the safe swap you can use instead."),
        _build_cue("cue-4", 21000, 28000, "Imagine saying the original line in a job interview."),
        _build_cue("cue-5", 28000, 35000, "That would sound intense, not professional at all."),
    ]

    generator = IntervalCandidateGenerator(min_duration_ms=18_000, ideal_duration_ms=26_000, max_duration_ms=34_000)

    first_run = generator.generate(cues)
    second_run = generator.generate(cues)

    assert first_run == second_run
    assert len(first_run) >= 4
    assert all(18_000 <= candidate.duration_ms <= 34_000 for candidate in first_run)
    assert any(first.start_ms < second.start_ms < first.end_ms for first, second in zip(first_run, first_run[1:]))


def test_interval_candidate_generator_stops_the_window_when_gap_exceeds_limit():
    cues = [
        _build_cue("cue-1", 0, 9000, "Why does this expression sound rude?"),
        _build_cue("cue-2", 9000, 18000, "Because the literal meaning is too strong."),
        _build_cue("cue-3", 20500, 29500, "Here is a safer option you can use instead."),
    ]

    generator = IntervalCandidateGenerator(min_duration_ms=18_000, max_gap_ms=1_500)

    candidates = generator.generate(cues)

    assert [candidate.cue_ids for candidate in candidates] == [("cue-1", "cue-2")]


def test_interval_candidate_generator_keeps_the_last_window_even_without_boundary_when_duration_is_valid():
    cues = [
        _build_cue("cue-1", 0, 7000, "This opening has no punctuation"),
        _build_cue("cue-2", 7000, 14000, "but it keeps building the same idea"),
        _build_cue("cue-3", 14000, 21000, "and the clip should still be considered"),
    ]

    generator = IntervalCandidateGenerator(min_duration_ms=18_000, ideal_duration_ms=40_000, max_duration_ms=30_000)

    candidates = generator.generate(cues)

    assert candidates == [generator._build_candidate(cues)]


def test_interval_candidate_generator_discards_windows_that_exceed_max_duration():
    cues = [
        _build_cue("cue-1", 0, 10000, "Why does this phrase sound natural here?"),
        _build_cue("cue-2", 10000, 20000, "Because the context makes the register softer."),
        _build_cue("cue-3", 20000, 30000, "This third cue would push the window over the limit."),
    ]

    generator = IntervalCandidateGenerator(min_duration_ms=18_000, ideal_duration_ms=40_000, max_duration_ms=25_000)

    candidates = generator.generate(cues)

    assert [candidate.cue_ids for candidate in candidates] == [("cue-1", "cue-2"), ("cue-2", "cue-3")]

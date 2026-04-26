from src.application.intervals.models import IntervalCandidate
from src.domain.subtitle_models import SubtitleCue


class IntervalCandidateGenerator:
    DEFAULT_MIN_DURATION_MS = 18_000
    DEFAULT_IDEAL_DURATION_MS = 28_000
    DEFAULT_MAX_DURATION_MS = 34_000
    DEFAULT_MAX_GAP_MS = 1_500

    def __init__(
        self,
        min_duration_ms: int | None = None,
        ideal_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        max_gap_ms: int | None = None,
    ):
        self.min_duration_ms = self.DEFAULT_MIN_DURATION_MS if min_duration_ms is None else min_duration_ms
        self.ideal_duration_ms = self.DEFAULT_IDEAL_DURATION_MS if ideal_duration_ms is None else ideal_duration_ms
        self.max_duration_ms = self.DEFAULT_MAX_DURATION_MS if max_duration_ms is None else max_duration_ms
        self.max_gap_ms = self.DEFAULT_MAX_GAP_MS if max_gap_ms is None else max_gap_ms

    @staticmethod
    def _build_candidate(cues: list[SubtitleCue]) -> IntervalCandidate:
        text = " ".join(cue.text.strip() for cue in cues)
        return IntervalCandidate(
            start_ms=cues[0].start_ms,
            end_ms=cues[-1].end_ms,
            cue_ids=tuple(cue.cue_id for cue in cues),
            text=text,
            word_count=sum(len(cue.words) for cue in cues),
            speaker_count=len({cue.speaker for cue in cues}),
            opening_text=cues[0].text.strip(),
            closing_text=cues[-1].text.strip(),
        )

    @staticmethod
    def _gap_ms(current_cue: SubtitleCue, next_cue: SubtitleCue) -> int:
        return max(0, next_cue.start_ms - current_cue.end_ms)

    @staticmethod
    def _has_boundary(text: str) -> bool:
        return text.rstrip().endswith((".", "!", "?", ":", ";"))

    @staticmethod
    def _window_duration_ms(window_cues: list[SubtitleCue]) -> int:
        return window_cues[-1].end_ms - window_cues[0].start_ms

    @staticmethod
    def _next_cue(cues: list[SubtitleCue], current_index: int) -> SubtitleCue | None:
        if current_index + 1 >= len(cues):
            return None
        return cues[current_index + 1]

    def generate(self, cues: list[SubtitleCue]) -> list[IntervalCandidate]:
        candidates: list[IntervalCandidate] = []
        seen_ranges: set[tuple[int, int]] = set()

        for start_index in range(len(cues)):
            self._collect_candidates_from_start(cues, start_index, candidates, seen_ranges)

        return candidates

    def _collect_candidates_from_start(
        self,
        cues: list[SubtitleCue],
        start_index: int,
        candidates: list[IntervalCandidate],
        seen_ranges: set[tuple[int, int]],
    ) -> None:
        window_cues: list[SubtitleCue] = []
        for index in range(start_index, len(cues)):
            cue = cues[index]
            if self._should_stop_window(window_cues, cue):
                return

            window_cues.append(cue)
            if self._window_exceeds_max_duration(window_cues):
                return
            if not self._window_reached_minimum_duration(window_cues):
                continue
            if not self._should_keep_window(cues, index, cue, window_cues):
                continue

            self._append_candidate_if_new(window_cues, candidates, seen_ranges)

    def _should_stop_window(self, window_cues: list[SubtitleCue], cue: SubtitleCue) -> bool:
        if not window_cues:
            return False
        return self._gap_ms(window_cues[-1], cue) > self.max_gap_ms

    def _window_exceeds_max_duration(self, window_cues: list[SubtitleCue]) -> bool:
        return self._window_duration_ms(window_cues) > self.max_duration_ms

    def _window_reached_minimum_duration(self, window_cues: list[SubtitleCue]) -> bool:
        return self._window_duration_ms(window_cues) >= self.min_duration_ms

    def _should_keep_window(
        self,
        cues: list[SubtitleCue],
        current_index: int,
        cue: SubtitleCue,
        window_cues: list[SubtitleCue],
    ) -> bool:
        duration_ms = self._window_duration_ms(window_cues)
        next_cue = self._next_cue(cues, current_index)
        return self._has_boundary(cue.text) or self._is_close_to_ideal(duration_ms) or next_cue is None

    def _append_candidate_if_new(
        self,
        window_cues: list[SubtitleCue],
        candidates: list[IntervalCandidate],
        seen_ranges: set[tuple[int, int]],
    ) -> None:
        candidate = self._build_candidate(window_cues)
        candidate_range = (candidate.start_ms, candidate.end_ms)
        if candidate_range in seen_ranges:
            return
        seen_ranges.add(candidate_range)
        candidates.append(candidate)

    def _is_close_to_ideal(self, duration_ms: int) -> bool:
        return abs(duration_ms - self.ideal_duration_ms) <= 6_000

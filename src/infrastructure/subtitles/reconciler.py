from difflib import SequenceMatcher

from src.domain.subtitle_models import AlignedWord, ReconciledCue, ReconciledWord, SubtitleCue
from src.infrastructure.subtitles.approximate_aligner import ApproximateWordAligner
from src.infrastructure.subtitles.normalization import normalize_token


class TranscriptReconciler:
    version = "v1"

    def __init__(
        self,
        match_window_ms: int = 500,
        minimum_match_ratio: float = 0.6,
        fuzzy_threshold: float = 0.86,
    ):
        self.match_window_ms = match_window_ms
        self.minimum_match_ratio = minimum_match_ratio
        self.fuzzy_threshold = fuzzy_threshold
        self.approximate_aligner = ApproximateWordAligner()

    def reconcile(
        self, cues: list[SubtitleCue], aligned_words: list[AlignedWord]
    ) -> tuple[list[ReconciledCue], dict[str, object]]:
        reconciled_cues: list[ReconciledCue] = []
        total_words = 0
        matched_words = 0
        exact_matches = 0
        fallback_cues = 0

        for cue in cues:
            expected_words = list(cue.words)
            total_words += len(expected_words)
            candidates = self._candidate_words_for_cue(cue, aligned_words)
            reconciled_cue, cue_stats = self._reconcile_cue(cue, candidates)
            reconciled_cues.append(reconciled_cue)
            matched_words += cue_stats["matched_words"]
            exact_matches += cue_stats["exact_matches"]
            if reconciled_cue.timing_mode == "approximate":
                fallback_cues += 1

        total_cues = len(cues)
        quality = {
            "global_score": self._compute_quality(matched_words, exact_matches, total_words),
            "matched_word_ratio": matched_words / total_words if total_words else 0.0,
            "exact_match_ratio": exact_matches / total_words if total_words else 0.0,
            "fallback_cue_ratio": fallback_cues / total_cues if total_cues else 0.0,
        }
        return reconciled_cues, quality

    def _candidate_words_for_cue(self, cue: SubtitleCue, aligned_words: list[AlignedWord]) -> list[AlignedWord]:
        start_limit = cue.start_ms - self.match_window_ms
        end_limit = cue.end_ms + self.match_window_ms
        return [word for word in aligned_words if word.end_ms >= start_limit and word.start_ms <= end_limit]

    def _reconcile_cue(self, cue: SubtitleCue, candidates: list[AlignedWord]) -> tuple[ReconciledCue, dict[str, int]]:
        expected_words = list(cue.words)
        if not expected_words:
            return self._approximate_cue(cue), {
                "matched_words": 0,
                "exact_matches": 0,
            }

        matches: list[tuple[int, AlignedWord, str] | None] = [None] * len(expected_words)
        cursor = 0
        matched_words = 0
        exact_matches = 0

        for word_index, display_word in enumerate(expected_words):
            normalized_word = normalize_token(display_word)
            if not normalized_word:
                continue

            matched_index, match_method = self._find_candidate_match(normalized_word, candidates, cursor)
            if matched_index is None:
                continue

            matches[word_index] = (
                matched_index,
                candidates[matched_index],
                match_method,
            )
            matched_words += 1
            exact_matches += int(match_method == "exact_normalized")
            cursor = matched_index + 1

        expected_normalized_words = [
            normalize_token(display_word) for display_word in expected_words if normalize_token(display_word)
        ]
        match_ratio = matched_words / len(expected_normalized_words) if expected_normalized_words else 0.0
        if match_ratio < self.minimum_match_ratio:
            return self._approximate_cue(cue), {
                "matched_words": matched_words,
                "exact_matches": exact_matches,
            }

        reconciled_words = self._build_reconciled_words(cue, expected_words, matches)
        quality_score = self._compute_quality(matched_words, exact_matches, len(expected_words))
        return (
            ReconciledCue(
                cue_id=cue.cue_id,
                speaker=cue.speaker,
                original_text=cue.text,
                source_cue_start_ms=cue.start_ms,
                source_cue_end_ms=cue.end_ms,
                timing_mode="reconciled_asr",
                quality_score=quality_score,
                words=tuple(reconciled_words),
            ),
            {"matched_words": matched_words, "exact_matches": exact_matches},
        )

    def _find_candidate_match(
        self,
        normalized_word: str,
        candidates: list[AlignedWord],
        cursor: int,
    ) -> tuple[int | None, str]:
        for candidate_index in range(cursor, len(candidates)):
            if candidates[candidate_index].normalized_text == normalized_word:
                return candidate_index, "exact_normalized"

        for candidate_index in range(cursor, len(candidates)):
            ratio = SequenceMatcher(
                a=normalized_word,
                b=candidates[candidate_index].normalized_text,
            ).ratio()
            if ratio >= self.fuzzy_threshold:
                return candidate_index, "fuzzy_normalized"

        return None, "unmatched"

    def _build_reconciled_words(
        self,
        cue: SubtitleCue,
        expected_words: list[str],
        matches: list[tuple[int, AlignedWord, str] | None],
    ) -> list[ReconciledWord]:
        reconciled_words: list[ReconciledWord | None] = [None] * len(expected_words)

        for word_index, match in enumerate(matches):
            if match is None:
                continue

            _, matched_word, match_method = match
            reconciled_words[word_index] = ReconciledWord(
                display_text=expected_words[word_index],
                start_ms=matched_word.start_ms,
                end_ms=matched_word.end_ms,
                confidence=matched_word.confidence,
                source="reconciled",
                match_method=match_method,
                fallback_used=False,
            )

        word_index = 0
        while word_index < len(reconciled_words):
            if reconciled_words[word_index] is not None:
                word_index += 1
                continue

            prev_word = self._previous_resolved_word(reconciled_words, word_index)
            next_word = self._next_resolved_word(reconciled_words, word_index)
            span_start, span_end = self._interpolation_span(cue, prev_word, next_word)

            run_start = word_index
            run_end = word_index
            while run_end + 1 < len(reconciled_words) and reconciled_words[run_end + 1] is None:
                run_end += 1

            run_length = run_end - run_start + 1
            segment_duration = max(span_end - span_start, run_length)
            time_per_word = max(segment_duration // run_length, 1)

            for offset in range(run_length):
                current_index = run_start + offset
                word_start = span_start + offset * time_per_word
                word_end = span_start + (offset + 1) * time_per_word
                if offset == run_length - 1:
                    word_end = max(word_end, span_end)
                if word_end <= word_start:
                    word_end = word_start + 1

                reconciled_words[current_index] = ReconciledWord(
                    display_text=expected_words[current_index],
                    start_ms=word_start,
                    end_ms=word_end,
                    confidence=0.0,
                    source="interpolated",
                    match_method="interpolated",
                    fallback_used=False,
                )

            word_index = run_end + 1

        return [word for word in reconciled_words if word is not None]

    @staticmethod
    def _previous_resolved_word(
        reconciled_words: list[ReconciledWord | None], word_index: int
    ) -> ReconciledWord | None:
        for current_index in range(word_index - 1, -1, -1):
            if reconciled_words[current_index] is not None:
                return reconciled_words[current_index]
        return None

    @staticmethod
    def _next_resolved_word(reconciled_words: list[ReconciledWord | None], word_index: int) -> ReconciledWord | None:
        for current_index in range(word_index + 1, len(reconciled_words)):
            if reconciled_words[current_index] is not None:
                return reconciled_words[current_index]
        return None

    @staticmethod
    def _interpolation_span(
        cue: SubtitleCue,
        previous_word: ReconciledWord | None,
        next_word: ReconciledWord | None,
    ) -> tuple[int, int]:
        span_start = cue.start_ms if previous_word is None else previous_word.end_ms
        span_end = cue.end_ms if next_word is None else next_word.start_ms
        if span_end <= span_start:
            span_end = span_start + 1
        return span_start, span_end

    def _approximate_cue(self, cue: SubtitleCue) -> ReconciledCue:
        approximate_cues = self.approximate_aligner.build_cues([cue])
        if approximate_cues:
            return approximate_cues[0]

        return ReconciledCue(
            cue_id=cue.cue_id,
            speaker=cue.speaker,
            original_text=cue.text,
            source_cue_start_ms=cue.start_ms,
            source_cue_end_ms=cue.end_ms,
            timing_mode="approximate",
            quality_score=0.0,
            words=(),
        )

    @staticmethod
    def _compute_quality(
        matched_words: int,
        exact_matches: int,
        total_words: int,
    ) -> float:
        if total_words == 0:
            return 0.0

        matched_ratio = matched_words / total_words
        exact_ratio = exact_matches / total_words
        timing_coverage_ratio = 1.0 if matched_words else 0.0
        return round(
            0.5 * matched_ratio + 0.3 * exact_ratio + 0.2 * timing_coverage_ratio,
            4,
        )

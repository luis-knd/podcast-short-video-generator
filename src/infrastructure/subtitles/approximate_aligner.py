from src.domain.subtitle_models import ReconciledCue, ReconciledWord, SubtitleCue


class ApproximateWordAligner:
    @staticmethod
    def calculate_chunk_times(chunks: list[str], start_ms: int, end_ms: int) -> list[dict[str, int | str]]:
        total_duration = end_ms - start_ms
        total_words = sum(len(chunk.split()) for chunk in chunks)

        if total_words == 0:
            return []

        time_per_word = total_duration / total_words
        current_time = start_ms
        timed_chunks: list[dict[str, int | str]] = []

        for chunk in chunks:
            word_count = len(chunk.split())
            chunk_duration = int(word_count * time_per_word)
            timed_chunks.append(
                {
                    "text": chunk,
                    "start": int(current_time),
                    "end": int(current_time + chunk_duration),
                }
            )
            current_time += chunk_duration

        return timed_chunks

    def build_cues(self, cues: list[SubtitleCue]) -> list[ReconciledCue]:
        reconciled_cues: list[ReconciledCue] = []

        for cue in cues:
            timed_words = self.calculate_chunk_times(list(cue.words), cue.start_ms, cue.end_ms)
            reconciled_words = tuple(
                ReconciledWord(
                    display_text=str(word_payload["text"]),
                    start_ms=int(word_payload["start"]),
                    end_ms=int(word_payload["end"]),
                    confidence=0.0,
                    source="approximate",
                    match_method="approximate",
                    fallback_used=True,
                )
                for word_payload in timed_words
            )

            if not reconciled_words:
                continue

            reconciled_cues.append(
                ReconciledCue(
                    cue_id=cue.cue_id,
                    speaker=cue.speaker,
                    original_text=cue.text,
                    source_cue_start_ms=cue.start_ms,
                    source_cue_end_ms=cue.end_ms,
                    timing_mode="approximate",
                    quality_score=0.0,
                    words=reconciled_words,
                )
            )

        return reconciled_cues

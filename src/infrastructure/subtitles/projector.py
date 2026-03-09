from src.domain.subtitle_models import ReconciledCue
from src.domain.value_objects import TimeInterval


class IntervalSubtitleProjector:
    @staticmethod
    def group_into_phrases(words: list[str], words_per_phrase: int = 4) -> list[list[str]]:
        return [words[index : index + words_per_phrase] for index in range(0, len(words), words_per_phrase)]

    def project(
        self,
        cues: list[ReconciledCue],
        interval: TimeInterval,
        words_per_phrase: int = 6,
    ) -> list[dict[str, object]]:
        interval_start_ms = int(interval.start_seconds * 1000)
        interval_end_ms = int(interval.end_seconds * 1000)
        interval_duration_ms = interval_end_ms - interval_start_ms
        segments: list[dict[str, object]] = []

        for cue in cues:
            if cue.end_ms <= interval_start_ms or cue.start_ms >= interval_end_ms:
                continue

            projected_words = []
            for word in cue.words:
                word_start = word.start_ms - interval_start_ms
                word_end = word.end_ms - interval_start_ms

                if word_end <= 0 or word_start >= interval_duration_ms:
                    continue

                projected_words.append(
                    {
                        "text": word.display_text,
                        "start": max(0, word_start),
                        "end": min(interval_duration_ms, word_end),
                    }
                )

            if not projected_words:
                continue

            valid_words = [word["text"] for word in projected_words]
            phrase_groups = self.group_into_phrases(valid_words, words_per_phrase=words_per_phrase)

            word_index = 0
            for phrase_words in phrase_groups:
                phrase_word_times = projected_words[word_index : word_index + len(phrase_words)]
                word_index += len(phrase_words)

                segments.append(
                    {
                        "speaker": cue.speaker,
                        "phrase_text": " ".join(phrase_words),
                        "start_ms": phrase_word_times[0]["start"],
                        "end_ms": phrase_word_times[-1]["end"],
                        "words": phrase_word_times,
                    }
                )

        return segments

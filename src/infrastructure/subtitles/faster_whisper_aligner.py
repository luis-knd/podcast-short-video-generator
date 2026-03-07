from datetime import UTC, datetime

from src.infrastructure.subtitles.normalization import normalize_token


class FasterWhisperWordAligner:
    aligner_name = "faster_whisper"

    def __init__(
        self,
        model_size: str = "base",
        compute_type: str = "int8",
        language: str | None = None,
        beam_size: int = 5,
        vad_filter: bool = True,
    ):
        self.model_size = model_size
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self._model = None

    def align(self, media_filepath: str) -> dict[str, object]:
        model = self._load_model()
        segments, info = model.transcribe(
            media_filepath,
            beam_size=self.beam_size,
            language=self.language,
            vad_filter=self.vad_filter,
            word_timestamps=True,
        )

        words: list[dict[str, object]] = []
        for segment in segments:
            segment_words = getattr(segment, "words", None) or []
            for word in segment_words:
                start = getattr(word, "start", None)
                end = getattr(word, "end", None)
                raw_text = (getattr(word, "word", "") or "").strip()

                if start is None or end is None or not raw_text:
                    continue

                start_ms = int(round(float(start) * 1000))
                end_ms = int(round(float(end) * 1000))
                if end_ms <= start_ms:
                    end_ms = start_ms + 1

                words.append(
                    {
                        "text": raw_text,
                        "normalized_text": normalize_token(raw_text),
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "confidence": float(getattr(word, "probability", 0.0) or 0.0),
                    }
                )

        return {
            "metadata": {
                "aligner": self.aligner_name,
                "model": self.model_size,
                "compute_type": self.compute_type,
                "language": self.language or getattr(info, "language", None),
                "generated_at": datetime.now(UTC).isoformat(),
            },
            "words": words,
        }

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size,
                compute_type=self.compute_type,
            )
        return self._model

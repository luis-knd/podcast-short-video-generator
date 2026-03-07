from typing import Any

# fmt: off
# isort: off
from src.domain.subtitle_models import (
    AlignedWord,
    ReconciledCue,
    ReconciledWord,
)
from src.domain.value_objects import TimeInterval
from src.infrastructure.config import ConfigManager
from src.infrastructure.subtitles import (
    AlignmentCache,
    ApproximateWordAligner,
    AssWriter,
    FasterWhisperWordAligner,
    IntervalSubtitleProjector,
    SubtitleParser,
    TranscriptReconciler,
)
# isort: on
# fmt: on


class SubtitleProcessor:
    def __init__(
        self,
        subtitle_parser: SubtitleParser | None = None,
        ass_writer: AssWriter | None = None,
        approximate_aligner: ApproximateWordAligner | None = None,
        projector: IntervalSubtitleProjector | None = None,
        reconciler: TranscriptReconciler | None = None,
    ):
        self.subtitle_parser = subtitle_parser or SubtitleParser()
        self.ass_writer = ass_writer or AssWriter()
        self.approximate_aligner = approximate_aligner or ApproximateWordAligner()
        self.projector = projector or IntervalSubtitleProjector()
        self.reconciler = reconciler or TranscriptReconciler()

    @staticmethod
    def _parse_time_to_ms(time_str: str) -> int:
        return SubtitleParser.parse_time_to_ms(time_str)

    @staticmethod
    def _format_ms_to_ass_time(ms: int) -> str:
        return AssWriter.format_ms_to_ass_time(ms)

    @staticmethod
    def _calculate_chunk_times(chunks: list[str], start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        return ApproximateWordAligner.calculate_chunk_times(chunks, start_ms, end_ms)

    @staticmethod
    def _get_text_width(text: str, font_size: int) -> int:
        return AssWriter.get_text_width(text, font_size)

    @staticmethod
    def _group_into_phrases(words: list[str], words_per_phrase: int = 4) -> list[list[str]]:
        return IntervalSubtitleProjector.group_into_phrases(words, words_per_phrase=words_per_phrase)

    def process_subtitles(
        self,
        srt_filepath: str,
        interval: TimeInterval,
        output_ass_filepath: str,
        media_filepath: str | None = None,
    ) -> list[dict[str, Any]]:
        cues = self.subtitle_parser.parse(srt_filepath)
        timed_cues = self._resolve_timed_cues(
            cues=cues,
            interval=interval,
            srt_filepath=srt_filepath,
            output_ass_filepath=output_ass_filepath,
            media_filepath=media_filepath,
        )
        segments = self.projector.project(timed_cues, interval, words_per_phrase=6)
        self._write_ass_file(segments, output_ass_filepath)
        return segments

    def _resolve_timed_cues(
        self,
        cues,
        interval: TimeInterval,
        srt_filepath: str,
        output_ass_filepath: str,
        media_filepath: str | None,
    ) -> list[ReconciledCue]:
        if not cues:
            return []

        if not self._should_use_alignment(media_filepath):
            return self._build_approximate_cues(cues, interval)

        cache = AlignmentCache.from_output_filepath(output_ass_filepath)
        aligner = self._build_word_aligner()
        if aligner is None:
            return self._build_approximate_cues(cues, interval)

        try:
            raw_key = cache.build_raw_key(
                media_filepath=media_filepath,
                aligner_name=aligner.aligner_name,
                model_name=aligner.model_size,
                compute_type=aligner.compute_type,
                language=aligner.language,
            )
            raw_payload = cache.load_raw(raw_key)
            if raw_payload is None:
                raw_payload = aligner.align(media_filepath)
                cache.save_raw(raw_key, raw_payload)

            aligned_words = self._deserialize_aligned_words(raw_payload.get("words", []))
            if not aligned_words:
                return self._build_approximate_cues(cues, interval)

            reconciled_key = cache.build_reconciled_key(
                subtitle_filepath=srt_filepath,
                raw_key=raw_key,
                reconciliation_version=self.reconciler.version,
            )
            reconciled_payload = cache.load_reconciled(reconciled_key)
            if reconciled_payload is None:
                reconciled_cues, quality = self.reconciler.reconcile(cues, aligned_words)
                reconciled_payload = {
                    "quality": quality,
                    "cues": [cue.to_dict() for cue in reconciled_cues],
                    "raw_key": raw_key,
                }
                cache.save_reconciled(reconciled_key, reconciled_payload)
            return self._deserialize_reconciled_cues(reconciled_payload.get("cues", []))
        except (
            AttributeError,
            ImportError,
            KeyError,
            OSError,
            RuntimeError,
            TypeError,
            ValueError,
        ):
            return self._build_approximate_cues(cues, interval)

    @staticmethod
    def _should_use_alignment(media_filepath: str | None) -> bool:
        if not media_filepath:
            return False

        config = ConfigManager()
        return bool(config.get_alignment_setting("enabled", True))

    @staticmethod
    def _build_word_aligner() -> FasterWhisperWordAligner | None:
        config = ConfigManager()
        backend = config.get_alignment_setting("backend", "faster_whisper")
        if backend != "faster_whisper":
            return None

        return FasterWhisperWordAligner(
            model_size=config.get_alignment_setting("model_size", "base"),
            compute_type=config.get_alignment_setting("compute_type", "int8"),
            language=config.get_alignment_setting("language", None),
            beam_size=config.get_alignment_setting("beam_size", 5),
            vad_filter=config.get_alignment_setting("vad_filter", True),
        )

    def _build_approximate_cues(self, cues, interval: TimeInterval) -> list[ReconciledCue]:
        reconciled_cues: list[ReconciledCue] = []
        interval_start_ms = int(interval.start_seconds * 1000)
        interval_end_ms = int(interval.end_seconds * 1000)
        for cue in cues:
            if cue.end_ms <= interval_start_ms or cue.start_ms >= interval_end_ms:
                continue

            timed_words = self._calculate_chunk_times(list(cue.words), cue.start_ms, cue.end_ms)
            if not timed_words:
                continue

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

    @staticmethod
    def _deserialize_aligned_words(payload: object) -> list[AlignedWord]:
        if not isinstance(payload, list):
            return []

        return [AlignedWord.from_dict(item) for item in payload if isinstance(item, dict)]

    @staticmethod
    def _deserialize_reconciled_cues(payload: object) -> list[ReconciledCue]:
        if not isinstance(payload, list):
            return []

        return [ReconciledCue.from_dict(item) for item in payload if isinstance(item, dict)]

    def _write_ass_file(self, segments: list[dict[str, Any]], output_filepath: str):
        self.ass_writer.write(
            segments,
            output_filepath,
            format_time=self._format_ms_to_ass_time,
            get_text_width=self._get_text_width,
        )

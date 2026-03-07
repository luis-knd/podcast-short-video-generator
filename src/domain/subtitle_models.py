from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleCue:
    cue_id: str
    speaker: str
    text: str
    start_ms: int
    end_ms: int

    @property
    def words(self) -> tuple[str, ...]:
        return tuple(self.text.split())


@dataclass(frozen=True)
class AlignedWord:
    text: str
    normalized_text: str
    start_ms: int
    end_ms: int
    confidence: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "text": self.text,
            "normalized_text": self.normalized_text,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AlignedWord":
        return cls(
            text=str(payload.get("text", "")),
            normalized_text=str(payload.get("normalized_text", "")),
            start_ms=int(payload.get("start_ms", 0)),
            end_ms=int(payload.get("end_ms", 0)),
            confidence=float(payload.get("confidence", 0.0)),
        )


@dataclass(frozen=True)
class ReconciledWord:
    display_text: str
    start_ms: int
    end_ms: int
    confidence: float
    source: str
    match_method: str
    fallback_used: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "display_text": self.display_text,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "confidence": self.confidence,
            "source": self.source,
            "match_method": self.match_method,
            "fallback_used": self.fallback_used,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ReconciledWord":
        return cls(
            display_text=str(payload.get("display_text", "")),
            start_ms=int(payload.get("start_ms", 0)),
            end_ms=int(payload.get("end_ms", 0)),
            confidence=float(payload.get("confidence", 0.0)),
            source=str(payload.get("source", "approximate")),
            match_method=str(payload.get("match_method", "approximate")),
            fallback_used=bool(payload.get("fallback_used", False)),
        )


@dataclass(frozen=True)
class ReconciledCue:
    cue_id: str
    speaker: str
    original_text: str
    source_cue_start_ms: int
    source_cue_end_ms: int
    timing_mode: str
    quality_score: float
    words: tuple[ReconciledWord, ...]

    @property
    def start_ms(self) -> int:
        if not self.words:
            return self.source_cue_start_ms
        return self.words[0].start_ms

    @property
    def end_ms(self) -> int:
        if not self.words:
            return self.source_cue_end_ms
        return self.words[-1].end_ms

    def to_dict(self) -> dict[str, object]:
        return {
            "cue_id": self.cue_id,
            "speaker": self.speaker,
            "original_text": self.original_text,
            "source_cue_start_ms": self.source_cue_start_ms,
            "source_cue_end_ms": self.source_cue_end_ms,
            "timing_mode": self.timing_mode,
            "quality_score": self.quality_score,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "words": [word.to_dict() for word in self.words],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ReconciledCue":
        words_payload = payload.get("words", [])
        if not isinstance(words_payload, list):
            words_payload = []

        return cls(
            cue_id=str(payload.get("cue_id", "")),
            speaker=str(payload.get("speaker", "Speaker Unknown")),
            original_text=str(payload.get("original_text", "")),
            source_cue_start_ms=int(payload.get("source_cue_start_ms", 0)),
            source_cue_end_ms=int(payload.get("source_cue_end_ms", 0)),
            timing_mode=str(payload.get("timing_mode", "approximate")),
            quality_score=float(payload.get("quality_score", 0.0)),
            words=tuple(
                ReconciledWord.from_dict(word_payload)
                for word_payload in words_payload
                if isinstance(word_payload, dict)
            ),
        )

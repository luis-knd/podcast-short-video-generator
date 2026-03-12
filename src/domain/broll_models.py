from dataclasses import dataclass


@dataclass(frozen=True)
class BeatScoreBreakdown:
    total: float
    visualizability: float
    emotional_load: float
    contrast: float
    narrative_turn: float
    verbal_force: float
    duration_fit: float
    timing_confidence: float
    semantic_salience: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "total": self.total,
            "visualizability": self.visualizability,
            "emotional_load": self.emotional_load,
            "contrast": self.contrast,
            "narrative_turn": self.narrative_turn,
            "verbal_force": self.verbal_force,
            "duration_fit": self.duration_fit,
            "timing_confidence": self.timing_confidence,
            "semantic_salience": self.semantic_salience,
        }


@dataclass(frozen=True)
class ImpactBeat:
    beat_id: str
    text: str
    start_ms: int
    end_ms: int
    duration_ms: int
    timing_mode: str
    word_confidence_avg: float
    cue_quality_score: float
    scores: BeatScoreBreakdown
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "beat_id": self.beat_id,
            "text": self.text,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "timing_mode": self.timing_mode,
            "word_confidence_avg": self.word_confidence_avg,
            "cue_quality_score": self.cue_quality_score,
            "scores": self.scores.to_dict(),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class BrollCandidate:
    candidate_id: str
    provider: str
    discovery_source: str
    asset_type: str
    asset_url: str
    local_path: str | None
    duration_ms: int
    width: int
    height: int
    orientation: str
    title: str = ""
    tags: tuple[str, ...] = ()
    semantic_match: float = 0.0
    visual_fit: float = 0.0
    duration_fit: float = 0.0
    orientation_fit: float = 0.0
    diversity_bonus: float = 0.0
    technical_quality: float = 0.0
    total_score: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "provider": self.provider,
            "discovery_source": self.discovery_source,
            "asset_type": self.asset_type,
            "asset_url": self.asset_url,
            "local_path": self.local_path,
            "duration_ms": self.duration_ms,
            "width": self.width,
            "height": self.height,
            "orientation": self.orientation,
            "title": self.title,
            "tags": list(self.tags),
            "semantic_match": self.semantic_match,
            "visual_fit": self.visual_fit,
            "duration_fit": self.duration_fit,
            "orientation_fit": self.orientation_fit,
            "diversity_bonus": self.diversity_bonus,
            "technical_quality": self.technical_quality,
            "total_score": self.total_score,
        }


@dataclass(frozen=True)
class BrollInsertion:
    insertion_id: str
    beat_id: str
    mode: str
    asset_provider: str
    asset_path: str
    start_ms: int
    end_ms: int
    source_beat_score: float
    candidate_score: float
    x: int
    y: int
    width: int
    height: int
    opacity: float
    asset_in_ms: int
    asset_out_ms: int
    subtitle_safe: bool = True
    discovery_source: str = ""
    anchor_text: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "insertion_id": self.insertion_id,
            "beat_id": self.beat_id,
            "mode": self.mode,
            "asset_provider": self.asset_provider,
            "asset_path": self.asset_path,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "source_beat_score": self.source_beat_score,
            "candidate_score": self.candidate_score,
            "placement": {
                "x": self.x,
                "y": self.y,
                "width": self.width,
                "height": self.height,
                "opacity": self.opacity,
            },
            "trim": {
                "asset_in_ms": self.asset_in_ms,
                "asset_out_ms": self.asset_out_ms,
            },
            "subtitle_safe": self.subtitle_safe,
            "discovery_source": self.discovery_source,
        }
        if self.anchor_text:
            payload["anchor_text"] = self.anchor_text
        return payload


@dataclass(frozen=True)
class BeatCandidateSelection:
    beat: ImpactBeat
    candidates: tuple[BrollCandidate, ...]
    forced_mode: str | None = None
    override_start_ms: int | None = None
    override_end_ms: int | None = None
    priority: int = 0
    anchor_text: str | None = None
    selection_source: str = "automatic"


@dataclass(frozen=True)
class SkippedBeat:
    beat_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "beat_id": self.beat_id,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ShortEditingPlan:
    short_id: str
    enabled: bool
    strategy_version: str
    insertions: tuple[BrollInsertion, ...]
    skipped_beats: tuple[SkippedBeat, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "short_id": self.short_id,
            "enabled": self.enabled,
            "strategy_version": self.strategy_version,
            "insertions": [item.to_dict() for item in self.insertions],
            "skipped_beats": [item.to_dict() for item in self.skipped_beats],
        }

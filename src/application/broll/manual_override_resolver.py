from pathlib import Path

from src.domain.broll_models import BeatCandidateSelection, BeatScoreBreakdown, BrollCandidate, ImpactBeat
from src.domain.manual_broll_overrides import ManualBrollOverride
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline
from src.domain.text_utils import normalize_token


class ManualBrollOverrideResolver:
    IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}

    def resolve(
        self,
        short_id: str,
        timeline: SubtitleTimeline,
        detected_beats: list[ImpactBeat],
        overrides: tuple[ManualBrollOverride, ...],
    ) -> tuple[BeatCandidateSelection, ...]:
        relevant_overrides = [override for override in overrides if override.active and override.short_id == short_id]
        if not relevant_overrides:
            return ()

        selections_by_key: dict[str, BeatCandidateSelection] = {}
        synthetic_index = 0
        for override in sorted(relevant_overrides, key=lambda item: item.priority, reverse=True):
            asset_path = Path(override.asset_path)
            if not asset_path.is_file():
                continue

            beat = self._match_detected_beat(override, detected_beats)
            if beat is None:
                synthetic_index += 1
                beat = self._build_synthetic_beat(override, timeline, synthetic_index)
            if beat is None:
                continue

            beat_key = beat.beat_id
            if beat_key in selections_by_key:
                continue

            selections_by_key[beat_key] = BeatCandidateSelection(
                beat=beat,
                candidates=(self._build_manual_candidate(override, asset_path),),
                forced_mode=override.mode,
                override_start_ms=override.start_ms,
                override_end_ms=override.end_ms,
                priority=override.priority,
                anchor_text=override.anchor_text,
                selection_source="manual_override",
            )

        return tuple(
            sorted(
                selections_by_key.values(),
                key=lambda selection: (-selection.priority, selection.beat.start_ms),
            )
        )

    def _match_detected_beat(
        self,
        override: ManualBrollOverride,
        detected_beats: list[ImpactBeat],
    ) -> ImpactBeat | None:
        normalized_anchor = self._normalize_text(override.anchor_text)
        matched_beats = [
            beat
            for beat in detected_beats
            if normalized_anchor and normalized_anchor in self._normalize_text(beat.text)
        ]
        if not matched_beats:
            return None
        return min(matched_beats, key=lambda beat: (beat.duration_ms, beat.start_ms))

    def _build_synthetic_beat(
        self,
        override: ManualBrollOverride,
        timeline: SubtitleTimeline,
        synthetic_index: int,
    ) -> ImpactBeat | None:
        anchor_tokens = self._anchor_tokens(override.anchor_text)
        if not anchor_tokens:
            return None

        for cue in timeline.cues:
            matched_words = self._match_cue_words(cue, anchor_tokens)
            if matched_words:
                return self._manual_beat_from_words(override, cue, matched_words, synthetic_index)
            if self._normalize_text(override.anchor_text) in self._normalize_text(cue.original_text):
                return self._manual_beat_from_cue(override, cue, synthetic_index)
        return None

    @staticmethod
    def _match_cue_words(cue: ProjectedCue, anchor_tokens: tuple[str, ...]) -> tuple[ProjectedWord, ...]:
        normalized_words = [normalize_token(word.text) for word in cue.words]
        window_size = len(anchor_tokens)
        for index in range(0, len(normalized_words) - window_size + 1):
            if tuple(normalized_words[index : index + window_size]) == anchor_tokens:
                return cue.words[index : index + window_size]
        return ()

    def _manual_beat_from_words(
        self,
        override: ManualBrollOverride,
        cue: ProjectedCue,
        matched_words: tuple[ProjectedWord, ...],
        synthetic_index: int,
    ) -> ImpactBeat:
        start_ms = matched_words[0].start_ms
        end_ms = matched_words[-1].end_ms
        average_confidence = sum(word.confidence for word in matched_words) / len(matched_words)
        return ImpactBeat(
            beat_id=f"manual-beat-{synthetic_index:04d}",
            text=" ".join(word.text for word in matched_words),
            start_ms=start_ms,
            end_ms=end_ms,
            duration_ms=max(0, end_ms - start_ms),
            timing_mode=cue.timing_mode,
            word_confidence_avg=average_confidence,
            cue_quality_score=cue.quality_score,
            scores=self._manual_scores(),
            reasons=("manual override anchor matched",),
        )

    def _manual_beat_from_cue(
        self,
        override: ManualBrollOverride,
        cue: ProjectedCue,
        synthetic_index: int,
    ) -> ImpactBeat:
        average_confidence = 0.0
        if cue.words:
            average_confidence = sum(word.confidence for word in cue.words) / len(cue.words)
        return ImpactBeat(
            beat_id=f"manual-beat-{synthetic_index:04d}",
            text=override.anchor_text,
            start_ms=cue.start_ms,
            end_ms=cue.end_ms,
            duration_ms=cue.duration_ms,
            timing_mode=cue.timing_mode,
            word_confidence_avg=average_confidence,
            cue_quality_score=cue.quality_score,
            scores=self._manual_scores(),
            reasons=("manual override cue matched",),
        )

    def _build_manual_candidate(self, override: ManualBrollOverride, asset_path: Path) -> BrollCandidate:
        asset_type = self._asset_type(asset_path)
        orientation = self._orientation(asset_path)
        return BrollCandidate(
            candidate_id=f"manual-{normalize_token(override.anchor_text).replace(' ', '-')}-{asset_path.stem}",
            provider="manual_override",
            discovery_source="manual_override",
            asset_type=asset_type,
            asset_url=str(asset_path),
            local_path=str(asset_path),
            duration_ms=0,
            width=1080 if asset_type == "image" else 0,
            height=1080 if asset_type == "image" else 0,
            orientation=orientation,
            title=asset_path.stem.replace("_", " ").replace("-", " "),
            tags=tuple(self._anchor_tokens(override.anchor_text)),
            semantic_match=1.0,
            visual_fit=1.0,
            duration_fit=1.0,
            orientation_fit=1.0 if orientation == "vertical" else 0.8,
            technical_quality=0.8,
            total_score=1.0,
        )

    @staticmethod
    def _manual_scores() -> BeatScoreBreakdown:
        return BeatScoreBreakdown(
            total=1.0,
            visualizability=1.0,
            emotional_load=1.0,
            contrast=1.0,
            narrative_turn=1.0,
            verbal_force=1.0,
            duration_fit=1.0,
            timing_confidence=1.0,
            semantic_salience=1.0,
        )

    def _orientation(self, asset_path: Path) -> str:
        normalized_name = normalize_token(asset_path.stem)
        if any(token in normalized_name for token in ("vertical", "portrait", "reel", "short", "9x16")):
            return "vertical"
        if asset_path.suffix.lower() in self.IMAGE_EXTENSIONS:
            return "square"
        return "unknown"

    def _asset_type(self, asset_path: Path) -> str:
        return "image" if asset_path.suffix.lower() in self.IMAGE_EXTENSIONS else "video"

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(ManualBrollOverrideResolver._anchor_tokens(text))

    @staticmethod
    def _anchor_tokens(text: str) -> tuple[str, ...]:
        return tuple(normalize_token(token) for token in text.split() if normalize_token(token))

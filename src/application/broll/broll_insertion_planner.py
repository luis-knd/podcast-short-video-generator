from math import ceil

from src.domain.broll_models import (
    BeatCandidateSelection,
    BrollCandidate,
    BrollInsertion,
    ImpactBeat,
    ShortEditingPlan,
    SkippedBeat,
)
from src.domain.subtitle_models import SubtitleTimeline


class BrollInsertionPlanner:
    def __init__(
        self,
        minimum_gap_ms: int = 4500,
        beat_score_threshold: float = 0.68,
        cutaway_score_threshold: float = 0.82,
        minimum_candidate_score: float = 0.55,
        overlay_top_y: int = 120,
        support_beat_score_threshold: float = 0.30,
        automatic_candidate_semantic_match_threshold: float = 0.30,
        support_candidate_semantic_match_threshold: float = 0.45,
    ):
        self.minimum_gap_ms = minimum_gap_ms
        self.beat_score_threshold = beat_score_threshold
        self.cutaway_score_threshold = cutaway_score_threshold
        self.minimum_candidate_score = minimum_candidate_score
        self.overlay_top_y = overlay_top_y
        self.support_beat_score_threshold = support_beat_score_threshold
        self.automatic_candidate_semantic_match_threshold = automatic_candidate_semantic_match_threshold
        self.support_candidate_semantic_match_threshold = support_candidate_semantic_match_threshold

    def plan(
        self,
        short_id: str,
        timeline: SubtitleTimeline,
        beat_candidates: list[BeatCandidateSelection],
        target_width: int,
        target_height: int,
    ) -> ShortEditingPlan:
        target_total_insertions = self._target_insertions_for_duration(timeline.duration_ms)
        manual_count = sum(1 for selection in beat_candidates if self._is_manual_selection(selection))
        max_insertions = max(target_total_insertions, manual_count)
        effective_gap_ms = self._dynamic_gap_ms(timeline.duration_ms, target_total_insertions)
        insertions: list[BrollInsertion] = []
        skipped_beats: list[SkippedBeat] = []
        used_asset_keys: set[str] = set()

        ordered_selections = sorted(
            beat_candidates,
            key=lambda selection: (
                0 if self._is_manual_selection(selection) else 1,
                -selection.priority,
                -selection.beat.scores.total,
                selection.beat.start_ms,
            ),
        )

        for selection in ordered_selections:
            beat = selection.beat
            if len(insertions) >= max_insertions:
                skipped_beats.append(SkippedBeat(beat_id=beat.beat_id, reason="maximum insertions reached"))
                continue
            candidate = self._best_candidate(
                beat=beat,
                candidates=selection.candidates,
                selection_source=selection.selection_source,
                used_asset_keys=used_asset_keys,
            )
            if candidate is None:
                skipped_beats.append(SkippedBeat(beat_id=beat.beat_id, reason="no usable asset candidate"))
                continue
            if not self._is_manual_selection(selection) and not self._supports_automatic_insertion(
                beat=beat,
                candidate=candidate,
                current_insertions=len(insertions),
                target_insertions=max_insertions,
            ):
                skipped_beats.append(SkippedBeat(beat_id=beat.beat_id, reason="beat below insertion threshold"))
                continue
            mode = selection.forced_mode or self._mode_for_candidate(beat, candidate)
            if not self._is_manual_selection(selection) and not self._window_inside_boundaries(
                beat.start_ms,
                beat.end_ms,
                timeline,
                mode,
            ):
                skipped_beats.append(SkippedBeat(beat_id=beat.beat_id, reason="beat too close to clip boundary"))
                continue

            insertion = self._build_insertion(
                beat=beat,
                candidate=candidate,
                selection=selection,
                target_width=target_width,
                target_height=target_height,
                insertion_index=len(insertions) + 1,
                timeline=timeline,
            )

            if self._conflicts_with_existing(insertion, insertions, effective_gap_ms):
                skipped_beats.append(
                    SkippedBeat(beat_id=beat.beat_id, reason="below minimum gap with previous insertion")
                )
                continue

            insertions.append(insertion)
            used_asset_keys.add(self._candidate_identity(candidate))

        insertions.sort(key=lambda insertion: insertion.start_ms)
        return ShortEditingPlan(
            short_id=short_id,
            enabled=True,
            strategy_version="broll-plan-v1",
            insertions=tuple(insertions),
            skipped_beats=tuple(skipped_beats),
        )

    @staticmethod
    def _target_insertions_for_duration(duration_ms: int) -> int:
        return max(1, int(ceil(max(duration_ms, 1) / 15000)))

    @staticmethod
    def _dynamic_gap_ms(duration_ms: int, target_insertions: int) -> int:
        return max(500, int((duration_ms / max(1, target_insertions + 1)) * 0.50))

    def _best_candidate(
        self,
        beat: ImpactBeat,
        candidates: tuple[BrollCandidate, ...],
        selection_source: str,
        used_asset_keys: set[str],
    ) -> BrollCandidate | None:
        for candidate in candidates:
            if self._candidate_identity(candidate) in used_asset_keys:
                continue
            if self.is_candidate_usable(
                beat=beat,
                candidate=candidate,
                selection_source=selection_source,
            ):
                return candidate
        return None

    @staticmethod
    def _candidate_identity(candidate: BrollCandidate) -> str:
        return candidate.local_path or candidate.asset_url or candidate.candidate_id

    def _build_insertion(
        self,
        beat: ImpactBeat,
        candidate: BrollCandidate,
        selection: BeatCandidateSelection,
        target_width: int,
        target_height: int,
        insertion_index: int,
        timeline: SubtitleTimeline,
    ) -> BrollInsertion:
        mode = selection.forced_mode or self._mode_for_candidate(beat, candidate)
        minimum_start_ms = 0 if self._is_manual_selection(selection) else self._minimum_start_ms_for_mode(mode)
        maximum_end_ms = (
            timeline.duration_ms
            if self._is_manual_selection(selection)
            else self._maximum_end_ms_for_mode(mode, timeline.duration_ms)
        )
        preroll_ms = 80 if mode == "cutaway" else 120
        tail_ms = 220 if mode == "cutaway" else 300
        max_duration_ms = 2500 if mode == "cutaway" else 3000
        if mode == "full_frame_cutaway":
            preroll_ms = 80
            tail_ms = 220
            max_duration_ms = 3500

        computed_start_ms = max(minimum_start_ms, beat.start_ms - preroll_ms)
        computed_end_ms = min(maximum_end_ms, beat.end_ms + tail_ms, computed_start_ms + max_duration_ms)
        start_ms = selection.override_start_ms if selection.override_start_ms is not None else computed_start_ms
        end_ms = selection.override_end_ms if selection.override_end_ms is not None else computed_end_ms
        start_ms, end_ms = self._clamp_window(
            start_ms,
            end_ms,
            fallback_start_ms=computed_start_ms,
            fallback_end_ms=computed_end_ms,
            minimum_start_ms=minimum_start_ms,
            maximum_end_ms=maximum_end_ms,
        )
        duration_ms = max(300, end_ms - start_ms)
        asset_in_ms, asset_out_ms = self._asset_trim(candidate, duration_ms)

        if mode in {"cutaway", "full_frame_cutaway"}:
            x, y, width, height, opacity = 0, 0, target_width, target_height, 1.0
        else:
            width = min(target_width - 80, int(target_width * 0.82))
            height = min(int(target_height * 0.28), 620)
            x = max(0, (target_width - width) // 2)
            y = self.overlay_top_y
            opacity = 0.96

        return BrollInsertion(
            insertion_id=f"insert-{insertion_index:04d}",
            beat_id=beat.beat_id,
            mode=mode,
            asset_provider=candidate.provider,
            asset_path=candidate.local_path or "",
            start_ms=start_ms,
            end_ms=end_ms,
            source_beat_score=beat.scores.total,
            candidate_score=candidate.total_score,
            x=x,
            y=y,
            width=width,
            height=height,
            opacity=opacity,
            asset_in_ms=asset_in_ms,
            asset_out_ms=asset_out_ms,
            subtitle_safe=True,
            discovery_source=candidate.discovery_source,
            anchor_text=selection.anchor_text,
        )

    @staticmethod
    def _mode_for_candidate(beat: ImpactBeat, candidate: BrollCandidate) -> str:
        del beat
        del candidate
        return "full_frame_cutaway"

    @staticmethod
    def _asset_trim(candidate: BrollCandidate, desired_duration_ms: int) -> tuple[int, int]:
        if candidate.asset_type == "image" or candidate.duration_ms <= 0:
            return 0, desired_duration_ms

        if candidate.duration_ms <= desired_duration_ms:
            return 0, candidate.duration_ms

        asset_in_ms = max(0, (candidate.duration_ms - desired_duration_ms) // 2)
        return asset_in_ms, asset_in_ms + desired_duration_ms

    @staticmethod
    def _conflicts_with_existing(
        insertion: BrollInsertion,
        insertions: list[BrollInsertion],
        minimum_gap_ms: int,
    ) -> bool:
        for existing_insertion in insertions:
            if insertion.end_ms < existing_insertion.start_ms:
                distance_ms = existing_insertion.start_ms - insertion.end_ms
            elif existing_insertion.end_ms < insertion.start_ms:
                distance_ms = insertion.start_ms - existing_insertion.end_ms
            else:
                distance_ms = 0

            if distance_ms < minimum_gap_ms:
                return True
        return False

    @staticmethod
    def _is_manual_selection(selection: BeatCandidateSelection) -> bool:
        return selection.selection_source == "manual_override"

    @staticmethod
    def _is_promoted_near_miss(beat: ImpactBeat) -> bool:
        return "promoted near-miss high-salience beat" in beat.reasons

    def is_candidate_usable(
        self,
        beat: ImpactBeat,
        candidate: BrollCandidate,
        selection_source: str = "automatic",
    ) -> bool:
        if candidate.total_score < self.minimum_candidate_score or not candidate.local_path:
            return False

        if selection_source == "manual_override":
            return True

        return candidate.semantic_match >= self._semantic_floor_for_beat(beat)

    def _semantic_floor_for_beat(self, beat: ImpactBeat) -> float:
        if self._is_strong_automatic_beat(beat):
            return self.automatic_candidate_semantic_match_threshold
        return max(
            self.automatic_candidate_semantic_match_threshold,
            self.support_candidate_semantic_match_threshold,
        )

    def _is_strong_automatic_beat(self, beat: ImpactBeat) -> bool:
        return beat.scores.total >= self.beat_score_threshold or self._is_promoted_near_miss(beat)

    def _supports_automatic_insertion(
        self,
        beat: ImpactBeat,
        candidate: BrollCandidate,
        current_insertions: int,
        target_insertions: int,
    ) -> bool:
        del candidate
        if self._is_strong_automatic_beat(beat):
            return True

        return current_insertions < target_insertions and beat.scores.total >= self.support_beat_score_threshold

    @staticmethod
    def _window_inside_boundaries(start_ms: int, end_ms: int, timeline: SubtitleTimeline, mode: str) -> bool:
        return start_ms >= BrollInsertionPlanner._minimum_start_ms_for_mode(
            mode
        ) and end_ms <= BrollInsertionPlanner._maximum_end_ms_for_mode(mode, timeline.duration_ms)

    @staticmethod
    def _minimum_start_ms_for_mode(mode: str) -> int:
        del mode
        return 500

    @staticmethod
    def _maximum_end_ms_for_mode(mode: str, timeline_duration_ms: int) -> int:
        del mode
        return timeline_duration_ms - 250

    @staticmethod
    def _clamp_window(
        start_ms: int,
        end_ms: int,
        fallback_start_ms: int,
        fallback_end_ms: int,
        minimum_start_ms: int,
        maximum_end_ms: int,
    ) -> tuple[int, int]:
        start_ms = max(minimum_start_ms, start_ms)
        end_ms = min(maximum_end_ms, end_ms)
        if end_ms <= start_ms:
            return fallback_start_ms, fallback_end_ms
        return start_ms, end_ms

from contextlib import suppress
from math import ceil
from pathlib import Path

from src.application.broll.broll_candidate_ranker import BrollCandidateRanker
from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.application.broll.broll_query_generator import BrollQueryGenerator
from src.application.broll.impact_beat_detector import ImpactBeatDetector
from src.application.broll.manual_override_resolver import ManualBrollOverrideResolver
from src.domain.broll_models import BeatCandidateSelection, BrollCandidate, ImpactBeat, ShortEditingPlan
from src.domain.manual_broll_overrides import ManualBrollOverride
from src.domain.ports import IBrollArtifactsWriter, IBrollAssetProvider
from src.domain.subtitle_models import SubtitleTimeline


class BuildShortEditingPlanUseCase:
    DEFAULT_ENABLED = False

    def __init__(
        self,
        providers: tuple[IBrollAssetProvider, ...],
        plan_writer: IBrollArtifactsWriter,
        beat_detector: ImpactBeatDetector | None = None,
        query_generator: BrollQueryGenerator | None = None,
        candidate_ranker: BrollCandidateRanker | None = None,
        insertion_planner: BrollInsertionPlanner | None = None,
        manual_override_loader=None,
        manual_override_resolver: ManualBrollOverrideResolver | None = None,
        enabled: bool | None = None,
    ):
        self.providers = providers
        self.plan_writer = plan_writer
        self.beat_detector = beat_detector or ImpactBeatDetector()
        self.query_generator = query_generator or BrollQueryGenerator()
        self.candidate_ranker = candidate_ranker or BrollCandidateRanker()
        self.insertion_planner = insertion_planner or BrollInsertionPlanner()
        self.manual_override_loader = manual_override_loader
        self.manual_override_resolver = manual_override_resolver or ManualBrollOverrideResolver()
        self.enabled = self.DEFAULT_ENABLED if enabled is None else enabled

    def build(
        self,
        short_id: str,
        timeline: SubtitleTimeline,
        output_dir: str,
        target_width: int,
        target_height: int,
    ) -> ShortEditingPlan:
        if not self.enabled:
            return ShortEditingPlan(
                short_id=short_id,
                enabled=False,
                strategy_version="broll-plan-v1",
                insertions=(),
            )

        output_root = Path(output_dir)
        asset_cache_dir = output_root / ".cache" / "broll" / "assets"
        beats = self._detect_candidate_beats(timeline)
        self.plan_writer.write_impact_beats(short_id=short_id, timeline=timeline, beats=beats, output_dir=output_root)

        manual_override_selections = self.manual_override_resolver.resolve(
            short_id=short_id,
            timeline=timeline,
            detected_beats=beats,
            overrides=self._load_manual_overrides(),
        )
        manual_selections_by_beat = {selection.beat.beat_id: selection for selection in manual_override_selections}

        automatic_selections: list[BeatCandidateSelection] = []
        candidate_payloads: list[dict[str, object]] = []
        providers_by_name = {
            provider.__class__.__name__.replace("Provider", "").lower(): provider for provider in self.providers
        }
        for provider in self.providers:
            provider_name = getattr(provider, "provider_name", None)
            if provider_name:
                providers_by_name[provider_name] = provider

        for beat in beats:
            manual_selection = manual_selections_by_beat.get(beat.beat_id)
            if manual_selection is not None:
                candidate_payloads.append(
                    self._candidate_payload(
                        beat=manual_selection.beat,
                        queries=(),
                        candidates=manual_selection.candidates,
                        selection=manual_selection,
                    )
                )
                continue

            queries = self.query_generator.generate(beat)
            discovered_candidates, provider_attempts = self._discover_candidates(
                beat=beat,
                queries=queries,
                asset_cache_dir=str(asset_cache_dir),
            )

            ranked_candidates = self.candidate_ranker.rank(beat, queries, discovered_candidates)
            prepared_candidates = self._prepare_candidates(ranked_candidates, providers_by_name, str(asset_cache_dir))
            selection = BeatCandidateSelection(
                beat=beat,
                candidates=tuple(prepared_candidates),
                priority=int(round(beat.scores.total * 1000)),
            )
            automatic_selections.append(selection)
            candidate_payloads.append(
                self._candidate_payload(
                    beat=beat,
                    queries=queries,
                    candidates=selection.candidates,
                    selection=selection,
                    provider_attempts=provider_attempts,
                )
            )

        automatic_selections = self._prioritize_automatic_selections(
            selections=automatic_selections,
        )

        beat_candidates: list[BeatCandidateSelection] = list(automatic_selections)
        for selection in manual_override_selections:
            if selection.beat.beat_id in {beat.beat_id for beat in beats}:
                beat_candidates.append(selection)
                continue
            beat_candidates.append(selection)
            candidate_payloads.append(
                self._candidate_payload(
                    beat=selection.beat,
                    queries=(),
                    candidates=selection.candidates,
                    selection=selection,
                )
            )

        self.plan_writer.write_broll_candidates(short_id=short_id, beats=candidate_payloads, output_dir=output_root)
        plan = self.insertion_planner.plan(
            short_id=short_id,
            timeline=timeline,
            beat_candidates=beat_candidates,
            target_width=target_width,
            target_height=target_height,
        )
        self.plan_writer.write_broll_plan(short_id=short_id, plan=plan, output_dir=output_root)
        return plan

    def _detect_candidate_beats(self, timeline: SubtitleTimeline) -> list[ImpactBeat]:
        detect_candidates = getattr(self.beat_detector, "detect_candidates", None)
        if callable(detect_candidates):
            return list(detect_candidates(timeline))
        return list(self.beat_detector.detect(timeline))

    @staticmethod
    def _automatic_target_insertions(duration_ms: int, manual_override_count: int) -> int:
        target_total = max(1, int(ceil(max(duration_ms, 1) / 15000)))
        return max(0, target_total - manual_override_count)

    def _prioritize_automatic_selections(
        self,
        selections: list[BeatCandidateSelection],
    ) -> list[BeatCandidateSelection]:
        if not selections:
            return []

        return [self._prefer_local_candidates(selection, allow_remote=True) for selection in selections]

    @staticmethod
    def _prefer_local_candidates(
        selection: BeatCandidateSelection,
        allow_remote: bool,
    ) -> BeatCandidateSelection:
        local_manifest = [
            candidate for candidate in selection.candidates if candidate.discovery_source == "local_manifest"
        ]
        local_heuristic = [
            candidate for candidate in selection.candidates if candidate.discovery_source == "local_heuristic_fallback"
        ]
        remote_pexels = [candidate for candidate in selection.candidates if candidate.discovery_source == "pexels"]
        remote_pixabay = [candidate for candidate in selection.candidates if candidate.discovery_source == "pixabay"]
        remote_other = [
            candidate
            for candidate in selection.candidates
            if candidate.discovery_source not in {"local_manifest", "local_heuristic_fallback", "pexels", "pixabay"}
        ]

        prioritized_candidates = tuple(
            local_manifest + local_heuristic + (remote_pexels + remote_pixabay + remote_other if allow_remote else [])
        )
        return BeatCandidateSelection(
            beat=selection.beat,
            candidates=prioritized_candidates,
            forced_mode=selection.forced_mode,
            override_start_ms=selection.override_start_ms,
            override_end_ms=selection.override_end_ms,
            priority=selection.priority,
            anchor_text=selection.anchor_text,
            selection_source=selection.selection_source,
        )

    @staticmethod
    def _prepare_candidates(
        ranked_candidates: list[BrollCandidate],
        providers_by_name: dict[str, IBrollAssetProvider],
        cache_dir: str,
    ) -> list[BrollCandidate]:
        prepared_candidates: list[BrollCandidate] = []

        for index, candidate in enumerate(ranked_candidates):
            if index < 2:
                provider = providers_by_name.get(candidate.provider)
                if provider is not None:
                    with suppress(OSError, RuntimeError, ValueError):
                        candidate = provider.prepare_asset(candidate, cache_dir)
            prepared_candidates.append(candidate)

        return prepared_candidates

    def _load_manual_overrides(self) -> tuple[ManualBrollOverride, ...]:
        if self.manual_override_loader is None:
            return ()
        try:
            return tuple(self.manual_override_loader.load())
        except (OSError, RuntimeError, TypeError, ValueError):
            return ()

    def _discover_candidates(
        self,
        beat: ImpactBeat,
        queries: tuple[str, ...],
        asset_cache_dir: str,
    ) -> tuple[list[BrollCandidate], list[dict[str, object]]]:
        discovered_candidates: list[BrollCandidate] = []
        provider_attempts: list[dict[str, object]] = []

        for provider in self.providers:
            provider_name = self._provider_name(provider)
            provider_configured = self._provider_configured(provider)
            if not queries:
                provider_attempts.append(
                    {
                        "provider": provider_name,
                        "configured": provider_configured,
                        "attempted": False,
                        "queries": [],
                    }
                )
                continue

            query_attempts: list[dict[str, object]] = []
            provider_candidates: list[BrollCandidate] = []
            for query in queries:
                attempt = {
                    "provider": provider_name,
                    "query": query,
                    "configured": provider_configured,
                    "attempted": provider_configured,
                    "result_count": 0,
                    "error": None,
                }
                if not provider_configured:
                    query_attempts.append(attempt)
                    continue

                try:
                    query_candidates = provider.search(beat, (query,), asset_cache_dir)
                except (OSError, RuntimeError, ValueError) as error:
                    attempt["error"] = f"{error.__class__.__name__}: {error}"
                    query_attempts.append(attempt)
                    continue

                attempt["result_count"] = len(query_candidates)
                query_attempts.append(attempt)
                provider_candidates.extend(query_candidates)

            provider_attempts.append(
                {
                    "provider": provider_name,
                    "configured": provider_configured,
                    "attempted": provider_configured and bool(queries),
                    "queries": query_attempts,
                    "total_results": len(provider_candidates),
                }
            )
            discovered_candidates.extend(provider_candidates)

        return discovered_candidates, provider_attempts

    @staticmethod
    def _provider_name(provider: IBrollAssetProvider) -> str:
        return getattr(provider, "provider_name", provider.__class__.__name__.replace("Provider", "").lower())

    @staticmethod
    def _provider_configured(provider: IBrollAssetProvider) -> bool:
        api_key = getattr(provider, "api_key", None)
        if api_key is None:
            return True
        return bool(api_key)

    @staticmethod
    def _candidate_payload(
        beat: ImpactBeat,
        queries: tuple[str, ...],
        candidates: tuple[BrollCandidate, ...],
        selection: BeatCandidateSelection,
        provider_attempts: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        payload = {
            "beat_id": beat.beat_id,
            "queries": list(queries),
            "candidates": [candidate.to_dict() for candidate in candidates],
            "selection_source": selection.selection_source,
        }
        if provider_attempts:
            payload["provider_attempts"] = provider_attempts
        if selection.anchor_text:
            payload["anchor_text"] = selection.anchor_text
        if selection.forced_mode:
            payload["forced_mode"] = selection.forced_mode
        return payload

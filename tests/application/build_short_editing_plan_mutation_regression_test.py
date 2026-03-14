from typing import cast

from src.application.broll import BuildShortEditingPlanUseCase
from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.application.broll.impact_beat_detector import ImpactBeatDetector
from src.domain.broll_models import BeatCandidateSelection, ImpactBeat, ShortEditingPlan
from src.domain.ports import IBrollArtifactsWriter, IBrollAssetProvider
from tests.application.build_short_editing_plan_use_case_support_test import (
    FakeManualOverrideLoader,
    FakeProvider,
    FakeWriter,
    TwoBeatDetector,
    _build_timeline,
    build_manual_override,
)


class CapturingInsertionPlanner:
    def __init__(self):
        self.beat_candidates: tuple[BeatCandidateSelection, ...] = ()

    def plan(self, short_id, timeline, beat_candidates, target_width, target_height):
        del timeline, target_width, target_height
        self.beat_candidates = tuple(beat_candidates)
        return ShortEditingPlan(short_id=short_id, enabled=True, strategy_version="broll-plan-v1", insertions=())


def test_build_short_editing_plan_use_case_uses_disabled_default_when_enabled_is_none(tmp_path):
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=cast(IBrollArtifactsWriter, FakeWriter()),
        enabled=None,
    )

    plan = use_case.build(
        short_id="short-default-none",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.short_id == "short-default-none"
    assert plan.enabled is False
    assert plan.insertions == ()


def test_build_short_editing_plan_use_case_disabled_plan_preserves_short_id(tmp_path):
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=cast(IBrollArtifactsWriter, FakeWriter()),
        enabled=False,
    )

    plan = use_case.build(
        short_id="short-disabled",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.short_id == "short-disabled"
    assert plan.enabled is False
    assert plan.insertions == ()


def test_build_short_editing_plan_use_case_continues_after_manual_selection_for_first_detected_beat(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    manual_asset = tmp_path / "manual-negative.mp4"
    manual_asset.write_bytes(b"video")
    use_case = BuildShortEditingPlanUseCase(
        providers=cast(tuple[IBrollAssetProvider, ...], (provider,)),
        plan_writer=cast(IBrollArtifactsWriter, writer),
        beat_detector=cast(ImpactBeatDetector, TwoBeatDetector()),
        manual_override_loader=FakeManualOverrideLoader(
            (
                build_manual_override(
                    short_id="short-manual-first",
                    anchor_text="negative thoughts",
                    asset_path=str(manual_asset),
                    mode="full_frame_cutaway",
                    priority=250,
                ),
            )
        ),
        enabled=True,
    )

    use_case.build(
        short_id="short-manual-first",
        timeline=_build_timeline(0, 24000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    payloads = writer.candidate_payload[1]
    assert [payload["beat_id"] for payload in payloads] == ["beat-0001", "beat-0002"]
    assert payloads[0]["selection_source"] == "manual_override"
    assert payloads[1]["selection_source"] == "automatic"
    assert provider.search_calls > 0


def test_build_short_editing_plan_use_case_scales_automatic_priorities_from_beat_score(tmp_path):
    planner = CapturingInsertionPlanner()
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=cast(IBrollArtifactsWriter, FakeWriter()),
        beat_detector=cast(ImpactBeatDetector, TwoBeatDetector()),
        insertion_planner=cast(BrollInsertionPlanner, planner),
        enabled=True,
    )

    use_case.build(
        short_id="short-priority-scale",
        timeline=_build_timeline(0, 24000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert [selection.priority for selection in planner.beat_candidates] == [890, 820]
    assert all(isinstance(selection.beat, ImpactBeat) for selection in planner.beat_candidates)


def test_build_short_editing_plan_use_case_records_nested_query_configuration_metadata(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=cast(tuple[IBrollAssetProvider, ...], (provider,)),
        plan_writer=cast(IBrollArtifactsWriter, writer),
        beat_detector=cast(ImpactBeatDetector, TwoBeatDetector()),
        enabled=True,
    )

    use_case.build(
        short_id="short-query-audit",
        timeline=_build_timeline(0, 24000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    attempts = writer.candidate_payload[1][0]["provider_attempts"][0]["queries"]
    assert attempts
    assert all(attempt["configured"] is True for attempt in attempts)
    assert all(attempt["attempted"] is True for attempt in attempts)

from pathlib import Path

from src.application.broll import BuildShortEditingPlanUseCase
from tests.application.build_short_editing_plan_use_case_support_test import (
    ClassNameFallbackProvider,
    DualQueryGenerator,
    EmptyQueryGenerator,
    FailingProvider,
    FakeDetector,
    FakeProvider,
    FakeWriter,
    RaiseOnPrepareProvider,
    RaisingLoader,
    SingleQueryGenerator,
    TrackingFailingProvider,
    UnconfiguredProvider,
    _build_candidate,
    _build_timeline,
)


def test_build_short_editing_plan_use_case_audits_provider_errors_in_candidate_payload(tmp_path):
    writer = FakeWriter()
    use_case = BuildShortEditingPlanUseCase(
        providers=(FailingProvider(),),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_provider_audit",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 0
    attempt = writer.candidate_payload[1][0]["provider_attempts"][0]
    assert attempt["provider"] == "pexels"
    assert attempt["configured"] is True
    assert attempt["attempted"] is True
    assert attempt["queries"][0]["error"] == "RuntimeError: boom"
    assert attempt["queries"][0]["result_count"] == 0


def test_build_short_editing_plan_use_case_records_successful_query_attempt_metadata(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        query_generator=SingleQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_successful_attempt",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    attempt = writer.candidate_payload[1][0]["provider_attempts"][0]["queries"][0]
    assert attempt["provider"] == "fake"
    assert attempt["query"] == "launch product office"
    assert attempt["result_count"] == 1
    assert attempt["error"] is None


def test_build_short_editing_plan_use_case_uses_class_name_provider_mapping_for_prepare_asset(tmp_path):
    writer = FakeWriter()
    provider = ClassNameFallbackProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        query_generator=SingleQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_class_name_provider",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert provider.prepare_calls == 1
    assert writer.candidate_payload[1][0]["candidates"][0]["local_path"] == str(
        Path(tmp_path) / ".cache" / "broll" / "assets" / "class-name-1.mp4"
    )


def test_build_short_editing_plan_use_case_records_empty_query_attempts_for_all_providers(tmp_path):
    writer = FakeWriter()
    configured_provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(configured_provider, UnconfiguredProvider()),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        query_generator=EmptyQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_empty_queries_all_providers",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 0
    assert configured_provider.search_calls == 0
    assert writer.candidate_payload[1][0]["provider_attempts"] == [
        {
            "provider": "fake",
            "configured": True,
            "attempted": False,
            "queries": [],
        },
        {
            "provider": "pixabay",
            "configured": False,
            "attempted": False,
            "queries": [],
        },
    ]


def test_build_short_editing_plan_use_case_skips_search_when_queries_are_empty(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        query_generator=EmptyQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_empty_queries",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 0
    assert provider.search_calls == 0
    assert writer.candidate_payload[1][0]["provider_attempts"][0] == {
        "provider": "fake",
        "configured": True,
        "attempted": False,
        "queries": [],
    }


def test_build_short_editing_plan_use_case_marks_unconfigured_provider_without_calling_search(tmp_path):
    writer = FakeWriter()
    use_case = BuildShortEditingPlanUseCase(
        providers=(UnconfiguredProvider(),),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_unconfigured_provider",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 0
    attempt = writer.candidate_payload[1][0]["provider_attempts"][0]
    assert attempt["configured"] is False
    assert attempt["attempted"] is False
    assert all(query_attempt["attempted"] is False for query_attempt in attempt["queries"])


def test_build_short_editing_plan_use_case_keeps_auditing_all_queries_after_provider_errors(tmp_path):
    writer = FakeWriter()
    provider = TrackingFailingProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        query_generator=DualQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_all_error_queries",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 0
    assert provider.searched_queries == ["launch product office", "confusing negatives"]
    attempt = writer.candidate_payload[1][0]["provider_attempts"][0]
    assert attempt["total_results"] == 0
    assert [query_attempt["query"] for query_attempt in attempt["queries"]] == [
        "launch product office",
        "confusing negatives",
    ]
    assert all(query_attempt["provider"] == "pexels" for query_attempt in attempt["queries"])
    assert all(query_attempt["error"] == "RuntimeError: boom" for query_attempt in attempt["queries"])


def test_build_short_editing_plan_use_case_ignores_manual_override_loader_errors(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        manual_override_loader=RaisingLoader(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_loader_error",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert writer.candidate_payload[1][0]["selection_source"] == "automatic"


def test_build_short_editing_plan_use_case_keeps_candidates_when_prepare_asset_fails(tmp_path):
    writer = FakeWriter()
    candidate = _build_candidate(
        candidate_id="local-prepare-fails",
        provider="local_media",
        discovery_source="local_manifest",
        local_path=str(tmp_path / "local-prepare-fails.mp4"),
        title="launch product office",
        tags=("launch", "product", "office"),
    )
    provider = RaiseOnPrepareProvider(candidate)
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        query_generator=SingleQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_prepare_error",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert provider.prepare_calls == 1
    assert plan.insertions[0].asset_provider == "local_media"

from src.application.broll import BuildShortEditingPlanUseCase
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline
from tests.application.build_short_editing_plan_use_case_support_test import (
    FakeDetector,
    FakeStaticProvider,
    FakeWriter,
    TwoBeatDetector,
    _build_candidate,
    _build_timeline,
)


def test_build_short_editing_plan_use_case_prefers_local_candidates_over_remote_when_target_is_met(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
            _build_candidate(
                candidate_id="local-2",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-2.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="remote-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "remote-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_local_first",
        timeline=_build_timeline(0, 24000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    assert all(insertion.asset_provider == "local_media" for insertion in plan.insertions)
    assert all(insertion.discovery_source == "local_manifest" for insertion in plan.insertions)
    assert all(insertion.mode == "full_frame_cutaway" for insertion in plan.insertions)


def test_build_short_editing_plan_use_case_uses_remote_when_local_density_is_insufficient(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="remote-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "remote-1.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_remote_fallback",
        timeline=_build_timeline(0, 24000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    assert any(insertion.asset_provider == "pixabay" for insertion in plan.insertions)
    assert any(insertion.asset_provider == "local_media" for insertion in plan.insertions)


def test_build_short_editing_plan_use_case_uses_remote_when_local_match_is_semantically_too_weak(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
            _build_candidate(
                candidate_id="local-2",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-2.mp4"),
                title="negatives",
                tags=("negatives",),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="remote-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "remote-1.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_remote_semantic_fallback",
        timeline=_build_timeline(0, 24000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    second_insertion = next(insertion for insertion in plan.insertions if insertion.beat_id == "beat-0002")
    assert second_insertion.asset_provider == "pixabay"
    assert second_insertion.discovery_source == "pixabay"


def test_build_short_editing_plan_use_case_uses_remote_when_local_asset_would_repeat_within_short(tmp_path):
    writer = FakeWriter()
    shared_local = str(tmp_path / "local-shared.mp4")
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-shared-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=shared_local,
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
            _build_candidate(
                candidate_id="local-shared-2",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=shared_local,
                title="confusing negatives",
                tags=("confusing", "negatives"),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pexels",
        candidates=[
            _build_candidate(
                candidate_id="pexels-1",
                provider="pexels",
                discovery_source="pexels",
                local_path=str(tmp_path / "pexels-1.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_remote_after_local_repeat",
        timeline=_build_timeline(0, 24000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    first_insertion = next(insertion for insertion in plan.insertions if insertion.beat_id == "beat-0001")
    second_insertion = next(insertion for insertion in plan.insertions if insertion.beat_id == "beat-0002")
    assert first_insertion.asset_provider == "local_media"
    assert second_insertion.asset_provider == "pexels"
    assert second_insertion.discovery_source == "pexels"


def test_build_short_editing_plan_use_case_keeps_remote_candidates_beyond_top_local_slots(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id=f"local-{index}",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / f"local-{index}.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
            )
            for index in range(6)
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pexels",
        candidates=[
            _build_candidate(
                candidate_id="pexels-1",
                provider="pexels",
                discovery_source="pexels",
                local_path=str(tmp_path / "pexels-1.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=10000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="launch product in office",
                start_ms=2000,
                end_ms=3600,
                timing_mode="reconciled_asr",
                quality_score=0.85,
                words=(
                    ProjectedWord("launch", 2000, 2400, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 2400, 3000, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("office", 3000, 3600, 0.8, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.85,
    )

    use_case.build(
        short_id="short_keep_remote_candidates",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    candidate_payload = writer.candidate_payload[1][0]["candidates"]
    assert any(candidate["discovery_source"] == "pexels" for candidate in candidate_payload)


def test_build_short_editing_plan_use_case_prefers_pexels_over_pixabay_within_remote_fallback(tmp_path):
    writer = FakeWriter()
    pexels_provider = FakeStaticProvider(
        provider_name="pexels",
        candidates=[
            _build_candidate(
                candidate_id="pexels-1",
                provider="pexels",
                discovery_source="pexels",
                local_path=str(tmp_path / "pexels-1.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
        ],
    )
    pixabay_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="pixabay-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "pixabay-1.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(pixabay_provider, pexels_provider),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=10000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="launch product in office",
                start_ms=2000,
                end_ms=3600,
                timing_mode="reconciled_asr",
                quality_score=0.85,
                words=(
                    ProjectedWord("launch", 2000, 2400, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 2400, 3000, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("office", 3000, 3600, 0.8, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.85,
    )

    plan = use_case.build(
        short_id="short_pexels_remote_priority",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].asset_provider == "pexels"
    assert plan.insertions[0].discovery_source == "pexels"

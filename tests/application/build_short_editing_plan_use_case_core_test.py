from pathlib import Path

from src.application.broll import BuildShortEditingPlanUseCase
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline
from tests.application.build_short_editing_plan_use_case_support_test import (
    CandidateOnlyDetector,
    ConfusingBeatDetector,
    EmptyQueryGenerator,
    FakeDetector,
    FakeManualOverrideLoader,
    FakeProvider,
    FakeWriter,
    TimelineTrackingDetector,
    _build_detected_beat,
    _build_timeline,
    build_manual_override,
)


def test_build_short_editing_plan_use_case_returns_disabled_plan_when_feature_is_off(tmp_path):
    writer = FakeWriter()
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=writer,
        enabled=False,
    )

    plan = use_case.build(
        short_id="short_0",
        timeline=SubtitleTimeline(0, 1000, (), (), 0.0),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.enabled is False
    assert plan.insertions == ()
    assert plan.strategy_version == "broll-plan-v1"
    assert writer.impact_payload is None


def test_build_short_editing_plan_use_case_is_disabled_by_default(tmp_path):
    writer = FakeWriter()
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=writer,
    )

    plan = use_case.build(
        short_id="short_default_disabled",
        timeline=SubtitleTimeline(0, 1000, (), (), 0.0),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.enabled is False
    assert plan.insertions == ()
    assert writer.impact_payload is None


def test_build_short_editing_plan_use_case_writes_artifacts_and_prepares_candidates(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
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
        short_id="short_0",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )
    expected_cache_dir = str(Path(tmp_path) / ".cache" / "broll" / "assets")

    assert plan.enabled is True
    assert len(plan.insertions) == 1
    assert provider.prepare_calls == 2
    assert set(provider.search_cache_dirs) == {expected_cache_dir}
    assert set(provider.prepare_cache_dirs) == {expected_cache_dir}
    assert writer.impact_payload[0] == "short_0"
    assert writer.impact_payload[3] == Path(tmp_path)
    assert writer.candidate_payload[0] == "short_0"
    assert writer.plan_payload[0] == "short_0"
    assert writer.candidate_payload[1][0]["candidates"][0]["discovery_source"] == "fake"
    assert writer.candidate_payload[1][0]["candidates"][0]["local_path"] == str(Path(expected_cache_dir) / "fake-1.mp4")
    assert writer.candidate_payload[1][0]["provider_attempts"][0]["provider"] == "fake"
    assert writer.candidate_payload[1][0]["provider_attempts"][0]["queries"][0]["result_count"] == 1


def test_build_short_editing_plan_use_case_creates_insertion_for_confusing_phrase(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="It's so confusing with all those negatives.",
                start_ms=2000,
                end_ms=3960,
                timing_mode="reconciled_asr",
                quality_score=0.95,
                words=(
                    ProjectedWord("It's", 2000, 2280, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("so", 2280, 2560, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("confusing", 2560, 2840, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("with", 2840, 3120, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("all", 3120, 3400, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("those", 3400, 3680, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("negatives.", 3680, 3960, 0.94, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.95,
    )

    plan = use_case.build(
        short_id="short_1",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.enabled is True
    assert len(plan.insertions) == 1
    assert writer.impact_payload[2][0].text == "It's so confusing with all those negatives."
    assert writer.candidate_payload[1][0]["candidates"][0]["discovery_source"] == "fake"


def test_build_short_editing_plan_use_case_prefers_detect_candidates_when_available(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=CandidateOnlyDetector(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_detect_candidates",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert writer.impact_payload[2][0].beat_id == "beat-candidate"


def test_build_short_editing_plan_use_case_passes_timeline_to_detector_without_detect_candidates(tmp_path):
    writer = FakeWriter()
    detector = TimelineTrackingDetector(
        _build_detected_beat("beat-forwarded", "launch product office", 2000, 3600, 0.91)
    )
    timeline = _build_timeline(0, 12000)
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=writer,
        beat_detector=detector,
        query_generator=EmptyQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short_timeline_forwarded",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.insertions == ()
    assert detector.seen_timeline is timeline
    assert writer.impact_payload[1] is timeline
    assert writer.impact_payload[2][0].beat_id == "beat-forwarded"


def test_build_short_editing_plan_use_case_records_manual_candidate_payload_for_synthetic_beat(tmp_path):
    writer = FakeWriter()
    manual_asset = tmp_path / "manual-job-interview.mp4"
    manual_asset.write_bytes(b"video")
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=writer,
        beat_detector=type("NoBeatDetector", (), {"detect": staticmethod(lambda timeline: [])})(),
        manual_override_loader=FakeManualOverrideLoader(
            (
                build_manual_override(
                    short_id="short_manual_synthetic",
                    anchor_text="job interview",
                    asset_path=str(manual_asset),
                    mode="full_frame_cutaway",
                    priority=300,
                ),
            )
        ),
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=14000,
        cues=(
            ProjectedCue(
                cue_id="cue-2",
                speaker="Speaker 1",
                original_text="I walked into the job interview already nervous.",
                start_ms=2000,
                end_ms=5200,
                timing_mode="reconciled_asr",
                quality_score=0.93,
                words=(
                    ProjectedWord("I", 2000, 2200, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("walked", 2200, 2500, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("into", 2500, 2800, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("the", 2800, 3000, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("job", 3000, 3400, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("interview", 3400, 3900, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("already", 3900, 4400, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("nervous.", 4400, 5200, 0.9, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.93,
    )

    plan = use_case.build(
        short_id="short_manual_synthetic",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert writer.candidate_payload[1][0]["selection_source"] == "manual_override"
    assert writer.candidate_payload[1][0]["anchor_text"] == "job interview"


def test_build_short_editing_plan_use_case_prefers_manual_override_and_bypasses_auto_provider(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    manual_asset = tmp_path / "manual-confusing.mp4"
    manual_asset.write_bytes(b"video")
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=ConfusingBeatDetector(),
        manual_override_loader=FakeManualOverrideLoader(
            (
                build_manual_override(
                    short_id="short_0",
                    anchor_text="so confusing",
                    asset_path=str(manual_asset),
                    mode="full_frame_cutaway",
                    priority=250,
                ),
            )
        ),
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="It's so confusing with all those negatives.",
                start_ms=2000,
                end_ms=3960,
                timing_mode="reconciled_asr",
                quality_score=0.95,
                words=(
                    ProjectedWord("It's", 2000, 2280, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("so", 2280, 2560, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("confusing", 2560, 2840, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("with", 2840, 3120, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("all", 3120, 3400, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("those", 3400, 3680, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("negatives.", 3680, 3960, 0.94, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.95,
    )

    plan = use_case.build(
        short_id="short_0",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].mode == "full_frame_cutaway"
    assert plan.insertions[0].asset_provider == "manual_override"
    assert plan.insertions[0].discovery_source == "manual_override"
    assert provider.search_calls == 0
    assert writer.candidate_payload[1][0]["selection_source"] == "manual_override"

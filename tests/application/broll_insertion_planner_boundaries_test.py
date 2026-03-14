from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.domain.broll_models import BeatCandidateSelection, BeatScoreBreakdown, BrollCandidate, ImpactBeat
from src.domain.subtitle_models import SubtitleTimeline


def test_insertion_planner_uses_expected_defaults():
    planner = BrollInsertionPlanner()

    assert planner.minimum_gap_ms == 4500
    assert planner.beat_score_threshold == 0.68
    assert planner.cutaway_score_threshold == 0.82
    assert planner.minimum_candidate_score == 0.55
    assert planner.overlay_top_y == 120
    assert planner.support_beat_score_threshold == 0.30
    assert planner.automatic_candidate_semantic_match_threshold == 0.30
    assert planner.support_candidate_semantic_match_threshold == 0.45


def test_insertion_planner_prioritizes_manual_override_before_automatic_when_only_one_slot_fits():
    planner = BrollInsertionPlanner()
    timeline = SubtitleTimeline(0, 15000, (), (), 0.95)
    manual_selection = BeatCandidateSelection(
        beat=_build_beat("manual-beat", 5200, 6500, total=0.2),
        candidates=(_build_candidate("manual-candidate", "/tmp/manual.mp4", semantic_match=0.1),),
        selection_source="manual_override",
        priority=10,
        forced_mode="full_frame_cutaway",
    )
    automatic_selection = BeatCandidateSelection(
        beat=_build_beat("automatic-beat", 8000, 9400, total=0.95),
        candidates=(_build_candidate("automatic-candidate", "/tmp/automatic.mp4", semantic_match=0.9),),
        priority=999,
    )

    plan = planner.plan(
        short_id="short_manual_first",
        timeline=timeline,
        beat_candidates=[automatic_selection, manual_selection],
        target_width=1080,
        target_height=1920,
    )

    assert [insertion.beat_id for insertion in plan.insertions] == ["manual-beat"]
    assert [(skipped.beat_id, skipped.reason) for skipped in plan.skipped_beats] == [
        ("automatic-beat", "maximum insertions reached")
    ]


def test_insertion_planner_keeps_manual_candidate_usable_with_low_semantic_match():
    planner = BrollInsertionPlanner()
    timeline = SubtitleTimeline(0, 15000, (), (), 0.95)
    manual_selection = BeatCandidateSelection(
        beat=_build_beat("manual-beat", 5200, 6500, total=0.1),
        candidates=(_build_candidate("manual-candidate", "/tmp/manual.mp4", semantic_match=0.0),),
        selection_source="manual_override",
        priority=100,
        forced_mode="full_frame_cutaway",
    )

    plan = planner.plan(
        short_id="short_manual_semantic_floor",
        timeline=timeline,
        beat_candidates=[manual_selection],
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].beat_id == "manual-beat"
    assert plan.insertions[0].asset_path == "/tmp/manual.mp4"


def _build_beat(beat_id: str, start_ms: int, end_ms: int, total: float) -> ImpactBeat:
    return ImpactBeat(
        beat_id=beat_id,
        text="market launch",
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        timing_mode="aligned",
        word_confidence_avg=0.9,
        cue_quality_score=0.9,
        scores=BeatScoreBreakdown(
            total=total,
            visualizability=0.8,
            emotional_load=0.7,
            contrast=0.6,
            narrative_turn=0.7,
            verbal_force=0.7,
            duration_fit=0.9,
            timing_confidence=0.95,
            semantic_salience=0.2,
        ),
        reasons=("strong beat",),
    )


def _build_candidate(candidate_id: str, local_path: str, semantic_match: float) -> BrollCandidate:
    return BrollCandidate(
        candidate_id=candidate_id,
        provider="local_media",
        discovery_source="local_manifest",
        asset_type="video",
        asset_url="https://example.com/asset.mp4",
        local_path=local_path,
        duration_ms=2400,
        width=720,
        height=1280,
        orientation="vertical",
        title="market launch",
        tags=("market", "launch"),
        semantic_match=semantic_match,
        total_score=0.9,
    )

from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.domain.broll_models import BeatCandidateSelection, BeatScoreBreakdown, BrollCandidate, ImpactBeat
from src.domain.subtitle_models import SubtitleTimeline


def test_insertion_planner_continues_after_high_priority_weak_beat_is_skipped():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 45000, (), (), 0.9)

    plan = planner.plan(
        short_id="short-continue-after-skip",
        timeline=timeline,
        beat_candidates=[
            BeatCandidateSelection(
                beat=_build_beat("weak-first", 5000, 6000, 0.2),
                candidates=(_build_candidate("candidate-weak", "/tmp/weak.mp4", 0.9),),
                priority=1000,
            ),
            BeatCandidateSelection(
                beat=_build_beat("strong-second", 20000, 21200, 0.9),
                candidates=(_build_candidate("candidate-strong", "/tmp/strong.mp4", 0.9),),
                priority=10,
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    assert [skipped.beat_id for skipped in plan.skipped_beats] == ["weak-first"]
    assert plan.skipped_beats[0].reason == "beat below insertion threshold"
    assert [insertion.beat_id for insertion in plan.insertions] == ["strong-second"]


def test_insertion_planner_build_insertion_uses_exact_cutaway_padding_values():
    planner = BrollInsertionPlanner()
    beat = _build_beat("cutaway-padding", 2000, 3000, 0.9)
    candidate = _build_candidate("candidate-cutaway", "/tmp/cutaway.mp4", 0.9, duration_ms=5000)
    selection = BeatCandidateSelection(
        beat=beat,
        candidates=(candidate,),
        forced_mode="cutaway",
    )
    timeline = SubtitleTimeline(0, 12000, (), (), 0.95)

    insertion = planner._build_insertion(
        beat=beat,
        candidate=candidate,
        selection=selection,
        target_width=1080,
        target_height=1920,
        insertion_index=1,
        timeline=timeline,
    )

    assert insertion.mode == "cutaway"
    assert insertion.start_ms == 1920
    assert insertion.end_ms == 3220
    assert insertion.asset_in_ms == 1850
    assert insertion.asset_out_ms == 3150
    assert (insertion.x, insertion.y, insertion.width, insertion.height, insertion.opacity) == (0, 0, 1080, 1920, 1.0)


def test_insertion_planner_build_insertion_caps_cutaway_duration_at_2500_ms():
    planner = BrollInsertionPlanner()
    beat = _build_beat("cutaway-capped", 4000, 7000, 0.9)
    candidate = _build_candidate("candidate-cutaway-cap", "/tmp/cutaway-cap.mp4", 0.9, duration_ms=6000)
    selection = BeatCandidateSelection(
        beat=beat,
        candidates=(candidate,),
        forced_mode="cutaway",
    )
    timeline = SubtitleTimeline(0, 14000, (), (), 0.95)

    insertion = planner._build_insertion(
        beat=beat,
        candidate=candidate,
        selection=selection,
        target_width=1080,
        target_height=1920,
        insertion_index=1,
        timeline=timeline,
    )

    assert insertion.start_ms == 3920
    assert insertion.end_ms == 6420
    assert insertion.asset_in_ms == 1750
    assert insertion.asset_out_ms == 4250


def test_insertion_planner_build_insertion_caps_full_frame_cutaway_duration_at_3500_ms():
    planner = BrollInsertionPlanner()
    beat = _build_beat("full-frame-capped", 5000, 9000, 0.9)
    candidate = _build_candidate("candidate-full-frame-cap", "/tmp/full-frame-cap.mp4", 0.9, duration_ms=7000)
    selection = BeatCandidateSelection(
        beat=beat,
        candidates=(candidate,),
        forced_mode="full_frame_cutaway",
    )
    timeline = SubtitleTimeline(0, 16000, (), (), 0.95)

    insertion = planner._build_insertion(
        beat=beat,
        candidate=candidate,
        selection=selection,
        target_width=1080,
        target_height=1920,
        insertion_index=1,
        timeline=timeline,
    )

    assert insertion.start_ms == 4920
    assert insertion.end_ms == 8420
    assert insertion.asset_in_ms == 1750
    assert insertion.asset_out_ms == 5250


def test_insertion_planner_candidate_identity_falls_back_from_local_path_to_asset_url_to_candidate_id():
    assert (
        BrollInsertionPlanner._candidate_identity(
            _build_candidate("candidate-local", "/tmp/local.mp4", 0.9, asset_url="https://example.com/local.mp4")
        )
        == "/tmp/local.mp4"
    )
    assert (
        BrollInsertionPlanner._candidate_identity(
            _build_candidate("candidate-url", None, 0.9, asset_url="https://example.com/remote.mp4")
        )
        == "https://example.com/remote.mp4"
    )
    assert (
        BrollInsertionPlanner._candidate_identity(_build_candidate("candidate-id", None, 0.9, asset_url=""))
        == "candidate-id"
    )


def test_insertion_planner_target_insertions_for_duration_uses_15_second_boundaries():
    assert BrollInsertionPlanner._target_insertions_for_duration(0) == 1
    assert BrollInsertionPlanner._target_insertions_for_duration(14999) == 1
    assert BrollInsertionPlanner._target_insertions_for_duration(15000) == 1
    assert BrollInsertionPlanner._target_insertions_for_duration(15001) == 2
    assert BrollInsertionPlanner._target_insertions_for_duration(30001) == 3


def test_insertion_planner_dynamic_gap_ms_applies_formula_and_500_ms_floor():
    assert BrollInsertionPlanner._dynamic_gap_ms(1000, 1) == 500
    assert BrollInsertionPlanner._dynamic_gap_ms(6000, 1) == 1500
    assert BrollInsertionPlanner._dynamic_gap_ms(9000, 2) == 1500


def test_insertion_planner_clamp_window_clamps_to_bounds_without_using_fallback():
    window = BrollInsertionPlanner._clamp_window(
        start_ms=200,
        end_ms=12500,
        fallback_start_ms=900,
        fallback_end_ms=1600,
        minimum_start_ms=500,
        maximum_end_ms=11750,
    )

    assert window == (500, 11750)


def test_insertion_planner_best_candidate_uses_real_beat_for_semantic_floor_checks():
    planner = BrollInsertionPlanner()
    beat = _build_beat("support-floor", 4000, 5200, planner.support_beat_score_threshold, reasons=("support beat",))
    weak_candidate = _build_candidate("candidate-weak-floor", "/tmp/weak-floor.mp4", 0.9)
    strong_candidate = _build_candidate("candidate-strong-floor", "/tmp/strong-floor.mp4", 0.9)
    weak_candidate = type(weak_candidate)(**{**weak_candidate.__dict__, "semantic_match": 0.44})
    strong_candidate = type(strong_candidate)(**{**strong_candidate.__dict__, "semantic_match": 0.45})

    selected = planner._best_candidate(
        beat=beat,
        candidates=(weak_candidate, strong_candidate),
        selection_source="automatic",
        used_asset_keys=set(),
    )

    assert selected == strong_candidate


def _build_beat(
    beat_id: str,
    start_ms: int,
    end_ms: int,
    total: float,
    reasons: tuple[str, ...] = ("strong beat",),
) -> ImpactBeat:
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
            semantic_salience=0.6,
        ),
        reasons=reasons,
    )


def _build_candidate(
    candidate_id: str,
    local_path: str | None,
    total_score: float,
    *,
    duration_ms: int = 2400,
    asset_url: str = "https://example.com/asset.mp4",
    discovery_source: str = "local_manifest",
) -> BrollCandidate:
    return BrollCandidate(
        candidate_id=candidate_id,
        provider="local_media",
        discovery_source=discovery_source,
        asset_type="video",
        asset_url=asset_url,
        local_path=local_path,
        duration_ms=duration_ms,
        width=720,
        height=1280,
        orientation="vertical",
        title="market launch",
        tags=("market", "launch"),
        semantic_match=0.9,
        total_score=total_score,
    )

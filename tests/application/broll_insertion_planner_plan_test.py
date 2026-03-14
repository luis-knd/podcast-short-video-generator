from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.domain.broll_models import BeatCandidateSelection, BeatScoreBreakdown, BrollCandidate, ImpactBeat
from src.domain.subtitle_models import SubtitleTimeline


def test_plan_records_beat_below_insertion_threshold_with_correct_beat_id_and_reason():
    planner = BrollInsertionPlanner(
        minimum_gap_ms=500,
        beat_score_threshold=0.68,
        support_beat_score_threshold=0.30,
    )
    timeline = SubtitleTimeline(0, 30000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(
                beat=_beat("below-thresh", 5000, 6000, 0.20),
                candidates=(_cand("c", "/tmp/c.mp4", 0.9),),
            )
        ],
        1080,
        1920,
    )

    assert len(plan.skipped_beats) == 1
    assert plan.skipped_beats[0].beat_id == "below-thresh"
    assert plan.skipped_beats[0].reason == "beat below insertion threshold"


def test_plan_continues_loop_after_skipped_beat_below_threshold():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 45000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(
                beat=_beat("weak", 5000, 6000, 0.30),
                candidates=(_cand("c1", "/tmp/c1.mp4", 0.9),),
            ),
            BeatCandidateSelection(
                beat=_beat("strong", 20000, 21000, 0.9),
                candidates=(_cand("c2", "/tmp/c2.mp4", 0.9),),
            ),
        ],
        1080,
        1920,
    )

    assert any(i.beat_id == "strong" for i in plan.insertions)


def test_plan_uses_forced_mode_when_provided():
    planner = BrollInsertionPlanner(minimum_gap_ms=500)
    timeline = SubtitleTimeline(0, 30000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(
                beat=_beat("m", 5000, 6000, 0.9),
                candidates=(_cand("c", "/tmp/c.mp4", 0.9),),
                forced_mode="overlay",
                selection_source="manual_override",
            )
        ],
        1080,
        1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].mode == "overlay"


def test_plan_falls_back_to_mode_for_candidate_when_no_forced_mode():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 30000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(
                beat=_beat("b", 5000, 6000, 0.9),
                candidates=(_cand("c", "/tmp/c.mp4", 0.9),),
                forced_mode=None,
            )
        ],
        1080,
        1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].mode == "full_frame_cutaway"


def test_plan_passes_candidate_to_window_check():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 30000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(
                beat=_beat("b", 5000, 6000, 0.9),
                candidates=(_cand("c", "/tmp/c.mp4", 0.9),),
            )
        ],
        1080,
        1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].beat_id == "b"
    assert plan.insertions[0].asset_path == "/tmp/c.mp4"


def test_plan_uses_mode_in_window_boundary_check():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 5000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(
                beat=_beat("b", 300, 600, 0.9),
                candidates=(_cand("c", "/tmp/c.mp4", 0.9),),
            )
        ],
        1080,
        1920,
    )

    assert any(s.reason == "beat too close to clip boundary" for s in plan.skipped_beats)


def test_plan_insertion_index_starts_at_one_and_increments():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 60000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(beat=_beat("b1", 5000, 6000, 0.9), candidates=(_cand("c1", "/tmp/c1.mp4", 0.9),)),
            BeatCandidateSelection(beat=_beat("b2", 20000, 21000, 0.9), candidates=(_cand("c2", "/tmp/c2.mp4", 0.9),)),
        ],
        1080,
        1920,
    )

    assert plan.insertions[0].insertion_id == "insert-0001"
    assert plan.insertions[1].insertion_id == "insert-0002"


def test_plan_gap_conflict_records_correct_beat_id():
    planner = BrollInsertionPlanner(minimum_gap_ms=8000, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 40000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(beat=_beat("first", 5000, 6000, 0.9), candidates=(_cand("c1", "/tmp/c1.mp4", 0.9),)),
            BeatCandidateSelection(
                beat=_beat("too-close", 8000, 9000, 0.9), candidates=(_cand("c2", "/tmp/c2.mp4", 0.9),)
            ),
        ],
        1080,
        1920,
    )

    gap_skip = next((s for s in plan.skipped_beats if s.reason == "below minimum gap with previous insertion"), None)
    assert gap_skip is not None
    assert gap_skip.beat_id == "too-close"


def test_plan_continues_after_gap_conflict_skip():
    planner = BrollInsertionPlanner(minimum_gap_ms=8000, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 60000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(beat=_beat("first", 5000, 6000, 0.9), candidates=(_cand("c1", "/tmp/c1.mp4", 0.9),)),
            BeatCandidateSelection(
                beat=_beat("too-close", 8000, 9000, 0.9), candidates=(_cand("c2", "/tmp/c2.mp4", 0.9),)
            ),
            BeatCandidateSelection(
                beat=_beat("far-away", 30000, 31000, 0.9), candidates=(_cand("c3", "/tmp/c3.mp4", 0.9),)
            ),
        ],
        1080,
        1920,
    )

    assert any(i.beat_id == "far-away" for i in plan.insertions)


def test_plan_preserves_short_id_and_strategy_version_in_output():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68)
    timeline = SubtitleTimeline(0, 30000, (), (), 0.9)

    plan = planner.plan("my-short-007", timeline, [], 1080, 1920)

    assert plan.short_id == "my-short-007"
    assert plan.strategy_version == "broll-plan-v1"


def test_build_insertion_minimum_start_ms_is_zero_for_manual_selection():
    planner = BrollInsertionPlanner(minimum_gap_ms=500)
    timeline = SubtitleTimeline(0, 20000, (), (), 0.9)

    plan = planner.plan(
        "s",
        timeline,
        [
            BeatCandidateSelection(
                beat=_beat("manual-early", 200, 600, 0.2),
                candidates=(_cand("c", "/tmp/c.mp4", 0.9),),
                selection_source="manual_override",
                override_start_ms=0,
                override_end_ms=500,
                forced_mode="full_frame_cutaway",
            )
        ],
        1080,
        1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].start_ms == 0


def test_is_candidate_usable_default_selection_source_is_automatic():
    planner = BrollInsertionPlanner()
    strong_beat = _beat("b", 2000, 3000, 0.9)
    good_candidate = BrollCandidate(
        candidate_id="c",
        provider="local",
        discovery_source="local",
        asset_type="video",
        asset_url="https://example.com/c.mp4",
        local_path="/tmp/c.mp4",
        duration_ms=2000,
        width=720,
        height=1280,
        orientation="vertical",
        title="market",
        semantic_match=0.35,
        total_score=0.8,
    )

    result = planner.is_candidate_usable(strong_beat, good_candidate)

    assert result is True


def _beat(
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
        ),
        reasons=reasons,
    )


def _cand(
    candidate_id: str,
    local_path: str | None,
    total_score: float,
    semantic_match: float = 0.6,
) -> BrollCandidate:
    return BrollCandidate(
        candidate_id=candidate_id,
        provider="local",
        discovery_source="local",
        asset_type="video",
        asset_url="https://example.com/asset.mp4",
        local_path=local_path,
        duration_ms=2400,
        width=720,
        height=1280,
        orientation="vertical",
        title="market",
        tags=("market",),
        semantic_match=semantic_match,
        total_score=total_score,
    )

from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.domain.broll_models import BeatCandidateSelection, BeatScoreBreakdown, BrollCandidate, ImpactBeat
from src.domain.subtitle_models import SubtitleTimeline


def test_insertion_planner_records_skip_reasons_and_limits_short_clip_insertions():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 30000, (), (), 0.9)

    plan = planner.plan(
        short_id="short_0",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-1", 5000, 6500, total=0.9), _build_candidate("cand-1", "/tmp/a.mp4", 0.9)
            ),
            _build_selection(
                _build_beat("beat-2", 8000, 9400, total=0.5), _build_candidate("cand-2", "/tmp/b.mp4", 0.9)
            ),
            _build_selection(
                _build_beat("beat-3", 200, 1200, total=0.9), _build_candidate("cand-3", "/tmp/c.mp4", 0.9)
            ),
            _build_selection(_build_beat("beat-4", 12000, 13500, total=0.9), _build_candidate("cand-4", None, 0.9)),
            _build_selection(
                _build_beat("beat-5", 16000, 17500, total=0.9), _build_candidate("cand-5", "/tmp/e.mp4", 0.9)
            ),
            _build_selection(
                _build_beat("beat-6", 23000, 24500, total=0.9), _build_candidate("cand-6", "/tmp/f.mp4", 0.9)
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    assert [insertion.beat_id for insertion in plan.insertions] == ["beat-1", "beat-5"]
    assert [(skipped.beat_id, skipped.reason) for skipped in plan.skipped_beats] == [
        ("beat-3", "beat too close to clip boundary"),
        ("beat-4", "no usable asset candidate"),
        ("beat-6", "maximum insertions reached"),
        ("beat-2", "maximum insertions reached"),
    ]


def test_insertion_planner_builds_full_frame_cutaway_with_center_trim_for_automatic_beats():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 50000, (), (), 0.9)

    plan = planner.plan(
        short_id="short_1",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-cut", 4000, 5500, total=0.9), _build_candidate("cand-cut", "/tmp/cut.mp4", 0.8, 5000)
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    insertion = plan.insertions[0]
    assert insertion.mode == "full_frame_cutaway"
    assert (insertion.x, insertion.y, insertion.width, insertion.height, insertion.opacity) == (0, 0, 1080, 1920, 1.0)
    assert (insertion.asset_in_ms, insertion.asset_out_ms) == (1600, 3400)


def test_insertion_planner_builds_full_frame_cutaway_and_skips_conflicting_beats():
    planner = BrollInsertionPlanner(minimum_gap_ms=3000, beat_score_threshold=0.68, cutaway_score_threshold=0.95)
    timeline = SubtitleTimeline(0, 50000, (), (), 0.9)

    plan = planner.plan(
        short_id="short_2",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-overlay", 5000, 6500, total=0.8),
                _build_candidate("cand-overlay", "/tmp/overlay.png", 0.8, 0, "image"),
            ),
            _build_selection(
                _build_beat("beat-conflict", 7000, 8200, total=0.8),
                _build_candidate("cand-conflict", "/tmp/conflict.mp4", 0.8),
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    insertion = plan.insertions[0]
    assert insertion.mode == "full_frame_cutaway"
    assert insertion.opacity == 1.0
    assert insertion.asset_in_ms == 0
    assert insertion.asset_out_ms == insertion.end_ms - insertion.start_ms
    assert plan.skipped_beats[0].reason == "below minimum gap with previous insertion"


def test_insertion_planner_allows_earlier_beat_when_stronger_later_beat_was_selected_first():
    planner = BrollInsertionPlanner(minimum_gap_ms=3000, beat_score_threshold=0.68, cutaway_score_threshold=0.95)
    timeline = SubtitleTimeline(0, 40000, (), (), 0.9)

    late_strong_selection = BeatCandidateSelection(
        beat=_build_beat("beat-late", 28000, 30000, total=0.9),
        candidates=(_build_candidate("cand-late", "/tmp/late.mp4", 0.87),),
        priority=900,
    )
    early_support_selection = BeatCandidateSelection(
        beat=_build_beat("beat-early", 10000, 12000, total=0.35, reasons=("support beat",)),
        candidates=(_build_candidate("cand-early", "/tmp/early.mp4", 0.57),),
        priority=350,
    )

    plan = planner.plan(
        short_id="short_gap",
        timeline=timeline,
        beat_candidates=[late_strong_selection, early_support_selection],
        target_width=1080,
        target_height=1920,
    )

    assert [insertion.beat_id for insertion in plan.insertions] == ["beat-early", "beat-late"]


def test_insertion_planner_allows_three_insertions_for_longer_clips():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 36000, (), (), 0.9)

    plan = planner.plan(
        short_id="short_3",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-1", 4000, 5200, total=0.9), _build_candidate("cand-1", "/tmp/1.mp4", 0.9)
            ),
            _build_selection(
                _build_beat("beat-2", 12000, 13200, total=0.9), _build_candidate("cand-2", "/tmp/2.mp4", 0.9)
            ),
            _build_selection(
                _build_beat("beat-3", 22000, 23200, total=0.9), _build_candidate("cand-3", "/tmp/3.mp4", 0.9)
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 3


def test_insertion_planner_does_not_reuse_same_asset_within_short():
    planner = BrollInsertionPlanner(minimum_gap_ms=500, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 36000, (), (), 0.9)

    plan = planner.plan(
        short_id="short_unique_assets",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-1", 4000, 5200, total=0.9),
                _build_candidate("cand-shared", "/tmp/shared.mp4", 0.9),
            ),
            BeatCandidateSelection(
                beat=_build_beat("beat-2", 16000, 17200, total=0.9),
                candidates=(
                    _build_candidate("cand-shared-2", "/tmp/shared.mp4", 0.9),
                    _build_candidate("cand-fallback", "/tmp/fallback.mp4", 0.88),
                ),
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    assert plan.insertions[0].asset_path == "/tmp/shared.mp4"
    assert plan.insertions[1].asset_path == "/tmp/fallback.mp4"


def test_insertion_planner_honors_manual_full_frame_cutaway_even_below_threshold():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 20000, (), (), 0.95)

    plan = planner.plan(
        short_id="short_4",
        timeline=timeline,
        beat_candidates=[
            BeatCandidateSelection(
                beat=_build_beat("manual-beat", 5200, 6300, total=0.2),
                candidates=(
                    _build_candidate(
                        "cand-manual",
                        "/tmp/manual.mp4",
                        1.0,
                        discovery_source="manual_override",
                    ),
                ),
                forced_mode="full_frame_cutaway",
                override_start_ms=5000,
                override_end_ms=7600,
                priority=200,
                anchor_text="so confusing",
                selection_source="manual_override",
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    insertion = plan.insertions[0]
    assert insertion.mode == "full_frame_cutaway"
    assert insertion.discovery_source == "manual_override"
    assert insertion.anchor_text == "so confusing"
    assert insertion.start_ms == 5000
    assert insertion.end_ms == 7600


def test_insertion_planner_accepts_promoted_near_miss_with_usable_candidate():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 20000, (), (), 0.95)

    plan = planner.plan(
        short_id="short_4b",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat(
                    "beat-near-miss",
                    5200,
                    6600,
                    total=0.62,
                    reasons=("contains emotional language", "promoted near-miss high-salience beat"),
                ),
                _build_candidate("cand-near-miss", "/tmp/local.mp4", 0.8),
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].beat_id == "beat-near-miss"


def test_insertion_planner_accepts_support_beat_when_density_target_is_not_met():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 20000, (), (), 0.95)

    plan = planner.plan(
        short_id="short_support",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-support", 5200, 6600, total=0.33, reasons=("support beat",)),
                _build_candidate("cand-support", "/tmp/local.mp4", 0.57),
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].beat_id == "beat-support"
    assert plan.insertions[0].mode == "full_frame_cutaway"


def test_insertion_planner_rejects_support_beat_when_candidate_semantic_match_is_too_weak():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 20000, (), (), 0.95)

    plan = planner.plan(
        short_id="short_support_weak_match",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-support", 5200, 6600, total=0.33, reasons=("support beat",)),
                _build_candidate("cand-support", "/tmp/local.mp4", 0.61, semantic_match=0.25),
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 0
    assert plan.skipped_beats[0].reason == "no usable asset candidate"


def test_insertion_planner_allows_manual_override_near_clip_start():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.82)
    timeline = SubtitleTimeline(0, 12000, (), (), 0.95)

    plan = planner.plan(
        short_id="short_5",
        timeline=timeline,
        beat_candidates=[
            BeatCandidateSelection(
                beat=_build_beat("manual-start", 420, 1180, total=0.1),
                candidates=(
                    _build_candidate(
                        "cand-start",
                        "/tmp/manual-start.mp4",
                        1.0,
                        discovery_source="manual_override",
                    ),
                ),
                forced_mode="full_frame_cutaway",
                priority=200,
                anchor_text="job interview",
                selection_source="manual_override",
            ),
        ],
        target_width=1080,
        target_height=1920,
    )

    insertion = plan.insertions[0]
    assert insertion.start_ms == 340
    assert insertion.end_ms == 1400


def test_insertion_planner_allows_full_frame_cutaway_near_clip_end_when_window_can_be_clamped():
    planner = BrollInsertionPlanner(minimum_gap_ms=1000, beat_score_threshold=0.68, cutaway_score_threshold=0.95)
    timeline = SubtitleTimeline(0, 31000, (), (), 0.95)

    plan = planner.plan(
        short_id="short_6",
        timeline=timeline,
        beat_candidates=[
            _build_selection(
                _build_beat("beat-end", 29080, 30400, total=0.62, reasons=("promoted near-miss high-salience beat",)),
                _build_candidate("cand-end", "/tmp/end.mp4", 0.87),
            )
        ],
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].mode == "full_frame_cutaway"
    assert plan.insertions[0].end_ms <= 30750


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
        ),
        reasons=reasons,
    )


def _build_candidate(
    candidate_id: str,
    local_path: str | None,
    total_score: float,
    duration_ms: int = 2400,
    asset_type: str = "video",
    discovery_source: str = "local_manifest",
    semantic_match: float = 0.6,
) -> BrollCandidate:
    return BrollCandidate(
        candidate_id=candidate_id,
        provider="local_media",
        discovery_source=discovery_source,
        asset_type=asset_type,
        asset_url="https://example.com/asset.mp4",
        local_path=local_path,
        duration_ms=duration_ms,
        width=720,
        height=1280,
        orientation="vertical",
        title="market launch",
        tags=("market", "launch"),
        semantic_match=semantic_match,
        total_score=total_score,
    )


def _build_selection(beat: ImpactBeat, candidate: BrollCandidate) -> BeatCandidateSelection:
    return BeatCandidateSelection(beat=beat, candidates=(candidate,))

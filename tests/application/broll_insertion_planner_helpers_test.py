import pytest

from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.domain.broll_models import (
    BeatCandidateSelection,
    BeatScoreBreakdown,
    BrollCandidate,
    BrollInsertion,
    ImpactBeat,
)
from src.domain.subtitle_models import SubtitleTimeline


def test_insertion_planner_best_candidate_keeps_manual_override_semantic_bypass():
    planner = BrollInsertionPlanner()
    beat = _build_beat("beat-manual", total=0.2)
    candidate = _build_candidate("candidate-manual", "/tmp/manual.mp4", total_score=0.6, semantic_match=0.0)

    selected = planner._best_candidate(
        beat=beat,
        candidates=(candidate,),
        selection_source="manual_override",
        used_asset_keys=set(),
    )

    assert selected == candidate


def test_insertion_planner_best_candidate_skips_used_asset_and_returns_next_usable_candidate():
    planner = BrollInsertionPlanner()
    beat = _build_beat("beat-duplicate", total=0.8)
    used_candidate = _build_candidate("candidate-used", "/tmp/shared.mp4", total_score=0.9)
    fallback_candidate = _build_candidate("candidate-fallback", "/tmp/fallback.mp4", total_score=0.8)

    selected = planner._best_candidate(
        beat=beat,
        candidates=(used_candidate, fallback_candidate),
        selection_source="automatic",
        used_asset_keys={"/tmp/shared.mp4"},
    )

    assert selected == fallback_candidate


def test_insertion_planner_build_insertion_uses_overlay_geometry_and_center_trim():
    planner = BrollInsertionPlanner()
    beat = _build_beat("beat-overlay", start_ms=2000, end_ms=2600, total=0.9)
    candidate = _build_candidate("candidate-overlay", "/tmp/overlay.mp4", total_score=0.9, duration_ms=5000)
    selection = BeatCandidateSelection(
        beat=beat,
        candidates=(candidate,),
        forced_mode="overlay",
        selection_source="automatic",
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

    assert insertion.mode == "overlay"
    assert (insertion.start_ms, insertion.end_ms) == (1880, 2900)
    assert (insertion.asset_in_ms, insertion.asset_out_ms) == (1990, 3010)
    assert (insertion.x, insertion.y, insertion.width, insertion.height, insertion.opacity) == (
        97,
        planner.overlay_top_y,
        885,
        537,
        0.96,
    )


def test_insertion_planner_build_insertion_keeps_minimum_asset_duration_for_short_override_window():
    planner = BrollInsertionPlanner()
    beat = _build_beat("beat-override", start_ms=5000, end_ms=5200, total=0.2)
    candidate = _build_candidate(
        "candidate-image", "/tmp/still.png", total_score=0.9, asset_type="image", duration_ms=0
    )
    selection = BeatCandidateSelection(
        beat=beat,
        candidates=(candidate,),
        forced_mode="full_frame_cutaway",
        override_start_ms=5000,
        override_end_ms=5200,
        selection_source="manual_override",
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

    assert (insertion.start_ms, insertion.end_ms) == (5000, 5200)
    assert (insertion.asset_in_ms, insertion.asset_out_ms) == (0, 300)


@pytest.mark.parametrize(
    ("asset_type", "candidate_duration_ms", "desired_duration_ms", "expected"),
    [
        ("image", 0, 900, (0, 900)),
        ("video", 700, 900, (0, 700)),
        ("video", 2500, 900, (800, 1700)),
    ],
)
def test_insertion_planner_asset_trim_handles_images_shorter_assets_and_center_trims(
    asset_type,
    candidate_duration_ms,
    desired_duration_ms,
    expected,
):
    planner = BrollInsertionPlanner()
    candidate = _build_candidate(
        "candidate-trim",
        "/tmp/asset.mp4",
        total_score=0.9,
        asset_type=asset_type,
        duration_ms=candidate_duration_ms,
    )

    trim = planner._asset_trim(candidate, desired_duration_ms)

    assert trim == expected


@pytest.mark.parametrize(
    ("insertion_spec", "minimum_gap_ms", "expected"),
    [
        (("insert-gap", 2500, 3000), 500, False),
        (("insert-close", 2400, 3000), 500, True),
        (("insert-overlap", 1800, 2600), 500, True),
    ],
)
def test_insertion_planner_conflicts_only_when_gap_is_below_threshold(insertion_spec, minimum_gap_ms, expected):
    insertion = _build_insertion(*insertion_spec)
    existing = [_build_insertion("insert-existing", 1000, 2000)]

    conflict = BrollInsertionPlanner._conflicts_with_existing(insertion, existing, minimum_gap_ms)

    assert conflict is expected


@pytest.mark.parametrize(
    ("beat_spec", "expected"),
    [
        (("beat-strong", 2000, 3200, 0.68, ("strong beat",)), 0.30),
        (("beat-support", 2000, 3200, 0.30, ("support beat",)), 0.45),
        (
            (
                "beat-promoted",
                2000,
                3200,
                0.40,
                ("support beat", "promoted near-miss high-salience beat"),
            ),
            0.30,
        ),
    ],
)
def test_insertion_planner_semantic_floor_distinguishes_strong_support_and_promoted_beats(beat_spec, expected):
    planner = BrollInsertionPlanner()
    beat = _build_beat(*beat_spec)

    assert planner._semantic_floor_for_beat(beat) == expected


def test_insertion_planner_candidate_usability_applies_correct_semantic_floor_by_selection_source():
    planner = BrollInsertionPlanner()
    strong_beat = _build_beat("beat-strong", total=0.68)
    support_beat = _build_beat("beat-support", total=0.30, reasons=("support beat",))
    manual_candidate = _build_candidate("candidate-manual", "/tmp/manual.mp4", total_score=0.55, semantic_match=0.0)
    automatic_candidate = _build_candidate(
        "candidate-automatic", "/tmp/automatic.mp4", total_score=0.55, semantic_match=0.30
    )

    assert planner.is_candidate_usable(strong_beat, automatic_candidate, selection_source="automatic") is True
    assert planner.is_candidate_usable(support_beat, automatic_candidate, selection_source="automatic") is False
    assert planner.is_candidate_usable(strong_beat, manual_candidate, selection_source="manual_override") is True


@pytest.mark.parametrize(
    ("current_insertions", "target_insertions", "expected"),
    [
        (0, 1, True),
        (1, 1, False),
    ],
)
def test_insertion_planner_support_insertion_requires_remaining_capacity(
    current_insertions, target_insertions, expected
):
    planner = BrollInsertionPlanner()
    beat = _build_beat("beat-support", total=planner.support_beat_score_threshold, reasons=("support beat",))
    candidate = _build_candidate("candidate-support", "/tmp/support.mp4", total_score=0.9)

    supported = planner._supports_automatic_insertion(
        beat=beat,
        candidate=candidate,
        current_insertions=current_insertions,
        target_insertions=target_insertions,
    )

    assert supported is expected


def test_insertion_planner_window_boundaries_accept_exact_limits_and_reject_outside_values():
    timeline = SubtitleTimeline(0, 12000, (), (), 0.95)

    assert BrollInsertionPlanner._window_inside_boundaries(500, 11750, timeline, "overlay") is True
    assert BrollInsertionPlanner._window_inside_boundaries(499, 11750, timeline, "overlay") is False
    assert BrollInsertionPlanner._window_inside_boundaries(500, 11751, timeline, "overlay") is False


def test_insertion_planner_clamp_window_uses_fallback_when_end_is_not_after_start():
    window = BrollInsertionPlanner._clamp_window(
        start_ms=700,
        end_ms=700,
        fallback_start_ms=820,
        fallback_end_ms=1200,
        minimum_start_ms=500,
        maximum_end_ms=2000,
    )

    assert window == (820, 1200)


def _build_beat(
    beat_id: str,
    start_ms: int = 2000,
    end_ms: int = 3200,
    total: float = 0.9,
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
    asset_type: str = "video",
    duration_ms: int = 2400,
    semantic_match: float = 0.6,
) -> BrollCandidate:
    return BrollCandidate(
        candidate_id=candidate_id,
        provider="local_media",
        discovery_source="local_manifest",
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


def _build_insertion(insertion_id: str, start_ms: int, end_ms: int) -> BrollInsertion:
    return BrollInsertion(
        insertion_id=insertion_id,
        beat_id=f"beat-{insertion_id}",
        mode="full_frame_cutaway",
        asset_provider="local_media",
        asset_path="/tmp/asset.mp4",
        start_ms=start_ms,
        end_ms=end_ms,
        source_beat_score=0.9,
        candidate_score=0.9,
        x=0,
        y=0,
        width=1080,
        height=1920,
        opacity=1.0,
        asset_in_ms=0,
        asset_out_ms=end_ms - start_ms,
        subtitle_safe=True,
        discovery_source="local_manifest",
        anchor_text=None,
    )

from typing import cast

from src.application.broll.broll_insertion_planner import BrollInsertionPlanner
from src.domain.broll_models import BeatScoreBreakdown, BrollCandidate, ImpactBeat
from src.domain.subtitle_models import SubtitleTimeline


def test_broll_insertion_planner_uses_expected_defaults_when_none_is_provided():
    planner = BrollInsertionPlanner(
        minimum_gap_ms=None,
        beat_score_threshold=None,
        cutaway_score_threshold=None,
        minimum_candidate_score=None,
        overlay_top_y=None,
        support_beat_score_threshold=None,
        automatic_candidate_semantic_match_threshold=None,
        support_candidate_semantic_match_threshold=None,
    )

    assert planner.minimum_gap_ms == 4500
    assert planner.beat_score_threshold == 0.68
    assert planner.cutaway_score_threshold == 0.82
    assert planner.minimum_candidate_score == 0.55
    assert planner.overlay_top_y == 120
    assert planner.support_beat_score_threshold == 0.30
    assert planner.automatic_candidate_semantic_match_threshold == 0.30
    assert planner.support_candidate_semantic_match_threshold == 0.45


def test_broll_insertion_planner_uses_automatic_selection_source_when_none_is_provided():
    planner = BrollInsertionPlanner()

    usable = planner.is_candidate_usable(
        beat=_build_beat(total=0.9),
        candidate=_build_candidate(semantic_match=0.31),
        selection_source=None,
    )

    assert usable is True


def test_broll_insertion_planner_mode_resolution_requires_beat_and_candidate():
    candidate = _build_candidate()
    beat = _build_beat()

    _assert_raises_value_error(lambda: BrollInsertionPlanner._mode_for_candidate(cast(ImpactBeat, None), candidate))
    _assert_raises_value_error(lambda: BrollInsertionPlanner._mode_for_candidate(beat, cast(BrollCandidate, None)))


def test_broll_insertion_planner_boundary_helpers_reject_unknown_modes():
    timeline = SubtitleTimeline(0, 12000, (), (), 0.95)

    _assert_raises_value_error(lambda: BrollInsertionPlanner._minimum_start_ms_for_mode("unknown"))
    _assert_raises_value_error(lambda: BrollInsertionPlanner._maximum_end_ms_for_mode("unknown", timeline.duration_ms))
    _assert_raises_value_error(lambda: BrollInsertionPlanner._window_inside_boundaries(500, 1000, timeline, "unknown"))


def test_broll_insertion_planner_support_insertion_rejects_missing_candidate():
    planner = BrollInsertionPlanner()

    supported = planner._supports_automatic_insertion(
        beat=_build_beat(total=0.9),
        candidate=cast(BrollCandidate, None),
        current_insertions=0,
        target_insertions=1,
    )

    assert supported is False


def _assert_raises_value_error(callback):
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("Expected ValueError")


def _build_beat(total: float = 0.9) -> ImpactBeat:
    return ImpactBeat(
        beat_id="beat-1",
        text="market launch",
        start_ms=1000,
        end_ms=2200,
        duration_ms=1200,
        timing_mode="aligned",
        word_confidence_avg=0.9,
        cue_quality_score=0.95,
        scores=BeatScoreBreakdown(
            total=total,
            visualizability=0.8,
            emotional_load=0.7,
            contrast=0.6,
            narrative_turn=0.5,
            verbal_force=0.5,
            duration_fit=0.9,
            timing_confidence=0.95,
            semantic_salience=0.8,
        ),
        reasons=("strong beat",),
    )


def _build_candidate(semantic_match: float = 0.8) -> BrollCandidate:
    return BrollCandidate(
        candidate_id="candidate-1",
        provider="local_media",
        discovery_source="local_manifest",
        asset_type="video",
        asset_url="https://example.com/asset.mp4",
        local_path="/tmp/asset.mp4",
        duration_ms=2400,
        width=720,
        height=1280,
        orientation="vertical",
        title="market launch",
        tags=("market", "launch"),
        semantic_match=semantic_match,
        total_score=0.9,
    )

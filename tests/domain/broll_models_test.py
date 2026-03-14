from src.domain.broll_models import (
    BeatScoreBreakdown,
    BrollCandidate,
    BrollInsertion,
    ImpactBeat,
    ShortEditingPlan,
    SkippedBeat,
)


def test_broll_models_to_dict_keep_expected_shape():
    scores = BeatScoreBreakdown(
        total=0.9,
        visualizability=0.8,
        emotional_load=0.4,
        contrast=0.3,
        narrative_turn=0.2,
        verbal_force=0.5,
        duration_fit=1.0,
        timing_confidence=0.85,
    )
    beat = ImpactBeat(
        beat_id="beat-0001",
        text="launch the product today",
        start_ms=1000,
        end_ms=2400,
        duration_ms=1400,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.81,
        cue_quality_score=0.84,
        scores=scores,
        reasons=("contains concrete or visual anchors",),
    )
    candidate = BrollCandidate(
        candidate_id="cand-1",
        provider="pixabay",
        discovery_source="pixabay",
        asset_type="video",
        asset_url="https://example.com/video.mp4",
        local_path="outputs/.cache/video.mp4",
        duration_ms=3000,
        width=1080,
        height=1920,
        orientation="vertical",
        title="office launch",
        tags=("office", "launch"),
        total_score=0.77,
    )
    insertion = BrollInsertion(
        insertion_id="insert-0001",
        beat_id="beat-0001",
        mode="overlay",
        asset_provider="pixabay",
        asset_path="outputs/.cache/video.mp4",
        start_ms=900,
        end_ms=2500,
        source_beat_score=0.9,
        candidate_score=0.77,
        x=100,
        y=120,
        width=800,
        height=520,
        opacity=0.96,
        asset_in_ms=200,
        asset_out_ms=1800,
    )
    plan = ShortEditingPlan(
        short_id="short_0",
        enabled=True,
        strategy_version="broll-plan-v1",
        insertions=(insertion,),
    )

    assert beat.to_dict()["scores"]["timing_confidence"] == 0.85
    assert candidate.to_dict()["discovery_source"] == "pixabay"
    assert candidate.to_dict()["tags"] == ["office", "launch"]
    assert insertion.to_dict()["placement"]["opacity"] == 0.96
    assert plan.to_dict()["insertions"][0]["trim"]["asset_out_ms"] == 1800


def test_broll_models_include_optional_anchor_and_skipped_beats():
    insertion = BrollInsertion(
        insertion_id="insert-0002",
        beat_id="beat-0002",
        mode="full_frame_cutaway",
        asset_provider="manual_override",
        asset_path="inputs/broll/library/portrait/woman-smiling.mp4",
        start_ms=1200,
        end_ms=2600,
        source_beat_score=1.0,
        candidate_score=1.0,
        x=0,
        y=0,
        width=1080,
        height=1920,
        opacity=1.0,
        asset_in_ms=0,
        asset_out_ms=1400,
        anchor_text="woman smiling",
    )
    plan = ShortEditingPlan(
        short_id="short_9",
        enabled=True,
        strategy_version="broll-plan-v1",
        insertions=(insertion,),
        skipped_beats=(SkippedBeat(beat_id="beat-0003", reason="no_candidate"),),
    )

    payload = plan.to_dict()

    assert payload["insertions"][0]["anchor_text"] == "woman smiling"
    assert payload["skipped_beats"] == [{"beat_id": "beat-0003", "reason": "no_candidate"}]

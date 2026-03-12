from src.application.broll.manual_override_resolver import ManualBrollOverrideResolver
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
from src.domain.manual_broll_overrides import ManualBrollOverride
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline


def test_manual_override_resolver_matches_detected_beat_and_builds_manual_candidate(tmp_path):
    asset = tmp_path / "confusing.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short_2",
        anchor_text="so confusing",
        asset_path=str(asset),
        mode="full_frame_cutaway",
        priority=250,
    )
    detected_beat = _build_detected_beat("It's so confusing with all those negatives.", 2400, 3920, total=0.32)

    selections = resolver.resolve(
        short_id="short_2",
        timeline=_build_confusing_timeline(),
        detected_beats=[detected_beat],
        overrides=(override,),
    )

    assert len(selections) == 1
    selection = selections[0]
    assert selection.beat.beat_id == detected_beat.beat_id
    assert selection.forced_mode == "full_frame_cutaway"
    assert selection.selection_source == "manual_override"
    assert selection.candidates[0].discovery_source == "manual_override"
    assert selection.candidates[0].local_path == str(asset)


def test_manual_override_resolver_creates_synthetic_beat_when_detector_misses_phrase(tmp_path):
    asset = tmp_path / "job-interview.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short_5",
        anchor_text="job interview",
        asset_path=str(asset),
        mode="full_frame_cutaway",
    )

    selections = resolver.resolve(
        short_id="short_5",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(override,),
    )

    assert len(selections) == 1
    selection = selections[0]
    assert selection.beat.beat_id == "manual-beat-0001"
    assert selection.beat.text == "job interview"
    assert selection.beat.start_ms == 3000
    assert selection.beat.end_ms == 3900
    assert selection.candidates[0].asset_type == "video"
    assert selection.candidates[0].total_score == 1.0


def _build_detected_beat(text: str, start_ms: int, end_ms: int, total: float) -> ImpactBeat:
    return ImpactBeat(
        beat_id="beat-0001",
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.92,
        cue_quality_score=0.94,
        scores=BeatScoreBreakdown(
            total=total,
            visualizability=0.4,
            emotional_load=0.5,
            contrast=0.4,
            narrative_turn=0.4,
            verbal_force=0.5,
            duration_fit=0.9,
            timing_confidence=0.95,
            semantic_salience=0.5,
        ),
        reasons=("test beat",),
    )


def _build_confusing_timeline() -> SubtitleTimeline:
    return SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="It's so confusing with all those negatives.",
                start_ms=2000,
                end_ms=3920,
                timing_mode="reconciled_asr",
                quality_score=0.96,
                words=(
                    ProjectedWord("It's", 2000, 2280, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("so", 2280, 2560, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("confusing", 2560, 2840, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("with", 2840, 3120, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("all", 3120, 3400, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("those", 3400, 3680, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("negatives.", 3680, 3920, 0.94, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.96,
    )


def _build_job_interview_timeline() -> SubtitleTimeline:
    return SubtitleTimeline(
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

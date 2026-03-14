import pytest

from src.application.broll.manual_override_resolver import ManualBrollOverrideResolver
from src.domain.manual_broll_overrides import ManualBrollOverride
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline


def test_manual_override_resolver_builds_complete_video_candidate_and_word_matched_beat(tmp_path):
    asset = tmp_path / "job_interview-vertical.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()

    selections = resolver.resolve(
        short_id="short_13",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(_build_override("short_13", "job interview", str(asset)),),
    )

    assert len(selections) == 1
    selection = selections[0]
    candidate = selection.candidates[0]
    assert selection.beat.start_ms == 3000
    assert selection.beat.end_ms == 3900
    assert selection.beat.duration_ms == 900
    assert selection.beat.timing_mode == "reconciled_asr"
    assert selection.beat.word_confidence_avg == 0.9
    assert selection.beat.cue_quality_score == 0.93
    assert selection.beat.reasons == ("manual override anchor matched",)
    assert candidate.candidate_id == "manual-job-interview-job_interview-vertical"
    assert candidate.provider == "manual_override"
    assert candidate.discovery_source == "manual_override"
    assert candidate.asset_type == "video"
    assert candidate.asset_url == str(asset)
    assert candidate.local_path == str(asset)
    assert candidate.width == 0
    assert candidate.height == 0
    assert candidate.orientation == "vertical"
    assert candidate.title == "job interview vertical"
    assert candidate.tags == ("job", "interview")
    assert candidate.semantic_match == 1.0
    assert candidate.visual_fit == 1.0
    assert candidate.duration_fit == 1.0
    assert candidate.orientation_fit == 1.0
    assert candidate.technical_quality == 0.8
    assert candidate.total_score == 1.0


def test_manual_override_resolver_builds_complete_image_candidate_and_cue_matched_beat(tmp_path):
    asset = tmp_path / "still_frame.png"
    asset.write_bytes(b"image")
    resolver = ManualBrollOverrideResolver()
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=14000,
        cues=(
            ProjectedCue(
                cue_id="cue-image",
                speaker="Speaker 1",
                original_text="I walked in already nervous about the meeting.",
                start_ms=4000,
                end_ms=5200,
                timing_mode="reconciled_asr",
                quality_score=0.91,
                words=(),
            ),
        ),
        segments=(),
        quality_score=0.91,
    )

    selections = resolver.resolve(
        short_id="short_14",
        timeline=timeline,
        detected_beats=[],
        overrides=(_build_override("short_14", "already nervous", str(asset)),),
    )

    assert len(selections) == 1
    selection = selections[0]
    candidate = selection.candidates[0]
    assert selection.beat.start_ms == 4000
    assert selection.beat.end_ms == 5200
    assert selection.beat.duration_ms == 1200
    assert selection.beat.timing_mode == "reconciled_asr"
    assert selection.beat.word_confidence_avg == 0.0
    assert selection.beat.cue_quality_score == 0.91
    assert selection.beat.reasons == ("manual override cue matched",)
    assert candidate.asset_type == "image"
    assert candidate.asset_url == str(asset)
    assert candidate.local_path == str(asset)
    assert candidate.width == 1080
    assert candidate.height == 1080
    assert candidate.orientation == "square"
    assert candidate.title == "still frame"
    assert candidate.orientation_fit == 0.8


@pytest.mark.parametrize("stem", ["clip-vertical", "clip-portrait", "clip-reel", "clip-short", "clip-9x16"])
def test_manual_override_resolver_marks_keyword_video_assets_as_vertical(tmp_path, stem):
    asset = tmp_path / f"{stem}.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()

    selections = resolver.resolve(
        short_id="short_15",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(_build_override("short_15", "job interview", str(asset)),),
    )

    assert len(selections) == 1
    assert selections[0].candidates[0].orientation == "vertical"


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


def _build_override(short_id: str, anchor_text: str, asset_path: str) -> ManualBrollOverride:
    return ManualBrollOverride(
        short_id=short_id,
        anchor_text=anchor_text,
        asset_path=asset_path,
        mode="full_frame_cutaway",
        priority=100,
        active=True,
    )

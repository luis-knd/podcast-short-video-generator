from src.application.broll.manual_override_resolver import ManualBrollOverrideResolver
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
from src.domain.manual_broll_overrides import ManualBrollOverride
from src.domain.subtitle_models import ProjectedCue, SubtitleTimeline
from tests.application.manual_override_resolver_test import _build_job_interview_timeline


def test_manual_override_resolver_keeps_explicit_override_window_on_selection(tmp_path):
    asset = tmp_path / "manual-window.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short-window",
        anchor_text="job interview",
        asset_path=str(asset),
        mode="full_frame_cutaway",
        start_ms=460,
        end_ms=1800,
        priority=200,
    )

    selections = resolver.resolve(
        short_id="short-window",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(override,),
    )

    assert len(selections) == 1
    assert selections[0].override_start_ms == 460
    assert selections[0].override_end_ms == 1800


def test_manual_override_resolver_builds_video_candidate_with_zero_duration(tmp_path):
    asset = tmp_path / "job_interview.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short-duration",
        anchor_text="job interview",
        asset_path=str(asset),
        mode="full_frame_cutaway",
    )

    selections = resolver.resolve(
        short_id="short-duration",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(override,),
    )

    assert len(selections) == 1
    assert selections[0].candidates[0].duration_ms == 0


def test_manual_override_resolver_cue_match_uses_override_anchor_text_verbatim(tmp_path):
    asset = tmp_path / "cue-still.png"
    asset.write_bytes(b"image")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short-cue",
        anchor_text="already nervous",
        asset_path=str(asset),
        mode="full_frame_cutaway",
    )

    selections = resolver.resolve(
        short_id="short-cue",
        timeline=SubtitleTimeline(
            interval_start_ms=0,
            interval_end_ms=14000,
            cues=(
                ProjectedCue(
                    cue_id="cue-1",
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
        ),
        detected_beats=[],
        overrides=(override,),
    )

    assert len(selections) == 1
    assert selections[0].beat.text == "already nervous"


def test_manual_override_resolver_orientation_prefers_vertical_keywords_even_for_images(tmp_path):
    asset = tmp_path / "teaser-short.png"
    asset.write_bytes(b"image")
    resolver = ManualBrollOverrideResolver()

    assert resolver._orientation(asset) == "vertical"


def test_manual_override_resolver_orientation_distinguishes_square_images_from_unknown_videos(tmp_path):
    image_asset = tmp_path / "still-frame.png"
    video_asset = tmp_path / "clip.mp4"
    image_asset.write_bytes(b"image")
    video_asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()

    assert resolver._orientation(image_asset) == "square"
    assert resolver._orientation(video_asset) == "unknown"


def test_manual_override_resolver_asset_type_distinguishes_images_from_videos(tmp_path):
    image_asset = tmp_path / "still-frame.webp"
    video_asset = tmp_path / "clip.mp4"
    image_asset.write_bytes(b"image")
    video_asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()

    assert resolver._asset_type(image_asset) == "image"
    assert resolver._asset_type(video_asset) == "video"


def test_manual_override_resolver_build_manual_candidate_keeps_expected_manual_metadata(tmp_path):
    asset = tmp_path / "still-frame.png"
    asset.write_bytes(b"image")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short-metadata",
        anchor_text="already nervous",
        asset_path=str(asset),
        mode="full_frame_cutaway",
        priority=300,
    )

    candidate = resolver._build_manual_candidate(override, asset)

    assert candidate.candidate_id == "manual-already-nervous-still-frame"
    assert candidate.provider == "manual_override"
    assert candidate.discovery_source == "manual_override"
    assert candidate.asset_type == "image"
    assert candidate.asset_url == str(asset)
    assert candidate.local_path == str(asset)
    assert candidate.duration_ms == 0
    assert candidate.width == 1080
    assert candidate.height == 1080
    assert candidate.orientation == "square"
    assert candidate.title == "still frame"
    assert candidate.tags == ("already", "nervous")
    assert candidate.semantic_match == 1.0
    assert candidate.visual_fit == 1.0
    assert candidate.duration_fit == 1.0
    assert candidate.orientation_fit == 0.8
    assert candidate.technical_quality == 0.8
    assert candidate.total_score == 1.0


def test_manual_override_resolver_matches_shortest_detected_beat_then_earliest_start():
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short-match",
        anchor_text="job interview",
        asset_path="/tmp/unused.mp4",
        mode="full_frame_cutaway",
    )
    beats = [
        _build_detected_beat("The job interview started.", 3200, 4100),
        _build_detected_beat("Another job interview moment.", 3000, 3900),
        _build_detected_beat("Longer job interview section.", 2800, 4200),
    ]

    matched = resolver._match_detected_beat(override, beats)

    assert matched is beats[1]


def test_manual_override_resolver_returns_selections_sorted_by_priority_then_start_time(tmp_path):
    first_asset = tmp_path / "already-nervous.mp4"
    second_asset = tmp_path / "job-interview.mp4"
    first_asset.write_bytes(b"video")
    second_asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()

    selections = resolver.resolve(
        short_id="short-sort",
        timeline=_build_job_interview_timeline(),
        detected_beats=[
            _build_detected_beat("already nervous", 2500, 3200),
            _build_detected_beat("job interview", 3000, 3900),
        ],
        overrides=(
            ManualBrollOverride(
                short_id="short-sort",
                anchor_text="job interview",
                asset_path=str(second_asset),
                mode="full_frame_cutaway",
                priority=200,
            ),
            ManualBrollOverride(
                short_id="short-sort",
                anchor_text="already nervous",
                asset_path=str(first_asset),
                mode="full_frame_cutaway",
                priority=200,
            ),
        ),
    )

    assert [selection.anchor_text for selection in selections] == ["already nervous", "job interview"]


def _build_detected_beat(text: str, start_ms: int, end_ms: int) -> ImpactBeat:
    return ImpactBeat(
        beat_id=f"beat-{start_ms}",
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.9,
        cue_quality_score=0.95,
        scores=BeatScoreBreakdown(
            total=0.8,
            visualizability=0.8,
            emotional_load=0.4,
            contrast=0.2,
            narrative_turn=0.1,
            verbal_force=0.3,
            duration_fit=0.9,
            timing_confidence=0.95,
            semantic_salience=0.8,
        ),
        reasons=("detected",),
    )

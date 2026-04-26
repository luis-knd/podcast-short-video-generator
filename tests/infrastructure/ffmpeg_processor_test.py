from typing import cast
from unittest.mock import MagicMock, call, patch

import pytest

from src.domain.broll_models import BrollInsertion, ShortEditingPlan
from src.domain.entities import Video
from src.domain.exceptions import InfrastructureError
from src.domain.value_objects import TimeInterval, VideoFormat
from src.infrastructure.broll.providers import LocalMediaProvider
from src.infrastructure.ffmpeg_processor import FFmpegVideoProcessor

_INPUT_VIDEO_FILEPATH = "in_video.mp4"
_SUBTITLES_FILEPATH = "subs.srt"
_OUTPUT_FILE_PATH = "out.mp4"
_OUTRO_FILEPATH = "inputs/outroShort.mp4"
_ASSET_IMAGE_PATH = "asset.png"
_HALF_WIDTH_CROP = "in_w/2"
_VERTICAL_CENTER_CROP = "(in_h-out_h)/2"
_PAD_CENTER_X = "(ow-iw)/2"
_PAD_CENTER_Y = "(oh-ih)/2"


def _build_default_video() -> Video:
    return Video(filepath=_INPUT_VIDEO_FILEPATH, subtitles_filepath=_SUBTITLES_FILEPATH)


def _build_default_interval() -> TimeInterval:
    return TimeInterval(start_seconds=10.0, end_seconds=20.0)


def _build_split_input(prefix: str):
    mock_input = MagicMock(name=f"{prefix}_input")
    mock_video_stream = MagicMock(name=f"{prefix}_video_stream")
    mock_audio_stream = MagicMock(name=f"{prefix}_audio_stream")
    mock_left = MagicMock(name=f"{prefix}_left")
    mock_right = MagicMock(name=f"{prefix}_right")

    mock_input.video = mock_video_stream
    mock_input.audio = mock_audio_stream
    mock_left.filter.return_value = mock_left
    mock_right.filter.return_value = mock_right
    mock_video_stream.split.return_value = [mock_left, mock_right]
    return mock_input, mock_audio_stream, mock_left, mock_right


def _build_outro_input():
    mock_outro_input = MagicMock(name="outro_input")
    mock_outro_video = MagicMock(name="outro_video")
    mock_outro_audio = MagicMock(name="outro_audio")

    mock_outro_input.video = mock_outro_video
    mock_outro_input.audio = mock_outro_audio
    mock_outro_video.filter.return_value = mock_outro_video
    mock_outro_audio.filter.return_value = mock_outro_audio
    return mock_outro_input, mock_outro_video, mock_outro_audio


def _build_mock_output(mock_ffmpeg):
    mock_output = MagicMock(name="output")
    mock_global_args = MagicMock(name="global_args")
    mock_ffmpeg.output.return_value = mock_output
    mock_output.global_args.return_value = mock_global_args
    return mock_output, mock_global_args


def _build_concat_result(video_output: str = "concat_video", audio_output: str = "concat_audio"):
    mock_concat_node = MagicMock(name="concat_node")
    mock_concat_node.__getitem__.side_effect = [video_output, audio_output]
    mock_concat_result = MagicMock(name="concat_result")
    mock_concat_result.node = mock_concat_node
    return mock_concat_result


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_generates_short(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.build_timeline.return_value = MagicMock()
    processor = FFmpegVideoProcessor()

    # Use a challenging path to test ASS path escaping
    video = _build_default_video()
    interval = _build_default_interval()
    target_format = VideoFormat.youtube_shorts()
    output_filepath = "C:\\fake:dir\\out.mp4"

    mock_input, mock_audio_stream, mock_left, mock_right = _build_split_input(prefix="main")
    mock_ffmpeg.input.return_value = mock_input

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]

    _, mock_global_args = _build_mock_output(mock_ffmpeg)

    # Act
    result = processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath=output_filepath,
    )

    # Assert basic result properties
    assert result.filepath == output_filepath
    assert result.interval == interval
    assert result.format == target_format

    mock_ffmpeg.input.assert_called_once_with(_INPUT_VIDEO_FILEPATH, ss=10.0, t=10.0)

    mock_left.filter.assert_has_calls(
        [
            call("crop", _HALF_WIDTH_CROP, "in_h", "in_w/16", "0"),
            call("scale", 1080, "-1"),
            call("crop", 1080, 960, "0", _VERTICAL_CENTER_CROP),
        ]
    )
    mock_right.filter.assert_has_calls(
        [
            call("crop", _HALF_WIDTH_CROP, "in_h", "in_w/2-in_w/16", "0"),
            call("scale", 1080, "-1"),
            call("crop", 1080, 960, "0", _VERTICAL_CENTER_CROP),
        ]
    )
    assert mock_left.filter.call_args_list[2].args[2] == 960
    assert isinstance(mock_left.filter.call_args_list[2].args[2], int)
    assert mock_right.filter.call_args_list[2].args[2] == 960
    assert isinstance(mock_right.filter.call_args_list[2].args[2], int)

    ass_escaped = "C\\:/fake\\:dir/out.ass"
    mock_ffmpeg.filter.assert_has_calls(
        [call([mock_left, mock_right], "vstack"), call(mock_vstack, "ass", ass_escaped)]
    )
    mock_ffmpeg.output.assert_called_once_with(
        mock_ass,
        mock_audio_stream,
        output_filepath,
        vcodec="libx264",
        acodec="aac",
        preset="fast",
    )
    mock_global_args.run.assert_called_once()
    mock_subtitle_processor.build_timeline.assert_called_once_with(
        srt_filepath=_SUBTITLES_FILEPATH,
        interval=interval,
        output_ass_filepath="C:\\fake:dir\\out.ass",
        media_filepath=_INPUT_VIDEO_FILEPATH,
    )
    mock_subtitle_processor.write_ass_from_timeline.assert_called_once()


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_generates_short_with_outro_and_fades(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.build_timeline.return_value = MagicMock()
    processor = FFmpegVideoProcessor()

    video = _build_default_video()
    interval = _build_default_interval()
    target_format = VideoFormat.youtube_shorts()

    mock_base_input, mock_base_audio_stream, _, _ = _build_split_input(prefix="base")
    mock_outro_input, mock_outro_video, mock_outro_audio = _build_outro_input()
    mock_ffmpeg.input.side_effect = [mock_base_input, mock_outro_input]

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]

    mock_video_faded = MagicMock(name="video_faded")
    mock_audio_faded = MagicMock(name="audio_faded")
    mock_ass.filter.return_value = mock_video_faded
    mock_base_audio_stream.filter.return_value = mock_audio_faded

    mock_ffmpeg.concat.return_value = _build_concat_result()
    _, mock_global_args = _build_mock_output(mock_ffmpeg)

    # Act
    result = processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath=_OUTPUT_FILE_PATH,
        outro_filepath=_OUTRO_FILEPATH,
        fade_duration=0.7,
    )

    # Assert
    assert result.filepath == _OUTPUT_FILE_PATH
    assert result.interval == interval
    mock_ffmpeg.input.assert_has_calls(
        [
            call(_INPUT_VIDEO_FILEPATH, ss=10.0, t=10.0),
            call(_OUTRO_FILEPATH),
        ]
    )
    mock_ass.filter.assert_called_once_with("fade", type="out", start_time=9.3, duration=0.7)
    mock_base_audio_stream.filter.assert_called_once_with("afade", type="out", start_time=9.3, duration=0.7)
    assert mock_outro_video.filter.call_args_list == [
        call("scale", 1080, 1920, force_original_aspect_ratio="decrease"),
        call("pad", 1080, 1920, _PAD_CENTER_X, _PAD_CENTER_Y),
        call("fade", type="in", start_time=0, duration=0.7),
    ]
    assert mock_outro_audio.filter.call_args_list == [call("afade", type="in", start_time=0, duration=0.7)]
    mock_ffmpeg.concat.assert_called_once_with(
        mock_video_faded,
        mock_audio_faded,
        mock_outro_video,
        mock_outro_audio,
        v=1,
        a=1,
    )
    mock_ffmpeg.output.assert_called_once_with(
        "concat_video",
        "concat_audio",
        _OUTPUT_FILE_PATH,
        vcodec="libx264",
        acodec="aac",
        preset="fast",
    )
    mock_global_args.run.assert_called_once()


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_uses_default_fade_duration_when_outro_is_enabled(mock_subtitle_processor_class, mock_ffmpeg):
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.build_timeline.return_value = MagicMock()
    processor = FFmpegVideoProcessor()

    video = _build_default_video()
    interval = _build_default_interval()
    target_format = VideoFormat.youtube_shorts()

    mock_base_input, mock_base_audio_stream, _, _ = _build_split_input(prefix="base")
    mock_outro_input, _, _ = _build_outro_input()
    mock_ffmpeg.input.side_effect = [mock_base_input, mock_outro_input]

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]
    mock_video_faded = MagicMock(name="video_faded")
    mock_audio_faded = MagicMock(name="audio_faded")
    mock_ass.filter.return_value = mock_video_faded
    mock_base_audio_stream.filter.return_value = mock_audio_faded

    mock_ffmpeg.concat.return_value = _build_concat_result()
    _build_mock_output(mock_ffmpeg)

    processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath=_OUTPUT_FILE_PATH,
        outro_filepath=_OUTRO_FILEPATH,
    )

    mock_ass.filter.assert_called_once_with("fade", type="out", start_time=9.3, duration=0.7)
    mock_base_audio_stream.filter.assert_called_once_with("afade", type="out", start_time=9.3, duration=0.7)
    mock_ffmpeg.output.assert_called_once_with(
        "concat_video",
        "concat_audio",
        _OUTPUT_FILE_PATH,
        vcodec="libx264",
        acodec="aac",
        preset="fast",
    )


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_generates_short_with_outro_and_zero_fade(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.build_timeline.return_value = MagicMock()
    processor = FFmpegVideoProcessor()

    video = _build_default_video()
    interval = _build_default_interval()
    target_format = VideoFormat.youtube_shorts()

    mock_base_input, mock_base_audio_stream, _, _ = _build_split_input(prefix="base")
    mock_outro_input, mock_outro_video, mock_outro_audio = _build_outro_input()
    mock_ffmpeg.input.side_effect = [mock_base_input, mock_outro_input]

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]
    mock_ffmpeg.concat.return_value = _build_concat_result()
    _build_mock_output(mock_ffmpeg)

    # Act
    processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath=_OUTPUT_FILE_PATH,
        outro_filepath=_OUTRO_FILEPATH,
        fade_duration=0.0,
    )

    # Assert no fade is applied when fade duration is 0
    assert call("fade", type="out", start_time=10.0, duration=0.0) not in mock_ass.filter.call_args_list
    assert not any(args[0] == "afade" for args, _ in mock_base_audio_stream.filter.call_args_list)
    assert mock_outro_video.filter.call_args_list == [
        call("scale", 1080, 1920, force_original_aspect_ratio="decrease"),
        call("pad", 1080, 1920, _PAD_CENTER_X, _PAD_CENTER_Y),
    ]
    assert mock_outro_audio.filter.call_args_list == []


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
def test_append_outro_clamps_fade_duration_to_base_duration(mock_ffmpeg):
    base_video_stream = MagicMock(name="base_video")
    base_audio_stream = MagicMock(name="base_audio")
    base_video_stream.filter.return_value = base_video_stream
    base_audio_stream.filter.return_value = base_audio_stream

    outro_input = MagicMock(name="outro_input")
    outro_video = MagicMock(name="outro_video")
    outro_audio = MagicMock(name="outro_audio")
    outro_input.video = outro_video
    outro_input.audio = outro_audio
    outro_video.filter.return_value = outro_video
    outro_audio.filter.return_value = outro_audio
    mock_ffmpeg.input.return_value = outro_input

    mock_ffmpeg.concat.return_value = _build_concat_result(video_output="v_out", audio_output="a_out")

    result_video, result_audio = FFmpegVideoProcessor._append_outro_if_enabled(
        base_video_stream=base_video_stream,
        base_audio_stream=base_audio_stream,
        target_format=VideoFormat.youtube_shorts(),
        base_duration=1.0,
        outro_filepath=_OUTRO_FILEPATH,
        fade_duration=5.0,
    )

    base_video_stream.filter.assert_has_calls([call("fade", type="out", start_time=0.0, duration=1.0)])
    base_audio_stream.filter.assert_has_calls([call("afade", type="out", start_time=0.0, duration=1.0)])
    assert result_video == "v_out"
    assert result_audio == "a_out"


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_wraps_ffmpeg_error_as_infrastructure_error(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.build_timeline.return_value = MagicMock()
    processor = FFmpegVideoProcessor()

    video = _build_default_video()
    interval = _build_default_interval()
    target_format = VideoFormat.youtube_shorts()

    mock_input, _, _, _ = _build_split_input(prefix="error")
    mock_ffmpeg.input.return_value = mock_input

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]
    _, mock_global_args = _build_mock_output(mock_ffmpeg)

    class FakeFFmpegError(Exception):
        pass

    mock_ffmpeg.Error = FakeFFmpegError
    mock_global_args.run.side_effect = FakeFFmpegError("boom")

    with pytest.raises(InfrastructureError, match=r"FFmpeg processing failed: boom") as exc_info:
        processor.generate_short(
            video=video,
            interval=interval,
            target_format=target_format,
            output_filepath=_OUTPUT_FILE_PATH,
        )
    assert str(exc_info.value) == "FFmpeg processing failed: boom"
    assert isinstance(exc_info.value.__cause__, FakeFFmpegError)


@patch.object(FFmpegVideoProcessor, "_append_outro_if_enabled")
@patch.object(FFmpegVideoProcessor, "_apply_editing_plan")
@patch.object(FFmpegVideoProcessor, "_build_editing_plan")
@patch.object(FFmpegVideoProcessor, "_build_split_screen_video_stream")
@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_generate_short_wires_editing_plan_and_default_fade_arguments(
    mock_subtitle_processor_class,
    mock_ffmpeg,
    mock_build_split_screen_video_stream,
    mock_build_editing_plan,
    mock_apply_editing_plan,
    mock_append_outro_if_enabled,
):
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    timeline = MagicMock(name="timeline")
    mock_subtitle_processor.build_timeline.return_value = timeline
    mock_build_split_screen_video_stream.return_value = "split_video"
    mock_build_editing_plan.return_value = "editing_plan"
    mock_apply_editing_plan.return_value = "edited_video"
    mock_ffmpeg.filter.return_value = "video_with_ass"
    mock_append_outro_if_enabled.return_value = ("video_with_outro", "audio_with_outro")
    mock_output, mock_global_args = _build_mock_output(mock_ffmpeg)
    processor = FFmpegVideoProcessor()

    video = _build_default_video()
    interval = _build_default_interval()
    target_format = VideoFormat.youtube_shorts()
    mock_input = MagicMock(name="input")
    mock_input.video = MagicMock(name="video_stream")
    mock_input.audio = MagicMock(name="audio_stream")
    mock_ffmpeg.input.return_value = mock_input

    result = processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath=_OUTPUT_FILE_PATH,
        outro_filepath=_OUTRO_FILEPATH,
    )

    mock_subtitle_processor.write_ass_from_timeline.assert_called_once_with(timeline, "out.ass")
    mock_build_editing_plan.assert_called_once_with(
        output_filepath=_OUTPUT_FILE_PATH,
        timeline=timeline,
        target_format=target_format,
    )
    mock_apply_editing_plan.assert_called_once_with("split_video", "editing_plan", target_format)
    mock_append_outro_if_enabled.assert_called_once_with(
        base_video_stream="video_with_ass",
        base_audio_stream=mock_input.audio,
        target_format=target_format,
        base_duration=10.0,
        outro_filepath=_OUTRO_FILEPATH,
        fade_duration=0.7,
    )
    mock_output.global_args.assert_called_once_with("-loglevel", "warning", "-y")
    mock_global_args.run.assert_called_once_with()
    assert result.original_video is video


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
def test_ffmpeg_processor_applies_cutaway_plan_before_ass_burn(mock_ffmpeg):
    base_stream = MagicMock(name="base_stream")
    overlay_stream = MagicMock(name="overlay_stream")
    mock_ffmpeg.input.return_value.video = overlay_stream
    overlay_stream.filter.return_value = overlay_stream
    mock_ffmpeg.overlay.return_value = "composited"

    processor = FFmpegVideoProcessor(editing_plan_builder=MagicMock())
    plan = ShortEditingPlan(
        short_id="short_0",
        enabled=True,
        strategy_version="broll-plan-v1",
        insertions=(
            BrollInsertion(
                insertion_id="insert-0001",
                beat_id="beat-0001",
                mode="cutaway",
                asset_provider="local_stills",
                asset_path=_ASSET_IMAGE_PATH,
                start_ms=1000,
                end_ms=2200,
                source_beat_score=0.9,
                candidate_score=0.8,
                x=0,
                y=0,
                width=1080,
                height=1920,
                opacity=1.0,
                asset_in_ms=0,
                asset_out_ms=1200,
            ),
        ),
    )

    composited_stream = processor._apply_editing_plan(base_stream, plan, VideoFormat.youtube_shorts())

    assert composited_stream == "composited"
    mock_ffmpeg.overlay.assert_called_once_with(
        base_stream,
        overlay_stream,
        x=0,
        y=0,
        enable="between(t,1.000,2.200)",
        eof_action="pass",
    )


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
def test_ffmpeg_processor_builds_overlay_stream_for_still_images_with_opacity(mock_ffmpeg):
    overlay_stream = MagicMock(name="overlay_stream")
    overlay_stream.filter.return_value = overlay_stream
    mock_ffmpeg.input.return_value.video = overlay_stream

    processor = FFmpegVideoProcessor(editing_plan_builder=MagicMock())
    insertion = BrollInsertion(
        insertion_id="insert-0001",
        beat_id="beat-0001",
        mode="overlay",
        asset_provider="local_media",
        asset_path=_ASSET_IMAGE_PATH,
        start_ms=1000,
        end_ms=2500,
        source_beat_score=0.9,
        candidate_score=0.8,
        x=100,
        y=120,
        width=800,
        height=520,
        opacity=0.5,
        asset_in_ms=0,
        asset_out_ms=1500,
    )

    result = processor._build_broll_stream(insertion, VideoFormat.youtube_shorts())

    assert result == overlay_stream
    mock_ffmpeg.input.assert_called_once_with(_ASSET_IMAGE_PATH, loop=1, framerate=30, t=1.5)
    assert overlay_stream.filter.call_args_list == [
        call("setpts", "PTS-STARTPTS+1.000/TB"),
        call("scale", 800, 520, force_original_aspect_ratio="decrease"),
        call("pad", 800, 520, _PAD_CENTER_X, _PAD_CENTER_Y),
        call("format", "rgba"),
        call("colorchannelmixer", aa=0.5),
    ]


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
def test_ffmpeg_processor_builds_full_frame_cutaway_stream_for_video_assets(mock_ffmpeg):
    cutaway_stream = MagicMock(name="cutaway_stream")
    cutaway_stream.filter.return_value = cutaway_stream
    mock_ffmpeg.input.return_value.video = cutaway_stream

    processor = FFmpegVideoProcessor(editing_plan_builder=MagicMock())
    insertion = BrollInsertion(
        insertion_id="insert-0002",
        beat_id="beat-0002",
        mode="full_frame_cutaway",
        asset_provider="manual_override",
        asset_path="manual.mp4",
        start_ms=2000,
        end_ms=4600,
        source_beat_score=1.0,
        candidate_score=1.0,
        x=0,
        y=0,
        width=1080,
        height=1920,
        opacity=1.0,
        asset_in_ms=0,
        asset_out_ms=2600,
        discovery_source="manual_override",
        anchor_text="so confusing",
    )

    result = processor._build_broll_stream(insertion, VideoFormat.youtube_shorts())

    assert result == cutaway_stream
    mock_ffmpeg.input.assert_called_once_with("manual.mp4", ss=0.0, t=2.6)
    assert cutaway_stream.filter.call_args_list == [
        call("setpts", "PTS-STARTPTS+2.000/TB"),
        call("scale", 1080, 1920, force_original_aspect_ratio="increase"),
        call("crop", 1080, 1920, "(in_w-out_w)/2", _VERTICAL_CENTER_CROP),
    ]


def test_ffmpeg_processor_returns_base_stream_when_editing_plan_is_disabled():
    processor = FFmpegVideoProcessor(editing_plan_builder=MagicMock())
    base_stream = MagicMock(name="base_stream")
    disabled_plan = ShortEditingPlan(
        short_id="short_0",
        enabled=False,
        strategy_version="broll-plan-v1",
        insertions=(),
    )

    assert processor._apply_editing_plan(base_stream, None, VideoFormat.youtube_shorts()) is base_stream
    assert processor._apply_editing_plan(base_stream, disabled_plan, VideoFormat.youtube_shorts()) is base_stream


def test_ffmpeg_processor_returns_base_stream_when_enabled_plan_has_no_insertions():
    processor = FFmpegVideoProcessor(editing_plan_builder=MagicMock())
    base_stream = MagicMock(name="base_stream")
    enabled_empty_plan = ShortEditingPlan(
        short_id="short_0",
        enabled=True,
        strategy_version="broll-plan-v1",
        insertions=(),
    )

    assert processor._apply_editing_plan(base_stream, enabled_empty_plan, VideoFormat.youtube_shorts()) is base_stream


def test_ffmpeg_processor_build_editing_plan_forwards_expected_builder_arguments():
    editing_plan_builder = MagicMock(name="editing_plan_builder")
    editing_plan_builder.build.return_value = "plan"
    processor = FFmpegVideoProcessor(editing_plan_builder=editing_plan_builder)
    timeline = MagicMock(name="timeline")
    target_format = VideoFormat.youtube_shorts()

    result = processor._build_editing_plan("nested/short_9.mp4", timeline, target_format)

    assert result == "plan"
    editing_plan_builder.build.assert_called_once_with(
        short_id="short_9",
        timeline=timeline,
        output_dir="nested",
        target_width=target_format.width,
        target_height=target_format.height,
    )


@patch("src.infrastructure.ffmpeg_processor.ConfigManager")
def test_ffmpeg_processor_build_editing_plan_builder_coerces_invalid_local_dirs(mock_config_manager):
    config = mock_config_manager.return_value
    config.get_broll_setting.side_effect = lambda name, default: {
        "local_search_dirs": "invalid",
        "beat_score_threshold": 0.7,
        "cutaway_score_threshold": 0.85,
        "min_gap_ms": 5000,
        "overlay_top_y": 140,
        "enabled": True,
    }.get(name, default)

    use_case = FFmpegVideoProcessor._build_editing_plan_builder()
    local_provider = cast(LocalMediaProvider, use_case.providers[0])

    assert use_case.enabled is True
    assert local_provider.search_dirs == ()
    assert use_case.insertion_planner.minimum_gap_ms == 5000


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
def test_ffmpeg_processor_builds_overlay_stream_with_minimum_duration_floor_and_skips_alpha_filters_for_opaque_assets(
    mock_ffmpeg,
):
    overlay_stream = MagicMock(name="overlay_stream")
    overlay_stream.filter.return_value = overlay_stream
    mock_ffmpeg.input.return_value.video = overlay_stream

    processor = FFmpegVideoProcessor(editing_plan_builder=MagicMock())
    insertion = BrollInsertion(
        insertion_id="insert-opaque",
        beat_id="beat-opaque",
        mode="overlay",
        asset_provider="local_media",
        asset_path=_ASSET_IMAGE_PATH,
        start_ms=1000,
        end_ms=1100,
        source_beat_score=0.8,
        candidate_score=0.7,
        x=80,
        y=100,
        width=800,
        height=520,
        opacity=1.0,
        asset_in_ms=0,
        asset_out_ms=100,
    )

    result = processor._build_broll_stream(insertion, VideoFormat.youtube_shorts())

    assert result == overlay_stream
    mock_ffmpeg.input.assert_called_once_with(_ASSET_IMAGE_PATH, loop=1, framerate=30, t=0.3)
    assert overlay_stream.filter.call_args_list == [
        call("setpts", "PTS-STARTPTS+1.000/TB"),
        call("scale", 800, 520, force_original_aspect_ratio="decrease"),
        call("pad", 800, 520, _PAD_CENTER_X, _PAD_CENTER_Y),
    ]


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
def test_ffmpeg_processor_builds_cutaway_stream_with_exact_asset_offset_for_video_assets(mock_ffmpeg):
    cutaway_stream = MagicMock(name="cutaway_stream")
    cutaway_stream.filter.return_value = cutaway_stream
    mock_ffmpeg.input.return_value.video = cutaway_stream

    processor = FFmpegVideoProcessor(editing_plan_builder=MagicMock())
    insertion = BrollInsertion(
        insertion_id="insert-cutaway",
        beat_id="beat-cutaway",
        mode="cutaway",
        asset_provider="manual_override",
        asset_path="manual.mp4",
        start_ms=2000,
        end_ms=2400,
        source_beat_score=1.0,
        candidate_score=1.0,
        x=0,
        y=0,
        width=1080,
        height=1920,
        opacity=1.0,
        asset_in_ms=1500,
        asset_out_ms=1900,
    )

    result = processor._build_broll_stream(insertion, VideoFormat.youtube_shorts())

    assert result == cutaway_stream
    mock_ffmpeg.input.assert_called_once_with("manual.mp4", ss=1.5, t=0.4)
    assert cutaway_stream.filter.call_args_list == [
        call("setpts", "PTS-STARTPTS+2.000/TB"),
        call("scale", 1080, 1920, force_original_aspect_ratio="increase"),
        call("crop", 1080, 1920, "(in_w-out_w)/2", _VERTICAL_CENTER_CROP),
    ]

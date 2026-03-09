from unittest.mock import MagicMock, call, patch

import pytest

from src.domain.entities import Video
from src.domain.exceptions import InfrastructureError
from src.domain.value_objects import TimeInterval, VideoFormat
from src.infrastructure.ffmpeg_processor import FFmpegVideoProcessor


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_generates_short(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.process_subtitles.return_value = []
    processor = FFmpegVideoProcessor()

    # Use a challenging path to test ASS path escaping
    video = Video(filepath="in_video.mp4", subtitles_filepath="subs.srt")
    interval = TimeInterval(start_seconds=10.0, end_seconds=20.0)
    target_format = VideoFormat.youtube_shorts()
    output_filepath = "C:\\fake:dir\\out.mp4"

    # Mock ffmpeg input
    mock_input = MagicMock()
    mock_ffmpeg.input.return_value = mock_input

    # Mock video streams and split
    mock_video_stream = MagicMock()
    mock_audio_stream = MagicMock()
    mock_input.video = mock_video_stream
    mock_input.audio = mock_audio_stream

    mock_left = MagicMock(name="left")
    mock_right = MagicMock(name="right")
    # Return self on filter to allow chained query verification
    mock_left.filter.return_value = mock_left
    mock_right.filter.return_value = mock_right

    mock_video_stream.split.return_value = [mock_left, mock_right]

    # Mock standalone ffmpeg filters
    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]

    # Mock output and run
    mock_output = MagicMock()
    mock_ffmpeg.output.return_value = mock_output
    mock_global_args = MagicMock()
    mock_output.global_args.return_value = mock_global_args

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

    # Verify input
    mock_ffmpeg.input.assert_called_once_with("in_video.mp4", ss=10.0, t=10.0)

    # Verify left processing
    mock_left.filter.assert_has_calls(
        [
            call("crop", "in_w/2", "in_h", "0", "0"),
            call("scale", 1080, "-1"),
            call("crop", 1080, 960, "0", "(in_h-out_h)/2"),
        ]
    )

    # Verify right processing
    mock_right.filter.assert_has_calls(
        [
            call("crop", "in_w/2", "in_h", "in_w/2", "0"),
            call("scale", 1080, "-1"),
            call("crop", 1080, 960, "0", "(in_h-out_h)/2"),
        ]
    )
    # Enforce integer crop heights (not floats) to preserve exact ffmpeg arguments.
    assert mock_left.filter.call_args_list[2].args[2] == 960
    assert isinstance(mock_left.filter.call_args_list[2].args[2], int)
    assert mock_right.filter.call_args_list[2].args[2] == 960
    assert isinstance(mock_right.filter.call_args_list[2].args[2], int)

    # Verify global ffmpeg filters
    ass_escaped = "C\\:/fake\\:dir/out.ass"
    mock_ffmpeg.filter.assert_has_calls(
        [call([mock_left, mock_right], "vstack"), call(mock_vstack, "ass", ass_escaped)]
    )

    # Verify output call
    mock_ffmpeg.output.assert_called_once_with(
        mock_ass,
        mock_audio_stream,
        output_filepath,
        vcodec="libx264",
        acodec="aac",
        preset="fast",
    )

    # Verify arguments
    mock_output.global_args.assert_called_once_with("-loglevel", "warning", "-y")
    mock_global_args.run.assert_called_once()

    # Verify subtitle processor call
    ass_filepath = "C:\\fake:dir\\out.ass"
    mock_subtitle_processor.process_subtitles.assert_called_once_with(
        "subs.srt", interval, ass_filepath, media_filepath="in_video.mp4"
    )


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_generates_short_with_outro_and_fades(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.process_subtitles.return_value = []
    processor = FFmpegVideoProcessor()

    video = Video(filepath="in_video.mp4", subtitles_filepath="subs.srt")
    interval = TimeInterval(start_seconds=10.0, end_seconds=20.0)
    target_format = VideoFormat.youtube_shorts()
    output_filepath = "out.mp4"

    # Base input stream
    mock_base_input = MagicMock(name="base_input")
    mock_base_video_stream = MagicMock(name="base_video_stream")
    mock_base_audio_stream = MagicMock(name="base_audio_stream")
    mock_base_input.video = mock_base_video_stream
    mock_base_input.audio = mock_base_audio_stream

    mock_left = MagicMock(name="left")
    mock_right = MagicMock(name="right")
    mock_left.filter.return_value = mock_left
    mock_right.filter.return_value = mock_right
    mock_base_video_stream.split.return_value = [mock_left, mock_right]

    # Outro input stream
    mock_outro_input = MagicMock(name="outro_input")
    mock_outro_video = MagicMock(name="outro_video")
    mock_outro_audio = MagicMock(name="outro_audio")
    mock_outro_input.video = mock_outro_video
    mock_outro_input.audio = mock_outro_audio
    mock_outro_video.filter.return_value = mock_outro_video
    mock_outro_audio.filter.return_value = mock_outro_audio

    mock_ffmpeg.input.side_effect = [mock_base_input, mock_outro_input]

    # vstack + ass
    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]

    # Base fades
    mock_video_faded = MagicMock(name="video_faded")
    mock_audio_faded = MagicMock(name="audio_faded")
    mock_ass.filter.return_value = mock_video_faded
    mock_base_audio_stream.filter.return_value = mock_audio_faded

    # Concat output mapping
    mock_concat_node = MagicMock(name="concat_node")
    mock_concat_node.__getitem__.side_effect = ["concat_video", "concat_audio"]
    mock_concat_result = MagicMock(name="concat_result")
    mock_concat_result.node = mock_concat_node
    mock_ffmpeg.concat.return_value = mock_concat_result

    # Final output
    mock_output = MagicMock(name="output")
    mock_global_args = MagicMock(name="global_args")
    mock_ffmpeg.output.return_value = mock_output
    mock_output.global_args.return_value = mock_global_args

    # Act
    result = processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath=output_filepath,
        outro_filepath="inputs/outroShort.mp4",
        fade_duration=0.7,
    )

    # Assert
    assert result.filepath == output_filepath
    assert result.interval == interval

    mock_ffmpeg.input.assert_has_calls(
        [
            call("in_video.mp4", ss=10.0, t=10.0),
            call("inputs/outroShort.mp4"),
        ]
    )

    mock_ass.filter.assert_called_once_with("fade", type="out", start_time=9.3, duration=0.7)
    mock_base_audio_stream.filter.assert_called_once_with("afade", type="out", start_time=9.3, duration=0.7)

    assert mock_outro_video.filter.call_args_list == [
        call(
            "scale",
            1080,
            1920,
            force_original_aspect_ratio="decrease",
        ),
        call("pad", 1080, 1920, "(ow-iw)/2", "(oh-ih)/2"),
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
        output_filepath,
        vcodec="libx264",
        acodec="aac",
        preset="fast",
    )
    mock_global_args.run.assert_called_once()


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_uses_default_fade_duration_when_outro_is_enabled(mock_subtitle_processor_class, mock_ffmpeg):
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.process_subtitles.return_value = []
    processor = FFmpegVideoProcessor()

    video = Video(filepath="in_video.mp4", subtitles_filepath="subs.srt")
    interval = TimeInterval(start_seconds=10.0, end_seconds=20.0)
    target_format = VideoFormat.youtube_shorts()

    mock_base_input = MagicMock(name="base_input")
    mock_base_video_stream = MagicMock(name="base_video_stream")
    mock_base_audio_stream = MagicMock(name="base_audio_stream")
    mock_base_input.video = mock_base_video_stream
    mock_base_input.audio = mock_base_audio_stream
    mock_left = MagicMock(name="left")
    mock_right = MagicMock(name="right")
    mock_left.filter.return_value = mock_left
    mock_right.filter.return_value = mock_right
    mock_base_video_stream.split.return_value = [mock_left, mock_right]

    mock_outro_input = MagicMock(name="outro_input")
    mock_outro_video = MagicMock(name="outro_video")
    mock_outro_audio = MagicMock(name="outro_audio")
    mock_outro_input.video = mock_outro_video
    mock_outro_input.audio = mock_outro_audio
    mock_outro_video.filter.return_value = mock_outro_video
    mock_outro_audio.filter.return_value = mock_outro_audio
    mock_ffmpeg.input.side_effect = [mock_base_input, mock_outro_input]

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]
    mock_video_faded = MagicMock(name="video_faded")
    mock_audio_faded = MagicMock(name="audio_faded")
    mock_ass.filter.return_value = mock_video_faded
    mock_base_audio_stream.filter.return_value = mock_audio_faded

    concat_node = MagicMock(name="concat_node")
    concat_node.__getitem__.side_effect = lambda index: {
        0: "concat_video",
        1: "concat_audio",
    }[index]
    concat_result = MagicMock(name="concat_result")
    concat_result.node = concat_node
    mock_ffmpeg.concat.return_value = concat_result
    mock_output = MagicMock(name="output")
    mock_global_args = MagicMock(name="global_args")
    mock_ffmpeg.output.return_value = mock_output
    mock_output.global_args.return_value = mock_global_args

    processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath="out.mp4",
        outro_filepath="inputs/outroShort.mp4",
    )

    mock_ass.filter.assert_called_once_with("fade", type="out", start_time=9.3, duration=0.7)
    mock_base_audio_stream.filter.assert_called_once_with("afade", type="out", start_time=9.3, duration=0.7)
    mock_ffmpeg.output.assert_called_once_with(
        "concat_video",
        "concat_audio",
        "out.mp4",
        vcodec="libx264",
        acodec="aac",
        preset="fast",
    )


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_generates_short_with_outro_and_zero_fade(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.process_subtitles.return_value = []
    processor = FFmpegVideoProcessor()

    video = Video(filepath="in_video.mp4", subtitles_filepath="subs.srt")
    interval = TimeInterval(start_seconds=10.0, end_seconds=20.0)
    target_format = VideoFormat.youtube_shorts()

    mock_base_input = MagicMock(name="base_input")
    mock_base_video_stream = MagicMock(name="base_video_stream")
    mock_base_audio_stream = MagicMock(name="base_audio_stream")
    mock_base_input.video = mock_base_video_stream
    mock_base_input.audio = mock_base_audio_stream

    mock_left = MagicMock(name="left")
    mock_right = MagicMock(name="right")
    mock_left.filter.return_value = mock_left
    mock_right.filter.return_value = mock_right
    mock_base_video_stream.split.return_value = [mock_left, mock_right]

    mock_outro_input = MagicMock(name="outro_input")
    mock_outro_video = MagicMock(name="outro_video")
    mock_outro_audio = MagicMock(name="outro_audio")
    mock_outro_input.video = mock_outro_video
    mock_outro_input.audio = mock_outro_audio
    mock_outro_video.filter.return_value = mock_outro_video
    mock_outro_audio.filter.return_value = mock_outro_audio

    mock_ffmpeg.input.side_effect = [mock_base_input, mock_outro_input]

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]

    mock_concat_node = MagicMock(name="concat_node")
    mock_concat_node.__getitem__.side_effect = ["concat_video", "concat_audio"]
    mock_concat_result = MagicMock(name="concat_result")
    mock_concat_result.node = mock_concat_node
    mock_ffmpeg.concat.return_value = mock_concat_result

    mock_output = MagicMock(name="output")
    mock_global_args = MagicMock(name="global_args")
    mock_ffmpeg.output.return_value = mock_output
    mock_output.global_args.return_value = mock_global_args

    # Act
    processor.generate_short(
        video=video,
        interval=interval,
        target_format=target_format,
        output_filepath="out.mp4",
        outro_filepath="inputs/outroShort.mp4",
        fade_duration=0.0,
    )

    # Assert no fade is applied when fade duration is 0
    assert call("fade", type="out", start_time=10.0, duration=0.0) not in mock_ass.filter.call_args_list
    assert not any(args[0] == "afade" for args, _ in mock_base_audio_stream.filter.call_args_list)
    assert mock_outro_video.filter.call_args_list == [
        call("scale", 1080, 1920, force_original_aspect_ratio="decrease"),
        call("pad", 1080, 1920, "(ow-iw)/2", "(oh-ih)/2"),
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

    concat_node = MagicMock(name="concat_node")
    concat_node.__getitem__.side_effect = ["v_out", "a_out"]
    concat_result = MagicMock(name="concat_result")
    concat_result.node = concat_node
    mock_ffmpeg.concat.return_value = concat_result

    # Act
    result_video, result_audio = FFmpegVideoProcessor._append_outro_if_enabled(
        base_video_stream=base_video_stream,
        base_audio_stream=base_audio_stream,
        target_format=VideoFormat.youtube_shorts(),
        base_duration=1.0,
        outro_filepath="inputs/outroShort.mp4",
        fade_duration=5.0,
    )

    # Assert: fade duration is clamped to base_duration (1.0) and starts at 0.0
    base_video_stream.filter.assert_has_calls([call("fade", type="out", start_time=0.0, duration=1.0)])
    base_audio_stream.filter.assert_has_calls([call("afade", type="out", start_time=0.0, duration=1.0)])
    assert result_video == "v_out"
    assert result_audio == "a_out"


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
@patch("src.infrastructure.ffmpeg_processor.SubtitleProcessor")
def test_ffmpeg_processor_wraps_ffmpeg_error_as_infrastructure_error(mock_subtitle_processor_class, mock_ffmpeg):
    # Arrange
    mock_subtitle_processor = mock_subtitle_processor_class.return_value
    mock_subtitle_processor.process_subtitles.return_value = []
    processor = FFmpegVideoProcessor()

    video = Video(filepath="in_video.mp4", subtitles_filepath="subs.srt")
    interval = TimeInterval(start_seconds=10.0, end_seconds=20.0)
    target_format = VideoFormat.youtube_shorts()

    mock_input = MagicMock()
    mock_input.video = MagicMock()
    mock_input.audio = MagicMock()
    mock_left = MagicMock(name="left")
    mock_right = MagicMock(name="right")
    mock_left.filter.return_value = mock_left
    mock_right.filter.return_value = mock_right
    mock_input.video.split.return_value = [mock_left, mock_right]
    mock_ffmpeg.input.return_value = mock_input

    mock_vstack = MagicMock(name="vstack")
    mock_ass = MagicMock(name="ass")
    mock_ffmpeg.filter.side_effect = [mock_vstack, mock_ass]

    mock_output = MagicMock()
    mock_global_args = MagicMock()
    mock_ffmpeg.output.return_value = mock_output
    mock_output.global_args.return_value = mock_global_args

    class FakeFFmpegError(Exception):
        pass

    mock_ffmpeg.Error = FakeFFmpegError
    mock_global_args.run.side_effect = FakeFFmpegError("boom")

    # Act / Assert
    with pytest.raises(InfrastructureError, match=r"FFmpeg processing failed: boom") as exc_info:
        processor.generate_short(
            video=video,
            interval=interval,
            target_format=target_format,
            output_filepath="out.mp4",
        )
    assert str(exc_info.value) == "FFmpeg processing failed: boom"
    assert isinstance(exc_info.value.__cause__, FakeFFmpegError)

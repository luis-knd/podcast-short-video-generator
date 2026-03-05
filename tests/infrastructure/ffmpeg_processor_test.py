from unittest.mock import MagicMock, call, patch

from src.domain.entities import Video
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
        "subs.srt", interval, ass_filepath
    )

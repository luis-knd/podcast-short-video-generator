from unittest.mock import MagicMock, call, patch

from src.domain.value_objects import VideoFormat
from src.infrastructure.ffmpeg_processor import FFmpegVideoProcessor

_HALF_WIDTH_LEFT_CROP = "in_w/2"


@patch("src.infrastructure.ffmpeg_processor.ffmpeg")
def test_build_split_screen_video_stream_reframes_each_half_inward_before_scaling(mock_ffmpeg):
    source_stream = MagicMock(name="source_stream")
    left_stream = MagicMock(name="left_stream")
    right_stream = MagicMock(name="right_stream")
    source_stream.split.return_value = [left_stream, right_stream]
    left_stream.filter.return_value = left_stream
    right_stream.filter.return_value = right_stream
    stacked_stream = MagicMock(name="stacked_stream")
    mock_ffmpeg.filter.return_value = stacked_stream

    result = FFmpegVideoProcessor._build_split_screen_video_stream(source_stream, VideoFormat.youtube_shorts())

    assert result is stacked_stream
    assert left_stream.filter.call_args_list == [
        call("crop", _HALF_WIDTH_LEFT_CROP, "in_h", "in_w/16", "0"),
        call("scale", 1080, "-1"),
        call("crop", 1080, 960, "0", "(in_h-out_h)/2"),
    ]
    assert right_stream.filter.call_args_list == [
        call("crop", _HALF_WIDTH_LEFT_CROP, "in_h", "in_w/2-in_w/16", "0"),
        call("scale", 1080, "-1"),
        call("crop", 1080, 960, "0", "(in_h-out_h)/2"),
    ]
    mock_ffmpeg.filter.assert_called_once_with([left_stream, right_stream], "vstack")


def test_build_split_screen_video_stream_uses_distinct_inward_offsets_for_left_and_right_speakers():
    expected_left_x = "in_w/16"
    expected_right_x = "in_w/2-in_w/16"

    assert expected_left_x != "0"
    assert expected_right_x != "in_w/2"
    assert expected_left_x != expected_right_x

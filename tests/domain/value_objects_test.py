from dataclasses import FrozenInstanceError
from unittest.mock import PropertyMock, patch

import pytest

from src.domain.exceptions import DomainError
from src.domain.value_objects import TimeInterval, VideoFormat


def test_time_interval_valid_creation():
    interval = TimeInterval(start_seconds=10.5, end_seconds=20.0)
    assert interval.start_seconds == 10.5
    assert interval.end_seconds == 20.0


@pytest.mark.parametrize(
    ("start_seconds", "end_seconds"),
    [
        (10.5, 20.0),
        (0.0, 10.0),
        (0.5, 10.0),
    ],
)
def test_time_interval_accepts_valid_boundaries(start_seconds, end_seconds):
    interval = TimeInterval(start_seconds=start_seconds, end_seconds=end_seconds)
    assert interval.start_seconds == start_seconds
    assert interval.end_seconds == end_seconds


@pytest.mark.parametrize(
    ("time_str", "expected_seconds"),
    [
        ("01:30", 90.0),
        ("00:00:12,460", pytest.approx(12.460)),
        ("01:06:36,500", pytest.approx(3996.500)),
    ],
)
def test_time_interval_parse_time_supports_expected_formats(time_str, expected_seconds):
    assert TimeInterval._parse_time(time_str) == expected_seconds


def test_time_interval_negative_start():
    with pytest.raises(DomainError, match="^Start time cannot be negative$"):
        TimeInterval(start_seconds=-1, end_seconds=10)


@pytest.mark.parametrize("end_seconds", [5, 10])
def test_time_interval_rejects_non_increasing_end(end_seconds):
    with pytest.raises(DomainError, match="^End time must be greater than start time$"):
        TimeInterval(start_seconds=10, end_seconds=end_seconds)


def test_time_interval_is_frozen():
    interval = TimeInterval(start_seconds=10.5, end_seconds=20.0)
    with pytest.raises(FrozenInstanceError):
        interval.start_seconds = 15.0


@pytest.mark.parametrize(
    ("time_str", "start_seconds", "end_seconds"),
    [
        ("01:30 - 02:45", 90.0, 165.0),
        ("01:01:30 - 01:02:45", 3690.0, 3765.0),
        ("00:00:12,460 - 00:00:31,460", pytest.approx(12.460), pytest.approx(31.460)),
        ("00:06:36,460 - 00:07:24,460", pytest.approx(396.460), pytest.approx(444.460)),
        ("00:07:50,000 - 00:08:39,000", pytest.approx(470.0), pytest.approx(519.0)),
        ("10.5 - 20", 10.5, 20.0),
    ],
)
def test_time_interval_from_string_supports_expected_formats(time_str, start_seconds, end_seconds):
    interval = TimeInterval.from_string(time_str)
    assert interval.start_seconds == start_seconds
    assert interval.end_seconds == end_seconds


def test_time_interval_from_string_invalid_format():
    with pytest.raises(DomainError, match="^Invalid time format: 01:30. Expected 'MM:SS - MM:SS'$"):
        TimeInterval.from_string("01:30")


def test_time_interval_strict_separator():
    with pytest.raises(DomainError) as exc_info:
        TimeInterval.from_string("01:30 -02:45")
    assert str(exc_info.value.__context__) == "Must strictly use ' - ' separator"


def test_time_interval_from_string_inner_start_error():
    with pytest.raises(DomainError, match="^Start time cannot be negative$"):
        TimeInterval.from_string("-01:00 - 02:00")


def test_time_interval_from_string_inner_end_error():
    with pytest.raises(DomainError, match="^End time must be greater than start time$"):
        TimeInterval.from_string("02:00 - 01:00")


def test_video_format_youtube_shorts():
    fmt = VideoFormat.youtube_shorts()
    assert fmt.width == 1080
    assert fmt.height == 1920
    assert fmt.aspect_ratio == 1080 / 1920


def test_video_format_invalid_aspect_ratio():
    with pytest.raises(
        DomainError,
        match="^Video format must have a 9:16 aspect ratio for YouTube Shorts$",
    ):
        VideoFormat(width=1920, height=1080)


def test_video_format_negative_dimensions():
    with pytest.raises(DomainError, match="^Width and height must be positive$"):
        VideoFormat(width=-1080, height=1920)


def test_video_format_zero_dimensions():
    with pytest.raises(DomainError, match="^Width and height must be positive$"):
        VideoFormat(width=0, height=1920)
    with pytest.raises(DomainError, match="^Width and height must be positive$"):
        VideoFormat(width=1080, height=0)


def test_video_format_width_one_can_pass_when_ratio_validation_passes():
    with patch.object(
        VideoFormat,
        "aspect_ratio",
        new_callable=PropertyMock,
        return_value=(9 / 16),
    ):
        fmt = VideoFormat(width=1, height=1920)
    assert fmt.width == 1


def test_video_format_height_one_can_pass_when_ratio_validation_passes():
    with patch.object(
        VideoFormat,
        "aspect_ratio",
        new_callable=PropertyMock,
        return_value=(9 / 16),
    ):
        fmt = VideoFormat(width=1080, height=1)
    assert fmt.height == 1


def test_video_format_is_frozen():
    fmt = VideoFormat.youtube_shorts()
    with pytest.raises(FrozenInstanceError):
        fmt.width = 1000


def test_video_format_aspect_ratio_tolerance():
    # Valid exact
    fmt = VideoFormat(width=900, height=1600)
    assert fmt.width == 900

    # Valid close to bounds (0.5625 +/- 0.01)
    # 0.572 < 0.5725
    VideoFormat(width=572, height=1000)
    # 0.553 > 0.5525
    VideoFormat(width=553, height=1000)

    # Invalid slightly out of bounds
    with pytest.raises(
        DomainError,
        match="^Video format must have a 9:16 aspect ratio for YouTube Shorts$",
    ):
        VideoFormat(width=573, height=1000)  # 0.573

    with pytest.raises(
        DomainError,
        match="^Video format must have a 9:16 aspect ratio for YouTube Shorts$",
    ):
        VideoFormat(width=552, height=1000)  # 0.552


def test_video_format_uses_strict_greater_than_for_tolerance_check():
    class DiffProbe:
        def __abs__(self):
            return self

        def __gt__(self, _other):
            return False

        def __ge__(self, _other):
            return True

    class RatioProbe:
        def __sub__(self, _other):
            return DiffProbe()

    with patch.object(
        VideoFormat,
        "aspect_ratio",
        new_callable=PropertyMock,
        return_value=RatioProbe(),
    ):
        fmt = VideoFormat(width=1080, height=1920)
    assert fmt.width == 1080

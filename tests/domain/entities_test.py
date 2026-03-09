from src.domain.entities import ShortVideo, Video
from src.domain.value_objects import TimeInterval, VideoFormat


def test_video_creation():
    video = Video(filepath="video.mp4", subtitles_filepath="subs.srt")
    assert video.filepath == "video.mp4"
    assert video.subtitles_filepath == "subs.srt"


def test_short_video_creation():
    original = Video(filepath="video.mp4", subtitles_filepath="subs.srt")
    interval = TimeInterval(start_seconds=10, end_seconds=20)
    fmt = VideoFormat.youtube_shorts()

    short = ShortVideo(filepath="short.mp4", original_video=original, interval=interval, format=fmt)

    assert short.filepath == "short.mp4"
    assert short.original_video == original
    assert short.interval == interval
    assert short.format == fmt

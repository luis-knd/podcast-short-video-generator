from dataclasses import dataclass

from src.domain.value_objects import TimeInterval, VideoFormat


@dataclass
class Video:
    filepath: str
    subtitles_filepath: str


@dataclass
class ShortVideo:
    filepath: str
    original_video: Video
    interval: TimeInterval
    format: VideoFormat

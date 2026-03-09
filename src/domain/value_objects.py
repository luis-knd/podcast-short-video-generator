from dataclasses import dataclass

from src.domain.exceptions import DomainError


@dataclass(frozen=True)
class TimeInterval:
    start_seconds: float
    end_seconds: float

    def __post_init__(self):
        if self.start_seconds < 0:
            raise DomainError("Start time cannot be negative")
        if self.end_seconds <= self.start_seconds:
            raise DomainError("End time must be greater than start time")

    @classmethod
    def from_string(cls, time_str: str) -> "TimeInterval":
        """
        Parses a string in the format "MM:SS - MM:SS" into a TimeInterval.
        """
        try:
            if " - " not in time_str:
                raise DomainError("Must strictly use ' - ' separator")
            start_str, end_str = time_str.split(" - ")
            return cls(
                start_seconds=cls._parse_time(start_str),
                end_seconds=cls._parse_time(end_str),
            )
        except (ValueError, DomainError) as e:
            if "Start time" in str(e) or "End time" in str(e):
                raise
            raise DomainError(f"Invalid time format: {time_str}. Expected 'MM:SS - MM:SS'") from e

    @staticmethod
    def _parse_time(time_str: str) -> float:
        parts = time_str.split(":")
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        elif len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        else:
            return float(time_str)


@dataclass(frozen=True)
class VideoFormat:
    width: int
    height: int

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0:
            raise DomainError("Width and height must be positive")
        if abs(self.aspect_ratio - (9 / 16)) > 0.01:
            raise DomainError("Video format must have a 9:16 aspect ratio for YouTube Shorts")

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @classmethod
    def youtube_shorts(cls) -> "VideoFormat":
        return cls(width=1080, height=1920)

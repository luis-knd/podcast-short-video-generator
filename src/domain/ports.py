import abc

from src.domain.entities import ShortVideo, Video
from src.domain.value_objects import TimeInterval, VideoFormat


class IVideoProcessor(abc.ABC):
    @abc.abstractmethod
    def generate_short(
        self,
        video: Video,
        interval: TimeInterval,
        target_format: VideoFormat,
        output_filepath: str,
        outro_filepath: str | None = None,
        fade_duration: float = 0.7,
    ) -> ShortVideo:
        """
        Extracts a clip from the video at the given interval, formats it to the target format,
        burns the associated subtitles, and saves it to output_filepath.
        """
        pass  # pragma: no cover

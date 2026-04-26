import abc

from src.domain.broll_models import BrollCandidate, ImpactBeat, ShortEditingPlan
from src.domain.entities import ShortVideo, Video
from src.domain.subtitle_models import SubtitleTimeline
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


class ISubtitleIntervalGenerator(abc.ABC):
    @abc.abstractmethod
    def generate(self, subtitles_filepath: str) -> list[dict[str, str]]:
        """
        Infers short-ready intervals from a subtitle file and returns the JSON-compatible
        contract consumed by the existing shorts' use case.
        """
        pass  # pragma: no cover


class IBrollAssetProvider(abc.ABC):
    @abc.abstractmethod
    def search(
        self,
        beat: ImpactBeat,
        queries: tuple[str, ...],
        cache_dir: str,
    ) -> list[BrollCandidate]:
        """
        Searches a free/open-source asset source and returns locally usable candidates.
        """
        pass  # pragma: no cover

    @abc.abstractmethod
    def prepare_asset(
        self,
        candidate: BrollCandidate,
        cache_dir: str,
    ) -> BrollCandidate:
        """
        Ensures the candidate is locally available for FFmpeg consumption.
        """
        pass  # pragma: no cover


class IBrollArtifactsWriter(abc.ABC):
    @abc.abstractmethod
    def write_impact_beats(
        self,
        short_id: str,
        timeline: SubtitleTimeline,
        beats: list[ImpactBeat],
        output_dir,
    ):
        pass  # pragma: no cover

    @abc.abstractmethod
    def write_broll_candidates(
        self,
        short_id: str,
        beats: list[dict[str, object]],
        output_dir,
    ):
        pass  # pragma: no cover

    @abc.abstractmethod
    def write_broll_plan(
        self,
        short_id: str,
        plan: ShortEditingPlan,
        output_dir,
    ):
        pass  # pragma: no cover

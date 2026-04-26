from dataclasses import dataclass

from src.domain.entities import ShortVideo, Video
from src.domain.exceptions import ShortGeneratorError
from src.domain.ports import ISubtitleIntervalGenerator, IVideoProcessor
from src.domain.value_objects import TimeInterval, VideoFormat


@dataclass(frozen=True)
class ResolvedIntervals:
    intervals_json: list[dict[str, str]]
    source: str
    warning_message: str | None = None


class ResolveIntervalsUseCase:
    def __init__(self, interval_generator: ISubtitleIntervalGenerator):
        self.interval_generator = interval_generator

    def execute(
        self,
        subtitles_filepath: str,
        manual_intervals_json: list[dict[str, str]] | None,
        force_auto_generation: bool = False,
    ) -> ResolvedIntervals:
        if manual_intervals_json is not None and not force_auto_generation:
            return ResolvedIntervals(intervals_json=manual_intervals_json, source="manual")

        try:
            generated_intervals = self.interval_generator.generate(subtitles_filepath)
        except (OSError, RuntimeError, TypeError, ValueError, ShortGeneratorError) as exc:
            if manual_intervals_json is not None:
                return ResolvedIntervals(
                    intervals_json=manual_intervals_json,
                    source="manual",
                    warning_message=(
                        "Warning: Automatic interval generation failed; using existing intervals file instead. "
                        f"Reason: {exc}"
                    ),
                )
            raise ShortGeneratorError(f"Automatic interval generation failed: {exc}") from exc

        if generated_intervals:
            return ResolvedIntervals(intervals_json=generated_intervals, source="auto")

        if manual_intervals_json is not None:
            return ResolvedIntervals(
                intervals_json=manual_intervals_json,
                source="manual",
                warning_message=(
                    "Warning: Automatic interval generation produced no candidates; "
                    "using existing intervals file instead."
                ),
            )

        raise ShortGeneratorError("Automatic interval generation produced no candidates")


class GenerateShortUseCase:
    DEFAULT_FADE_DURATION = 0.7

    def __init__(self, video_processor: IVideoProcessor):
        self.video_processor = video_processor

    def execute(
        self,
        video_filepath: str,
        subtitles_filepath: str,
        intervals_json: list[dict[str, str]],
        output_dir: str,
        outro_filepath: str | None = None,
        fade_duration: float | None = None,
    ) -> list[ShortVideo]:
        """
        Orchestrates the creation of shorts from a single video and multiple intervals.
        intervals_json format: [{"time": "01:30 - 02:45"}, ...]
        """
        video = Video(filepath=video_filepath, subtitles_filepath=subtitles_filepath)
        target_format = VideoFormat.youtube_shorts()
        effective_fade_duration = self.DEFAULT_FADE_DURATION if fade_duration is None else fade_duration

        generated_shorts = []

        for idx, interval_data in enumerate(intervals_json):
            time_str = interval_data.get("time")
            if not time_str:
                continue

            interval = TimeInterval.from_string(time_str)
            output_filepath = f"{output_dir}/short_{idx}.mp4"

            short = self.video_processor.generate_short(
                video=video,
                interval=interval,
                target_format=target_format,
                output_filepath=output_filepath,
                outro_filepath=outro_filepath,
                fade_duration=effective_fade_duration,
            )
            generated_shorts.append(short)

        return generated_shorts

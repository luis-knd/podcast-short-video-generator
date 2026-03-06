from src.domain.entities import ShortVideo, Video
from src.domain.ports import IVideoProcessor
from src.domain.value_objects import TimeInterval, VideoFormat


class GenerateShortUseCase:
    def __init__(self, video_processor: IVideoProcessor):
        self.video_processor = video_processor

    def execute(
        self,
        video_filepath: str,
        subtitles_filepath: str,
        intervals_json: list[dict[str, str]],
        output_dir: str,
        outro_filepath: str | None = None,
        fade_duration: float = 0.7,
    ) -> list[ShortVideo]:
        """
        Orchestrates the creation of shorts from a single video and multiple intervals.
        intervals_json format: [{"time": "01:30 - 02:45"}, ...]
        """
        video = Video(filepath=video_filepath, subtitles_filepath=subtitles_filepath)
        target_format = VideoFormat.youtube_shorts()

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
                fade_duration=fade_duration,
            )
            generated_shorts.append(short)

        return generated_shorts

from unittest.mock import Mock

from src.application.use_cases import GenerateShortUseCase
from src.domain.entities import ShortVideo
from src.domain.ports import IVideoProcessor


def test_generate_short_use_case_uses_default_fade_duration_when_none_is_provided():
    processor = Mock(spec=IVideoProcessor)
    use_case = GenerateShortUseCase(video_processor=processor)

    def build_short(video, interval, target_format, output_filepath, outro_filepath=None, fade_duration=0.7):
        return ShortVideo(filepath=output_filepath, original_video=video, interval=interval, format=target_format)

    processor.generate_short.side_effect = build_short

    use_case.execute(
        video_filepath="video.mp4",
        subtitles_filepath="video.srt",
        intervals_json=[{"time": "00:01 - 00:10"}],
        output_dir="outputs",
        fade_duration=None,
    )

    assert processor.generate_short.call_args.kwargs["fade_duration"] == 0.7


def test_generate_short_use_case_skips_falsey_time_values_and_keeps_original_indexes():
    processor = Mock(spec=IVideoProcessor)
    use_case = GenerateShortUseCase(video_processor=processor)

    def build_short(video, interval, target_format, output_filepath, outro_filepath=None, fade_duration=0.7):
        return ShortVideo(filepath=output_filepath, original_video=video, interval=interval, format=target_format)

    processor.generate_short.side_effect = build_short

    shorts = use_case.execute(
        video_filepath="video.mp4",
        subtitles_filepath="video.srt",
        intervals_json=[{"time": ""}, {"time": None}, {"time": "00:20 - 00:30"}],
        output_dir="outputs",
    )

    assert len(shorts) == 1
    assert processor.generate_short.call_count == 1
    assert processor.generate_short.call_args.kwargs["output_filepath"] == "outputs/short_2.mp4"

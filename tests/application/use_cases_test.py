from unittest.mock import Mock

from src.application.use_cases import GenerateShortUseCase
from src.domain.entities import ShortVideo
from src.domain.ports import IVideoProcessor


def test_generate_short_use_case_success():
    # Arrange
    mock_processor = Mock(spec=IVideoProcessor)
    use_case = GenerateShortUseCase(video_processor=mock_processor)

    video_filepath = "test.mp4"
    subtitles_filepath = "test.srt"
    intervals_json = [{"time": "00:10 - 00:20"}, {"time": "01:30 - 01:45"}]
    output_dir = "output_dir"

    # Define mock return behavior
    def mock_generate_short(
        video,
        interval,
        target_format,
        output_filepath,
        outro_filepath=None,
        fade_duration=0.7,
    ):
        return ShortVideo(
            filepath=output_filepath,
            original_video=video,
            interval=interval,
            format=target_format,
        )

    mock_processor.generate_short.side_effect = mock_generate_short

    # Act
    shorts = use_case.execute(
        video_filepath=video_filepath,
        subtitles_filepath=subtitles_filepath,
        intervals_json=intervals_json,
        output_dir=output_dir,
    )

    # Assert
    assert len(shorts) == 2
    assert mock_processor.generate_short.call_count == 2

    # Check first call
    call_args_1 = mock_processor.generate_short.call_args_list[0].kwargs
    assert call_args_1["video"].filepath == "test.mp4"
    assert call_args_1["interval"].start_seconds == 10.0
    assert call_args_1["interval"].end_seconds == 20.0
    assert call_args_1["target_format"].width == 1080
    assert call_args_1["target_format"].height == 1920
    assert call_args_1["output_filepath"] == "output_dir/short_0.mp4"
    assert call_args_1["outro_filepath"] is None
    assert call_args_1["fade_duration"] == 0.7

    # Check second call
    call_args_2 = mock_processor.generate_short.call_args_list[1].kwargs
    assert call_args_2["interval"].start_seconds == 90.0
    assert call_args_2["interval"].end_seconds == 105.0
    assert call_args_2["output_filepath"] == "output_dir/short_1.mp4"
    assert call_args_2["outro_filepath"] is None
    assert call_args_2["fade_duration"] == 0.7


def test_generate_short_use_case_empty_time():
    # Arrange
    mock_processor = Mock(spec=IVideoProcessor)
    use_case = GenerateShortUseCase(video_processor=mock_processor)
    intervals_json = [{"missing_time": "val"}, {"time": "01:30 - 01:45"}]

    def mock_generate_short(
        video,
        interval,
        target_format,
        output_filepath,
        outro_filepath=None,
        fade_duration=0.7,
    ):
        return ShortVideo(
            filepath=output_filepath,
            original_video=video,
            interval=interval,
            format=target_format,
        )

    mock_processor.generate_short.side_effect = mock_generate_short

    # Act
    shorts = use_case.execute("v.mp4", "s.srt", intervals_json, "out")

    # Assert
    assert len(shorts) == 1
    assert mock_processor.generate_short.call_count == 1
    call_args_1 = mock_processor.generate_short.call_args_list[0].kwargs
    assert call_args_1["interval"].start_seconds == 90.0
    assert call_args_1["output_filepath"] == "out/short_1.mp4"
    assert call_args_1["outro_filepath"] is None
    assert call_args_1["fade_duration"] == 0.7


def test_generate_short_use_case_with_outro_options():
    # Arrange
    mock_processor = Mock(spec=IVideoProcessor)
    use_case = GenerateShortUseCase(video_processor=mock_processor)
    intervals_json = [{"time": "00:10 - 00:20"}]

    def mock_generate_short(
        video,
        interval,
        target_format,
        output_filepath,
        outro_filepath=None,
        fade_duration=0.7,
    ):
        return ShortVideo(
            filepath=output_filepath,
            original_video=video,
            interval=interval,
            format=target_format,
        )

    mock_processor.generate_short.side_effect = mock_generate_short

    # Act
    shorts = use_case.execute(
        video_filepath="v.mp4",
        subtitles_filepath="s.srt",
        intervals_json=intervals_json,
        output_dir="out",
        outro_filepath="inputs/outroShort.mp4",
        fade_duration=1.2,
    )

    # Assert
    assert len(shorts) == 1
    call_args = mock_processor.generate_short.call_args_list[0].kwargs
    assert call_args["outro_filepath"] == "inputs/outroShort.mp4"
    assert call_args["fade_duration"] == 1.2

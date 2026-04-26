from dataclasses import dataclass
from unittest.mock import Mock

from src.application.cli_runner import CliExecutionRequest, RunShortsCliUseCase
from src.application.use_cases import ResolvedIntervals
from src.domain.exceptions import ShortGeneratorError
from src.interfaces.cli_utils import IntervalsFileResolution, OutroResolution


@dataclass(frozen=True)
class _FileCheckStub:
    video_exists: bool = True
    subs_exists: bool = True

    def exists(self, filepath: str) -> bool:
        known_paths = {
            "video.mp4": self.video_exists,
            "captions.srt": self.subs_exists,
            "inputs/outroShort.mp4": True,
            "inputs/recortes.json": True,
        }
        return known_paths.get(filepath, False)


def test_run_shorts_cli_use_case_returns_validation_error_when_video_is_missing():
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub(video_exists=False).exists,
        resolve_outro=Mock(),
        load_intervals=Mock(),
        interval_generator_factory=Mock(),
        create_interval_resolver=Mock(),
        persist_intervals=Mock(),
        generate_shorts=Mock(),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(
        CliExecutionRequest(
            video_filepath="video.mp4",
            subtitles_filepath="captions.srt",
            intervals_filepath="inputs/recortes.json",
            output_dir="outputs",
            enable_outro=False,
            outro_filepath="inputs/outroShort.mp4",
            fade_duration=0.6,
            auto_intervals=False,
        )
    )

    assert result.exit_code == 1
    assert result.output_messages == ("Error: Video file not found: video.mp4",)


def test_run_shorts_cli_use_case_reuses_existing_intervals_and_guides_about_auto_flag():
    resolve_outro = Mock(return_value=OutroResolution(filepath=None, warning_message=None))
    load_intervals = Mock(
        return_value=IntervalsFileResolution(
            payload=[{"time": "00:00:20,000 - 00:00:40,000"}],
            warning_message=None,
        )
    )
    interval_generator_resolution = Mock(generator=Mock(), warning_message=None, info_message="Gemini configured")
    resolve_intervals = Mock(
        return_value=ResolvedIntervals(
            intervals_json=[{"time": "00:00:20,000 - 00:00:40,000"}],
            source="manual",
            warning_message=None,
        )
    )
    generate_shorts = Mock(return_value=[Mock(filepath="outputs/short_0.mp4")])
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=resolve_outro,
        load_intervals=load_intervals,
        interval_generator_factory=Mock(return_value=interval_generator_resolution),
        create_interval_resolver=Mock(return_value=resolve_intervals),
        persist_intervals=Mock(),
        generate_shorts=generate_shorts,
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(
        CliExecutionRequest(
            video_filepath="video.mp4",
            subtitles_filepath="captions.srt",
            intervals_filepath="inputs/recortes.json",
            output_dir="outputs",
            enable_outro=False,
            outro_filepath="inputs/outroShort.mp4",
            fade_duration=0.6,
            auto_intervals=False,
        )
    )

    assert result.exit_code == 0
    assert any("--auto-intervals" in message for message in result.output_messages)
    assert any("Generating 1 shorts..." in message for message in result.output_messages)
    generate_shorts.assert_called_once()


def test_run_shorts_cli_use_case_persists_auto_intervals_and_reports_generator_message():
    generator = Mock()
    generator.last_generation_message = "Gemini interval selection succeeded with model gemini-x."
    resolve_intervals = Mock(
        return_value=ResolvedIntervals(
            intervals_json=[{"time": "00:01:00,000 - 00:01:24,000"}],
            source="auto",
            warning_message=None,
        )
    )
    persist_intervals = Mock()
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(return_value=IntervalsFileResolution(payload=None, warning_message=None)),
        interval_generator_factory=Mock(
            return_value=Mock(
                generator=generator, warning_message=None, info_message="Interval generation provider: gemini"
            )
        ),
        create_interval_resolver=Mock(return_value=resolve_intervals),
        persist_intervals=persist_intervals,
        generate_shorts=Mock(return_value=[Mock(filepath="outputs/short_0.mp4")]),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(
        CliExecutionRequest(
            video_filepath="video.mp4",
            subtitles_filepath="captions.srt",
            intervals_filepath="inputs/recortes.json",
            output_dir="outputs",
            enable_outro=False,
            outro_filepath="inputs/outroShort.mp4",
            fade_duration=0.6,
            auto_intervals=True,
        )
    )

    assert result.exit_code == 0
    assert "Gemini interval selection succeeded with model gemini-x." in result.output_messages
    persist_intervals.assert_called_once_with(
        "inputs/recortes.json",
        [{"time": "00:01:00,000 - 00:01:24,000"}],
    )


def test_run_shorts_cli_use_case_returns_processing_error_when_interval_resolution_fails():
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(return_value=IntervalsFileResolution(payload=None, warning_message=None)),
        interval_generator_factory=Mock(return_value=Mock(generator=Mock(), warning_message=None, info_message=None)),
        create_interval_resolver=Mock(return_value=Mock(side_effect=ShortGeneratorError("boom"))),
        persist_intervals=Mock(),
        generate_shorts=Mock(),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(
        CliExecutionRequest(
            video_filepath="video.mp4",
            subtitles_filepath="captions.srt",
            intervals_filepath="inputs/recortes.json",
            output_dir="outputs",
            enable_outro=False,
            outro_filepath="inputs/outroShort.mp4",
            fade_duration=0.6,
            auto_intervals=True,
        )
    )

    assert result.exit_code == 1
    assert result.output_messages == ("An error occurred during processing: boom",)


def test_run_shorts_cli_use_case_translates_invalid_intervals_json_error():
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(side_effect=ValueError("Expecting value: line 1 column 1")),
        interval_generator_factory=Mock(),
        create_interval_resolver=Mock(),
        persist_intervals=Mock(),
        generate_shorts=Mock(),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(
        CliExecutionRequest(
            video_filepath="video.mp4",
            subtitles_filepath="captions.srt",
            intervals_filepath="inputs/recortes.json",
            output_dir="outputs",
            enable_outro=False,
            outro_filepath="inputs/outroShort.mp4",
            fade_duration=0.6,
            auto_intervals=True,
        )
    )

    assert result.exit_code == 1
    assert result.output_messages == (
        "Error: Invalid JSON formulation in inputs/recortes.json\nExpecting value: line 1 column 1",
    )

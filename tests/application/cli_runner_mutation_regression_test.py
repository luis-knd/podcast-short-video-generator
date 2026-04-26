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
        mapping = {
            "video.mp4": self.video_exists,
            "captions.srt": self.subs_exists,
            "inputs/outroShort.mp4": True,
            "inputs/recortes.json": True,
        }
        return mapping.get(filepath, False)


class _GeneratorResolution:
    def __init__(self, generator, info_message=None, warning_message=None):
        self.generator = generator
        self.info_message = info_message
        self.warning_message = warning_message


def _request(**overrides) -> CliExecutionRequest:
    payload = {
        "video_filepath": "video.mp4",
        "subtitles_filepath": "captions.srt",
        "intervals_filepath": "inputs/recortes.json",
        "output_dir": "outputs",
        "enable_outro": False,
        "outro_filepath": "inputs/outroShort.mp4",
        "fade_duration": 0.6,
        "auto_intervals": False,
    }
    payload.update(overrides)
    return CliExecutionRequest(**payload)


def test_run_shorts_cli_use_case_passes_exact_arguments_to_collaborators_on_manual_flow():
    resolve_outro = Mock(return_value=OutroResolution(filepath="resolved-outro.mp4", warning_message="outro warning"))
    load_intervals = Mock(
        return_value=IntervalsFileResolution(
            payload=[{"time": "00:00:20,000 - 00:00:40,000"}],
            warning_message="interval warning",
        )
    )
    generator = Mock(last_generation_message="should not be shown on manual flow")
    factory = Mock(
        return_value=_GeneratorResolution(generator, info_message="info message", warning_message="factory warning")
    )
    interval_resolver = Mock(
        return_value=ResolvedIntervals(
            intervals_json=[{"time": "00:00:20,000 - 00:00:40,000"}],
            source="manual",
            warning_message="resolver warning",
        )
    )
    create_interval_resolver = Mock(return_value=interval_resolver)
    persist_intervals = Mock()
    generate_shorts = Mock(return_value=[Mock(filepath="outputs/short_0.mp4")])
    ensure_output_dir = Mock()
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=resolve_outro,
        load_intervals=load_intervals,
        interval_generator_factory=factory,
        create_interval_resolver=create_interval_resolver,
        persist_intervals=persist_intervals,
        generate_shorts=generate_shorts,
        ensure_output_dir=ensure_output_dir,
    )

    result = use_case.execute(_request(enable_outro=True))

    assert result.exit_code == 0
    assert tuple(short.filepath for short in result.generated_shorts) == ("outputs/short_0.mp4",)
    assert result.output_messages == (
        "outro warning",
        "interval warning",
        "info message",
        "factory warning",
        "Using existing intervals file without regeneration. "
        "Pass --auto-intervals to rebuild it with the configured automatic selector.",
        "resolver warning",
        "Generating 1 shorts...",
        "Successfully generated 1 shorts in outputs/",
        " - outputs/short_0.mp4",
    )
    ensure_output_dir.assert_called_once_with("outputs")
    resolve_outro.assert_called_once_with(enable_outro=True, outro_filepath="inputs/outroShort.mp4")
    load_intervals.assert_called_once_with("inputs/recortes.json", allow_invalid_json_warning=False)
    factory.assert_called_once_with()
    create_interval_resolver.assert_called_once_with(generator)
    interval_resolver.assert_called_once_with(
        subtitles_filepath="captions.srt",
        manual_intervals_json=[{"time": "00:00:20,000 - 00:00:40,000"}],
        force_auto_generation=False,
    )
    generate_shorts.assert_called_once_with(
        video_filepath="video.mp4",
        subtitles_filepath="captions.srt",
        intervals_json=[{"time": "00:00:20,000 - 00:00:40,000"}],
        output_dir="outputs",
        outro_filepath="resolved-outro.mp4",
        fade_duration=0.6,
    )
    persist_intervals.assert_not_called()


def test_run_shorts_cli_use_case_persists_auto_generated_intervals_and_reports_exact_messages():
    generator = Mock(last_generation_message="Gemini interval selection succeeded with model gemini-x.")
    persist_intervals = Mock()
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(
            return_value=IntervalsFileResolution(
                payload=[{"time": "00:01:00,000 - 00:01:24,000"}],
                warning_message=None,
            )
        ),
        interval_generator_factory=Mock(
            return_value=_GeneratorResolution(
                generator, info_message="Interval generation provider: gemini", warning_message=None
            )
        ),
        create_interval_resolver=Mock(
            return_value=Mock(
                return_value=ResolvedIntervals(
                    intervals_json=[{"time": "00:01:00,000 - 00:01:24,000"}],
                    source="auto",
                    warning_message=None,
                )
            )
        ),
        persist_intervals=persist_intervals,
        generate_shorts=Mock(return_value=[Mock(filepath="outputs/short_0.mp4")]),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(_request(auto_intervals=True))

    use_case.load_intervals.assert_called_once_with("inputs/recortes.json", allow_invalid_json_warning=True)
    use_case.create_interval_resolver.assert_called_once_with(generator)
    use_case.create_interval_resolver.return_value.assert_called_once_with(
        subtitles_filepath="captions.srt",
        manual_intervals_json=[{"time": "00:01:00,000 - 00:01:24,000"}],
        force_auto_generation=True,
    )
    assert result.output_messages == (
        "Interval generation provider: gemini",
        "Gemini interval selection succeeded with model gemini-x.",
        "Automatic interval generation finished, but the resulting JSON matches the existing intervals file.",
        "Generated 1 intervals and saved them to inputs/recortes.json",
        "Generating 1 shorts...",
        "Successfully generated 1 shorts in outputs/",
        " - outputs/short_0.mp4",
    )
    persist_intervals.assert_called_once_with(
        "inputs/recortes.json",
        [{"time": "00:01:00,000 - 00:01:24,000"}],
    )


def test_run_shorts_cli_use_case_skips_generation_message_when_source_is_manual_even_if_generator_has_one():
    generator = Mock(last_generation_message="should stay hidden")
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(
            return_value=IntervalsFileResolution(
                payload=[{"time": "00:00:20,000 - 00:00:40,000"}],
                warning_message=None,
            )
        ),
        interval_generator_factory=Mock(
            return_value=_GeneratorResolution(generator, info_message=None, warning_message=None)
        ),
        create_interval_resolver=Mock(
            return_value=Mock(
                return_value=ResolvedIntervals(
                    intervals_json=[{"time": "00:00:20,000 - 00:00:40,000"}],
                    source="manual",
                    warning_message=None,
                )
            )
        ),
        persist_intervals=Mock(),
        generate_shorts=Mock(return_value=[Mock(filepath="outputs/short_0.mp4")]),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(_request())

    assert "should stay hidden" not in result.output_messages


def test_run_shorts_cli_use_case_only_reports_matching_auto_json_when_existing_payload_is_equal():
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(
            return_value=IntervalsFileResolution(
                payload=[{"time": "00:01:00,000 - 00:01:24,000"}],
                warning_message=None,
            )
        ),
        interval_generator_factory=Mock(return_value=_GeneratorResolution(Mock(last_generation_message=None))),
        create_interval_resolver=Mock(
            return_value=Mock(
                return_value=ResolvedIntervals(
                    intervals_json=[{"time": "00:02:00,000 - 00:02:24,000"}],
                    source="auto",
                    warning_message=None,
                )
            )
        ),
        persist_intervals=Mock(),
        generate_shorts=Mock(return_value=[Mock(filepath="outputs/short_0.mp4")]),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(_request(auto_intervals=True))

    assert all("matches the existing intervals file" not in message for message in result.output_messages)


def test_run_shorts_cli_use_case_returns_failure_when_short_generation_raises_domain_error():
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(return_value=IntervalsFileResolution(payload=None, warning_message=None)),
        interval_generator_factory=Mock(
            return_value=_GeneratorResolution(Mock(), info_message=None, warning_message=None)
        ),
        create_interval_resolver=Mock(
            return_value=Mock(
                return_value=ResolvedIntervals(
                    intervals_json=[{"time": "00:00:20,000 - 00:00:40,000"}],
                    source="auto",
                    warning_message=None,
                )
            )
        ),
        persist_intervals=Mock(),
        generate_shorts=Mock(side_effect=ShortGeneratorError("render boom")),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(_request(auto_intervals=True))

    assert result.exit_code == 1
    assert result.output_messages == ("An error occurred during processing: render boom",)


def test_run_shorts_cli_use_case_validates_subtitles_and_non_negative_fade_duration():
    missing_subs_use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub(subs_exists=False).exists,
        resolve_outro=Mock(),
        load_intervals=Mock(),
        interval_generator_factory=Mock(),
        create_interval_resolver=Mock(),
        persist_intervals=Mock(),
        generate_shorts=Mock(),
        ensure_output_dir=Mock(),
    )
    negative_fade_use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(),
        load_intervals=Mock(),
        interval_generator_factory=Mock(),
        create_interval_resolver=Mock(),
        persist_intervals=Mock(),
        generate_shorts=Mock(),
        ensure_output_dir=Mock(),
    )

    missing_subs_result = missing_subs_use_case.execute(_request())
    negative_fade_result = negative_fade_use_case.execute(_request(fade_duration=-0.1))

    assert missing_subs_result.output_messages == ("Error: Subtitles file not found: captions.srt",)
    assert negative_fade_result.output_messages == ("Error: --fade-duration must be greater than or equal to 0",)


def test_run_shorts_cli_use_case_accepts_zero_fade_duration():
    use_case = RunShortsCliUseCase(
        file_exists=_FileCheckStub().exists,
        resolve_outro=Mock(return_value=OutroResolution(filepath=None, warning_message=None)),
        load_intervals=Mock(return_value=IntervalsFileResolution(payload=None, warning_message=None)),
        interval_generator_factory=Mock(return_value=_GeneratorResolution(Mock(last_generation_message=None))),
        create_interval_resolver=Mock(
            return_value=Mock(
                return_value=ResolvedIntervals(
                    intervals_json=[{"time": "00:00:20,000 - 00:00:40,000"}],
                    source="auto",
                    warning_message=None,
                )
            )
        ),
        persist_intervals=Mock(),
        generate_shorts=Mock(return_value=[Mock(filepath="outputs/short_0.mp4")]),
        ensure_output_dir=Mock(),
    )

    result = use_case.execute(_request(fade_duration=0.0, auto_intervals=True))

    assert result.exit_code == 0

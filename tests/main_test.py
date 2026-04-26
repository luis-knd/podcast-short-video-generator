from argparse import Namespace
from json import JSONDecodeError
from unittest.mock import Mock, patch

import pytest

import main
from src.application.cli_runner import CliExecutionRequest, CliExecutionResult
from src.interfaces.cli_utils import persist_intervals_json, resolve_existing_intervals_file, resolve_outro_filepath

DEFAULT_VIDEO = "inputs/video.mp4"
DEFAULT_SUBS = "inputs/video.srt"
DEFAULT_INTERVALS = "inputs/recortes.json"
DEFAULT_OUTRO = "inputs/outroShort.mp4"
DEFAULT_OUTPUT_DIR = "outputs"


def test_resolve_outro_filepath_disabled():
    resolution = resolve_outro_filepath(
        enable_outro=False,
        outro_filepath=DEFAULT_OUTRO,
    )

    assert resolution.filepath is None
    assert resolution.warning_message is None


@patch("src.interfaces.cli_utils.os.path.exists", return_value=True)
def test_resolve_outro_filepath_enabled_and_exists(_mock_exists):
    resolution = resolve_outro_filepath(
        enable_outro=True,
        outro_filepath=DEFAULT_OUTRO,
    )

    assert resolution.filepath == DEFAULT_OUTRO
    assert resolution.warning_message is None


@patch("src.interfaces.cli_utils.os.path.exists", return_value=False)
def test_resolve_outro_filepath_enabled_and_missing(_mock_exists):
    resolution = resolve_outro_filepath(
        enable_outro=True,
        outro_filepath="inputs/missing.mp4",
    )

    assert resolution.filepath is None
    assert resolution.warning_message == "Warning: Outro file not found: inputs/missing.mp4. Continuing without outro."


def test_persist_intervals_json_creates_parent_dir_and_round_trips(tmp_path):
    intervals_filepath = tmp_path / "generated" / "recortes.json"
    payload = [{"time": "00:00:10,000 - 00:00:30,000"}]

    persist_intervals_json(str(intervals_filepath), payload)

    resolution = resolve_existing_intervals_file(str(intervals_filepath), allow_invalid_json_warning=False)

    assert resolution.payload == payload
    assert resolution.warning_message is None


def test_resolve_existing_intervals_file_returns_warning_for_invalid_json_when_allowed(tmp_path):
    intervals_filepath = tmp_path / "broken.json"
    intervals_filepath.write_text("{invalid", encoding="utf-8")

    resolution = resolve_existing_intervals_file(str(intervals_filepath), allow_invalid_json_warning=True)

    assert resolution.payload is None
    assert resolution.warning_message is not None
    assert "Ignoring invalid intervals JSON" in resolution.warning_message


def test_resolve_existing_intervals_file_raises_for_invalid_json_when_warning_is_not_allowed(tmp_path):
    intervals_filepath = tmp_path / "broken.json"
    intervals_filepath.write_text("{invalid", encoding="utf-8")

    with pytest.raises(JSONDecodeError):
        resolve_existing_intervals_file(str(intervals_filepath), allow_invalid_json_warning=False)


def test_to_cli_execution_request_maps_namespace_to_application_request():
    args = Namespace(
        video=DEFAULT_VIDEO,
        subs=DEFAULT_SUBS,
        intervals=DEFAULT_INTERVALS,
        output=DEFAULT_OUTPUT_DIR,
        enable_outro=True,
        outro=DEFAULT_OUTRO,
        fade_duration=0.6,
        auto_intervals=True,
    )

    request = main.to_cli_execution_request(args)

    assert request == CliExecutionRequest(
        video_filepath=DEFAULT_VIDEO,
        subtitles_filepath=DEFAULT_SUBS,
        intervals_filepath=DEFAULT_INTERVALS,
        output_dir=DEFAULT_OUTPUT_DIR,
        enable_outro=True,
        outro_filepath=DEFAULT_OUTRO,
        fade_duration=0.6,
        auto_intervals=True,
    )


def test_main_prints_runner_messages_in_order_when_execution_succeeds():
    args = Namespace(
        video=DEFAULT_VIDEO,
        subs=DEFAULT_SUBS,
        intervals=DEFAULT_INTERVALS,
        output=DEFAULT_OUTPUT_DIR,
        enable_outro=False,
        outro=DEFAULT_OUTRO,
        fade_duration=0.7,
        auto_intervals=False,
    )
    runner = Mock(
        execute=Mock(
            return_value=CliExecutionResult(
                exit_code=0,
                output_messages=("message 1", "message 2"),
            )
        )
    )

    with (
        patch("main.argparse.ArgumentParser.parse_args", return_value=args),
        patch("main.build_cli_use_case", return_value=runner),
        patch("builtins.print") as mock_print,
    ):
        main.main()

    assert mock_print.call_args_list == [(("message 1",),), (("message 2",),)]
    runner.execute.assert_called_once()


def test_main_exits_with_runner_exit_code_when_execution_fails():
    args = Namespace(
        video=DEFAULT_VIDEO,
        subs=DEFAULT_SUBS,
        intervals=DEFAULT_INTERVALS,
        output=DEFAULT_OUTPUT_DIR,
        enable_outro=False,
        outro=DEFAULT_OUTRO,
        fade_duration=0.7,
        auto_intervals=False,
    )
    runner = Mock(
        execute=Mock(
            return_value=CliExecutionResult(
                exit_code=1,
                output_messages=("boom",),
            )
        )
    )

    with (
        patch("main.argparse.ArgumentParser.parse_args", return_value=args),
        patch("main.build_cli_use_case", return_value=runner),
        patch("builtins.print"),
        patch("main.sys.exit") as mock_exit,
    ):
        main.main()

    mock_exit.assert_called_once_with(1)

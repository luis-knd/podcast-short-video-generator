from unittest.mock import patch

from src.interfaces.cli_utils import resolve_outro_filepath


def test_resolve_outro_filepath_disabled():
    resolved_outro, warning_message = resolve_outro_filepath(
        enable_outro=False,
        outro_filepath="inputs/outroShort.mp4",
    )

    assert resolved_outro is None
    assert warning_message is None


@patch("src.interfaces.cli_utils.os.path.exists", return_value=True)
def test_resolve_outro_filepath_enabled_and_exists(_mock_exists):
    resolved_outro, warning_message = resolve_outro_filepath(
        enable_outro=True,
        outro_filepath="inputs/outroShort.mp4",
    )

    assert resolved_outro == "inputs/outroShort.mp4"
    assert warning_message is None


@patch("src.interfaces.cli_utils.os.path.exists", return_value=False)
def test_resolve_outro_filepath_enabled_and_missing(_mock_exists):
    resolved_outro, warning_message = resolve_outro_filepath(
        enable_outro=True,
        outro_filepath="inputs/missing.mp4",
    )

    assert resolved_outro is None
    assert warning_message == (
        "Warning: Outro file not found: inputs/missing.mp4. Continuing without outro."
    )

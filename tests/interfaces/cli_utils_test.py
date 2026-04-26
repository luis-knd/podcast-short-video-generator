import os
import tempfile

import pytest

from src.interfaces.cli_utils import resolve_existing_intervals_file, resolve_outro_filepath


@pytest.mark.parametrize(
    ("enable_outro", "filepath"),
    [
        (False, "any/path.mp4"),
        (False, ""),
    ],
)
def test_resolve_outro_filepath_returns_none_when_disabled(enable_outro, filepath):
    resolution = resolve_outro_filepath(enable_outro, filepath)

    assert resolution.filepath is None
    assert resolution.warning_message is None


def test_resolve_outro_filepath_returns_path_when_enabled_and_file_exists():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        outro_path = tmp.name

    try:
        resolution = resolve_outro_filepath(True, outro_path)

        assert resolution.filepath == outro_path
        assert resolution.warning_message is None
    finally:
        os.remove(outro_path)


def test_resolve_outro_filepath_returns_warning_when_enabled_and_file_missing():
    missing_path = "/nonexistent/outro_file_abc123.mp4"

    resolution = resolve_outro_filepath(True, missing_path)

    assert resolution.filepath is None
    assert resolution.warning_message is not None
    assert missing_path in resolution.warning_message


def test_resolve_outro_filepath_checks_actual_filepath_not_none(monkeypatch):
    checked_paths: list[object] = []
    original_exists = os.path.exists

    def spy_exists(path: object) -> bool:
        checked_paths.append(path)
        return original_exists(path)

    monkeypatch.setattr(os.path, "exists", spy_exists)

    resolve_outro_filepath(True, "/some/specific/path.mp4")

    assert "/some/specific/path.mp4" in checked_paths


def test_resolve_existing_intervals_file_returns_named_resolution(tmp_path):
    intervals_filepath = tmp_path / "recortes.json"
    intervals_filepath.write_text('[{"time": "00:00:10,000 - 00:00:20,000"}]', encoding="utf-8")

    resolution = resolve_existing_intervals_file(str(intervals_filepath), allow_invalid_json_warning=False)

    assert resolution.payload == [{"time": "00:00:10,000 - 00:00:20,000"}]
    assert resolution.warning_message is None

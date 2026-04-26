import json
from unittest.mock import mock_open, patch

import pytest

from src.interfaces.cli_utils import persist_intervals_json, resolve_existing_intervals_file


def test_resolve_existing_intervals_file_opens_json_with_utf8_and_returns_exact_warning_message(tmp_path):
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{invalid", encoding="utf-8")

    with patch("builtins.open", mock_open(read_data="{invalid")) as mocked_open:
        resolution = resolve_existing_intervals_file(str(broken_path), allow_invalid_json_warning=True)

    mocked_open.assert_called_once_with(str(broken_path), encoding="utf-8")
    assert resolution.payload is None
    assert resolution.warning_message == (
        "Warning: Ignoring invalid intervals JSON in "
        f"{broken_path} while auto generation is enabled. "
        "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"
    )


def test_resolve_existing_intervals_file_raises_json_error_when_warning_mode_is_disabled(tmp_path):
    broken_path = tmp_path / "broken.json"
    broken_path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        resolve_existing_intervals_file(str(broken_path), allow_invalid_json_warning=False)


def test_persist_intervals_json_creates_parent_dir_and_writes_utf8_json_with_trailing_newline(tmp_path):
    intervals_path = tmp_path / "nested" / "recortes.json"
    payload = [{"time": "00:00:10,000 - 00:00:30,000"}]

    with patch("src.interfaces.cli_utils.os.makedirs", wraps=__import__("os").makedirs) as makedirs:
        persist_intervals_json(str(intervals_path), payload)

    makedirs.assert_called_once_with(str(intervals_path.parent), exist_ok=True)
    assert intervals_path.read_text(encoding="utf-8") == '[\n  {\n    "time": "00:00:10,000 - 00:00:30,000"\n  }\n]\n'


def test_persist_intervals_json_skips_directory_creation_for_top_level_paths(tmp_path):
    with patch("src.interfaces.cli_utils.os.makedirs") as makedirs:
        persist_intervals_json("recortes.json", [{"time": "00:00:00,000 - 00:00:10,000"}])

    makedirs.assert_not_called()


def test_persist_intervals_json_uses_utf8_write_mode_and_non_ascii_safe_dump_arguments(tmp_path):
    intervals_path = tmp_path / "recortes.json"
    payload = [{"time": "00:00:10,000 - 00:00:30,000", "label": "canción útil"}]

    with (
        patch("builtins.open", mock_open()) as mocked_open,
        patch("src.interfaces.cli_utils.json.dump") as mocked_dump,
    ):
        persist_intervals_json(str(intervals_path), payload)

    mocked_open.assert_called_once_with(str(intervals_path), "w", encoding="utf-8")
    dump_args, dump_kwargs = mocked_dump.call_args
    assert dump_args[0] == payload
    assert dump_kwargs == {"ensure_ascii": False, "indent": 2}

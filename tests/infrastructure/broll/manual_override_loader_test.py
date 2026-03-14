import json
from pathlib import Path
from unittest.mock import patch

from src.infrastructure.broll.manual_override_loader import ManualBrollOverrideLoader


def test_manual_override_loader_resolves_relative_asset_paths(tmp_path):
    asset = tmp_path / "manual" / "clip.mp4"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"video")

    overrides_file = tmp_path / "broll-overrides.json"
    overrides_file.write_text(
        json.dumps(
            {
                "version": 1,
                "overrides": [
                    {
                        "short_id": "short_2",
                        "anchor_text": "so confusing",
                        "asset_path": "manual/clip.mp4",
                        "start_ms": "1200",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    loader = ManualBrollOverrideLoader(filepath=overrides_file)
    overrides = loader.load()

    assert len(overrides) == 1
    assert overrides[0].short_id == "short_2"
    assert overrides[0].asset_path == str(asset.resolve())
    assert overrides[0].mode == "full_frame_cutaway"
    assert overrides[0].start_ms == 1200
    assert overrides[0].mute_asset_audio is True
    assert overrides[0].priority == 100
    assert overrides[0].active is True


def test_manual_override_loader_ignores_invalid_entries(tmp_path):
    overrides_file = tmp_path / "broll-overrides.json"
    overrides_file.write_text(
        json.dumps(
            {
                "overrides": [
                    {"short_id": "short_1", "anchor_text": "", "asset_path": "missing.mp4"},
                    {"short_id": "short_2", "anchor_text": "missing asset path"},
                    {"asset_path": "missing.mp4"},
                    "invalid",
                ]
            }
        ),
        encoding="utf-8",
    )

    loader = ManualBrollOverrideLoader(filepath=overrides_file)

    assert loader.load() == ()


def test_manual_override_loader_returns_empty_for_missing_or_invalid_payloads(tmp_path):
    missing_file = tmp_path / "missing.json"
    assert ManualBrollOverrideLoader(filepath=missing_file).load() == ()

    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{invalid json", encoding="utf-8")
    assert ManualBrollOverrideLoader(filepath=invalid_file).load() == ()

    wrong_shape_file = tmp_path / "wrong-shape.json"
    wrong_shape_file.write_text(json.dumps({"overrides": {"short_id": "short_1"}}), encoding="utf-8")
    assert ManualBrollOverrideLoader(filepath=wrong_shape_file).load() == ()

    empty_overrides_file = _write_overrides_file(tmp_path, {"overrides": []}, name="empty.json")
    with patch.object(type(empty_overrides_file), "read_text", return_value='{"overrides": []}') as read_text:
        assert ManualBrollOverrideLoader(filepath=empty_overrides_file).load() == ()
    read_text.assert_called_once_with(encoding="utf-8")


def test_manual_override_loader_preserves_absolute_paths_and_parses_optional_fields(tmp_path):
    asset = (tmp_path / "manual" / "clip.mp4").resolve()
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"video")

    overrides_file = tmp_path / "broll-overrides.json"
    overrides_file.write_text(
        json.dumps(
            {
                "overrides": [
                    {
                        "short_id": "short_3",
                        "anchor_text": "absolute path",
                        "asset_path": str(asset),
                        "mode": "",
                        "start_ms": "oops",
                        "end_ms": "900",
                        "mute_asset_audio": False,
                        "priority": 7,
                        "active": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    override = ManualBrollOverrideLoader(filepath=overrides_file).load()[0]

    assert override.asset_path == str(asset)
    assert override.mode == "full_frame_cutaway"
    assert override.start_ms is None
    assert override.end_ms == 900
    assert override.mute_asset_audio is False
    assert override.priority == 7
    assert override.active is False


def test_manual_override_loader_falls_back_to_project_root_for_missing_relative_assets(tmp_path):
    overrides_file = tmp_path / "nested" / "broll-overrides.json"
    overrides_file.parent.mkdir(parents=True)
    overrides_file.write_text(
        json.dumps(
            {
                "overrides": [
                    {
                        "short_id": "short_4",
                        "anchor_text": "woman smiling",
                        "asset_path": "inputs/broll/library/portrait/woman-smiling.mp4",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    override = ManualBrollOverrideLoader(filepath=overrides_file).load()[0]
    expected_asset = (Path.cwd() / "inputs" / "broll" / "library" / "portrait" / "woman-smiling.mp4").resolve()

    assert override.asset_path == str(expected_asset)


def _write_overrides_file(tmp_path: Path, payload: dict[str, object], *, name: str = "broll-overrides.json") -> Path:
    overrides_file = tmp_path / name
    overrides_file.parent.mkdir(parents=True, exist_ok=True)
    overrides_file.write_text(json.dumps(payload), encoding="utf-8")
    return overrides_file

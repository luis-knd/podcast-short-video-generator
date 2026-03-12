import json

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
                        "mode": "full_frame_cutaway",
                        "priority": 200,
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
    assert overrides[0].mute_asset_audio is True


def test_manual_override_loader_ignores_invalid_entries(tmp_path):
    overrides_file = tmp_path / "broll-overrides.json"
    overrides_file.write_text(
        json.dumps(
            {
                "overrides": [
                    {"short_id": "short_1", "anchor_text": "", "asset_path": "missing.mp4"},
                    {"asset_path": "missing.mp4"},
                    "invalid",
                ]
            }
        ),
        encoding="utf-8",
    )

    loader = ManualBrollOverrideLoader(filepath=overrides_file)

    assert loader.load() == ()

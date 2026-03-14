from src.infrastructure.broll.providers.local_still_provider import LocalMediaProvider
from tests.infrastructure.broll.providers.local_media_provider_support_test import (
    create_asset,
    search_candidates,
    write_metadata,
)


def test_local_media_provider_load_metadata_entries_skips_non_dict_assets_and_missing_paths(tmp_path):
    media_root = tmp_path / "broll"
    media_root.mkdir(parents=True)
    write_metadata(
        media_root,
        {
            "assets": [
                "not-a-dict",
                {
                    "title": "Missing path",
                    "tags": ["budget"],
                },
                {
                    "path": "city/budget-city.mp4",
                    "title": "Budget city",
                    "tags": ["budget", "city"],
                    "description": "Matching clip",
                },
            ]
        },
    )

    provider = LocalMediaProvider()
    entries = provider._load_metadata_entries(media_root)

    assert entries is not None
    assert [entry.relative_path for entry in entries] == ["city/budget-city.mp4"]
    assert entries[0].title == "Budget city"
    assert entries[0].tags == ("budget", "city")
    assert entries[0].active is True


def test_local_media_provider_limits_results_to_top_five_candidates(tmp_path):
    media_root = tmp_path / "broll"
    assets: list[dict[str, object]] = []
    for index in range(6):
        asset_path = media_root / "city" / f"budget-city-{index}.mp4"
        create_asset(asset_path, b"video")
        assets.append(
            {
                "path": f"city/budget-city-{index}.mp4",
                "title": f"Budget city {index}",
                "tags": ["budget", "city"],
                "description": "Matching city finance clip.",
                "asset_type": "video",
                "orientation": "vertical",
                "active": True,
            }
        )
    write_metadata(media_root, {"assets": assets})

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget hit the city",
        queries=("budget city",),
    )

    assert len(candidates) == 5
    assert all(candidate.title != "Budget city 0" for candidate in candidates)

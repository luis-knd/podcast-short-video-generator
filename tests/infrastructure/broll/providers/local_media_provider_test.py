import json

from src.infrastructure.broll.providers.local_still_provider import LocalMediaProvider
from tests.infrastructure.broll.providers.support_test import build_provider_test_beat


def test_local_media_provider_uses_manifest_metadata_as_primary_source(tmp_path):
    media_root = tmp_path / "broll"
    described_video = media_root / "library" / "clip-001.mp4"
    ignored_heuristic_file = media_root / "money" / "budget-crash-vertical.mp4"

    described_video.parent.mkdir(parents=True)
    ignored_heuristic_file.parent.mkdir(parents=True)

    described_video.write_bytes(b"video")
    ignored_heuristic_file.write_bytes(b"video")
    (media_root / "broll-metadata.json").write_text(
        json.dumps(
            {
                "version": 1,
                "assets": [
                    {
                        "path": "library/clip-001.mp4",
                        "title": "Phone market crash feed",
                        "tags": ["budget", "crash", "finance"],
                        "description": "Vertical phone clip showing a market collapse.",
                        "asset_type": "video",
                        "orientation": "vertical",
                        "active": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    provider = LocalMediaProvider(search_dirs=(str(media_root),))
    candidates = provider.search(
        beat=build_provider_test_beat("The budget crash hit hard"),
        queries=("budget crash",),
        cache_dir=str(tmp_path / "cache"),
    )

    assert [candidate.title for candidate in candidates] == ["Phone market crash feed"]
    assert [candidate.asset_type for candidate in candidates] == ["video"]
    assert [candidate.discovery_source for candidate in candidates] == ["local_manifest"]
    assert candidates[0].orientation == "vertical"
    assert all(candidate.local_path.endswith("clip-001.mp4") for candidate in candidates)


def test_local_media_provider_probes_video_metadata_for_manifest_candidates(tmp_path, monkeypatch):
    media_root = tmp_path / "broll"
    described_video = media_root / "library" / "clip-001.mp4"

    described_video.parent.mkdir(parents=True)
    described_video.write_bytes(b"video")
    (media_root / "broll-metadata.json").write_text(
        json.dumps(
            {
                "version": 1,
                "assets": [
                    {
                        "path": "library/clip-001.mp4",
                        "title": "Confusing grammar scene",
                        "tags": ["confusing", "grammar", "english"],
                        "description": "Scene for confusing language moments.",
                        "asset_type": "video",
                        "active": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    provider = LocalMediaProvider(search_dirs=(str(media_root),))
    monkeypatch.setattr(
        provider,
        "_run_ffprobe",
        lambda asset_path, fallback_orientation: (5208, 464, 832, "vertical"),
    )

    candidates = provider.search(
        beat=build_provider_test_beat("It's so confusing with all those negatives."),
        queries=("confusing negatives",),
        cache_dir=str(tmp_path / "cache"),
    )

    assert candidates[0].duration_ms == 5208
    assert candidates[0].width == 464
    assert candidates[0].height == 832
    assert candidates[0].orientation == "vertical"


def test_local_media_provider_falls_back_to_names_and_folders_without_manifest(tmp_path):
    media_root = tmp_path / "broll"
    matching_video = media_root / "money" / "budget-crash-vertical.mp4"
    matching_image = media_root / "city" / "night-street.png"
    ignored_video = media_root / "nature" / "forest.mp4"

    matching_video.parent.mkdir(parents=True)
    matching_image.parent.mkdir(parents=True)
    ignored_video.parent.mkdir(parents=True)

    matching_video.write_bytes(b"video")
    matching_image.write_bytes(b"image")
    ignored_video.write_bytes(b"video")

    provider = LocalMediaProvider(search_dirs=(str(media_root),))

    candidates = provider.search(
        beat=build_provider_test_beat("The budget crash hit the city"),
        queries=("budget crash", "city street"),
        cache_dir=str(tmp_path / "cache"),
    )

    assert [candidate.title for candidate in candidates] == ["budget-crash-vertical", "night-street"]
    assert [candidate.asset_type for candidate in candidates] == ["video", "image"]
    assert [candidate.discovery_source for candidate in candidates] == [
        "local_heuristic_fallback",
        "local_heuristic_fallback",
    ]
    assert candidates[0].orientation == "vertical"
    assert candidates[1].orientation == "square"
    assert all("forest" not in candidate.title for candidate in candidates)

from src.infrastructure.broll.providers.local_still_provider import LocalMediaProvider
from tests.infrastructure.broll.providers.local_media_provider_support_test import (
    create_asset,
    search_candidates,
    write_metadata,
)
from tests.infrastructure.broll.providers.support_test import build_provider_test_beat


def test_local_media_provider_uses_manifest_metadata_as_primary_source(tmp_path):
    media_root = tmp_path / "broll"
    described_video = media_root / "library" / "clip-001.mp4"
    ignored_heuristic_file = media_root / "money" / "budget-crash-vertical.mp4"

    create_asset(described_video, b"video")
    create_asset(ignored_heuristic_file, b"video")
    write_metadata(
        media_root,
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
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget crash hit hard",
        queries=("budget crash",),
    )

    assert [candidate.title for candidate in candidates] == ["Phone market crash feed"]
    assert [candidate.asset_type for candidate in candidates] == ["video"]
    assert [candidate.discovery_source for candidate in candidates] == ["local_manifest"]
    assert candidates[0].candidate_id == "local-library-clip-001.mp4"
    assert candidates[0].orientation == "vertical"
    assert all(candidate.local_path.endswith("clip-001.mp4") for candidate in candidates)


def test_local_media_provider_probes_video_metadata_for_manifest_candidates(tmp_path, monkeypatch):
    media_root = tmp_path / "broll"
    described_video = media_root / "library" / "clip-001.mp4"

    create_asset(described_video, b"video")
    write_metadata(
        media_root,
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
        },
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


def test_local_media_provider_keeps_searching_other_directories_after_manifest_directory(tmp_path):
    manifest_root = tmp_path / "manifest-root"
    fallback_root = tmp_path / "fallback-root"
    described_video = manifest_root / "library" / "clip-001.mp4"
    fallback_video = fallback_root / "money" / "budget-crash-vertical.mp4"

    create_asset(described_video, b"video")
    create_asset(fallback_video, b"video")
    write_metadata(
        manifest_root,
        {
            "assets": [
                {
                    "path": "library/clip-001.mp4",
                    "title": "Unrelated office clip",
                    "tags": ["office", "meeting"],
                    "description": "Does not match the requested beat.",
                    "asset_type": "video",
                    "orientation": "vertical",
                    "active": True,
                }
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(manifest_root, fallback_root),
        beat_text="The budget crash hit hard",
        queries=("budget crash",),
    )

    assert [candidate.title for candidate in candidates] == ["budget-crash-vertical"]
    assert candidates[0].candidate_id == "local-money-budget-crash-vertical.mp4"


def test_local_media_provider_prefers_manifest_videos_over_images_when_overlap_is_equal(tmp_path):
    media_root = tmp_path / "broll"
    image = media_root / "city" / "z-budget-city.png"
    video = media_root / "city" / "a-budget-city.mp4"

    create_asset(image, b"image")
    create_asset(video, b"video")
    write_metadata(
        media_root,
        {
            "assets": [
                {
                    "path": "city/z-budget-city.png",
                    "title": "Z budget city",
                    "tags": ["budget", "city"],
                    "description": "Square city image.",
                    "asset_type": "image",
                    "orientation": "square",
                    "active": True,
                },
                {
                    "path": "city/a-budget-city.mp4",
                    "title": "A budget city",
                    "tags": ["budget", "city"],
                    "description": "Square city video.",
                    "asset_type": "video",
                    "orientation": "square",
                    "active": True,
                },
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget hit the city",
        queries=("budget city",),
    )

    assert [candidate.asset_type for candidate in candidates] == ["video", "image"]
    assert [candidate.title for candidate in candidates] == ["A budget city", "Z budget city"]


def test_local_media_provider_keeps_matching_manifest_entries_after_initial_miss(tmp_path):
    media_root = tmp_path / "broll"
    missed_first = media_root / "office" / "meeting.mp4"
    matched_second = media_root / "money" / "budget-crash.mp4"

    create_asset(missed_first, b"video")
    create_asset(matched_second, b"video")
    write_metadata(
        media_root,
        {
            "assets": [
                {
                    "path": "office/meeting.mp4",
                    "title": "Office meeting",
                    "tags": ["office", "meeting"],
                    "description": "Does not match the requested beat.",
                    "asset_type": "video",
                    "orientation": "landscape",
                    "active": True,
                },
                {
                    "path": "money/budget-crash.mp4",
                    "title": "Budget crash",
                    "tags": ["budget", "crash"],
                    "description": "Matching financial clip.",
                    "asset_type": "video",
                    "orientation": "landscape",
                    "active": True,
                },
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget crash hit hard",
        queries=("budget crash",),
    )

    assert [candidate.title for candidate in candidates] == ["Budget crash"]


def test_local_media_provider_sorts_identical_priority_candidates_without_crashing(tmp_path):
    media_root = tmp_path / "broll"
    first_image = media_root / "city" / "budget-city-a.png"
    second_image = media_root / "city" / "budget-city-b.png"

    create_asset(first_image, b"image")
    create_asset(second_image, b"image")
    write_metadata(
        media_root,
        {
            "assets": [
                {
                    "path": "city/budget-city-a.png",
                    "title": "Budget city",
                    "tags": ["budget", "city"],
                    "description": "City finance still.",
                    "asset_type": "image",
                    "orientation": "square",
                    "active": True,
                },
                {
                    "path": "city/budget-city-b.png",
                    "title": "Budget city",
                    "tags": ["budget", "city"],
                    "description": "City finance still.",
                    "asset_type": "image",
                    "orientation": "square",
                    "active": True,
                },
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget hit the city",
        queries=("budget city",),
    )

    assert [candidate.candidate_id for candidate in candidates] == [
        "local-city-budget-city-a.png",
        "local-city-budget-city-b.png",
    ]


def test_local_media_provider_prefers_vertical_manifest_images_when_overlap_is_equal(tmp_path):
    media_root = tmp_path / "broll"
    vertical_image = media_root / "city" / "a-budget-frame.png"
    square_image = media_root / "city" / "z-budget-frame.png"

    create_asset(vertical_image, b"image")
    create_asset(square_image, b"image")
    write_metadata(
        media_root,
        {
            "assets": [
                {
                    "path": "city/a-budget-frame.png",
                    "title": "A budget frame",
                    "tags": ["budget", "city"],
                    "description": "Vertical budget still.",
                    "asset_type": "image",
                    "orientation": "vertical",
                    "active": True,
                },
                {
                    "path": "city/z-budget-frame.png",
                    "title": "Z budget frame",
                    "tags": ["budget", "city"],
                    "description": "Square budget still.",
                    "asset_type": "image",
                    "orientation": "square",
                    "active": True,
                },
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget hit the city",
        queries=("budget city",),
    )

    assert [candidate.title for candidate in candidates] == ["A budget frame", "Z budget frame"]


def test_local_media_provider_uses_generated_tags_for_manifest_image_and_skips_invalid_entries(tmp_path):
    media_root = tmp_path / "broll"
    valid_image = media_root / "city" / "night-street.png"
    invalid_asset = media_root / "city" / "unsupported.wav"
    inactive_video = media_root / "city" / "inactive.mp4"

    create_asset(valid_image, b"image")
    create_asset(invalid_asset, b"audio")
    create_asset(inactive_video, b"video")
    write_metadata(
        media_root,
        {
            "assets": [
                {
                    "path": "city/night-street.png",
                    "title": "Night Street",
                    "tags": "not-a-list",
                    "description": "City square lights",
                    "active": True,
                },
                {
                    "path": "city/missing.mp4",
                    "title": "Missing clip",
                    "tags": ["city"],
                    "description": "Should be ignored because file is absent",
                    "active": True,
                },
                {
                    "path": "city/unsupported.wav",
                    "title": "Audio asset",
                    "asset_type": "audio",
                    "description": "Should be ignored because asset type is unsupported",
                    "active": True,
                },
                {
                    "path": "city/inactive.mp4",
                    "title": "Inactive clip",
                    "tags": ["city"],
                    "description": "Should be ignored because it is inactive",
                    "active": False,
                },
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The city street was bright",
        queries=("city street",),
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Night Street"
    assert candidate.candidate_id == "local-city-night-street.png"
    assert candidate.asset_type == "image"
    assert candidate.orientation == "square"
    assert candidate.duration_ms == 0
    assert candidate.width == 1080
    assert candidate.height == 1080
    assert "city" in candidate.tags
    assert "street" in candidate.tags
    assert all(item.title != "Inactive clip" for item in candidates)


def test_local_media_provider_skips_invalid_manifest_entries_without_stopping(tmp_path):
    media_root = tmp_path / "broll"
    inactive_clip = media_root / "city" / "inactive.mp4"
    unsupported_asset = media_root / "city" / "audio.wav"
    matching_video = media_root / "city" / "budget-city.mp4"

    create_asset(inactive_clip, b"video")
    create_asset(unsupported_asset, b"audio")
    create_asset(matching_video, b"video")
    write_metadata(
        media_root,
        {
            "assets": [
                {
                    "path": "city/inactive.mp4",
                    "title": "Inactive clip",
                    "tags": ["budget", "city"],
                    "description": "Should be skipped because it is inactive.",
                    "asset_type": "video",
                    "orientation": "vertical",
                    "active": False,
                },
                {
                    "path": "city/missing.mp4",
                    "title": "Missing clip",
                    "tags": ["budget", "city"],
                    "description": "Should be skipped because file is absent.",
                    "asset_type": "video",
                    "orientation": "vertical",
                    "active": True,
                },
                {
                    "path": "city/audio.wav",
                    "title": "Unsupported clip",
                    "tags": ["budget", "city"],
                    "description": "Should be skipped because type is unsupported.",
                    "asset_type": "audio",
                    "orientation": "vertical",
                    "active": True,
                },
                {
                    "path": "city/budget-city.mp4",
                    "title": "Budget city",
                    "tags": ["budget", "city"],
                    "description": "The only valid matching clip.",
                    "asset_type": "video",
                    "orientation": "vertical",
                    "active": True,
                },
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget hit the city",
        queries=("budget city",),
    )

    assert [candidate.title for candidate in candidates] == ["Budget city"]


def test_local_media_provider_preserves_vertical_manifest_orientation_for_images(tmp_path):
    media_root = tmp_path / "broll"
    poster = media_root / "portrait" / "speaker-poster.png"

    create_asset(poster, b"image")
    write_metadata(
        media_root,
        {
            "assets": [
                {
                    "path": "portrait/speaker-poster.png",
                    "title": "Speaker poster",
                    "description": "Vertical image asset.",
                    "tags": ["speaker", "poster"],
                    "asset_type": "image",
                    "orientation": "vertical",
                    "active": True,
                }
            ]
        },
    )

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The speaker poster was ready",
        queries=("speaker poster",),
    )

    assert len(candidates) == 1
    assert candidates[0].orientation == "vertical"
    assert candidates[0].width == 1080
    assert candidates[0].height == 1080


def test_local_media_provider_returns_no_candidates_for_malformed_manifest(tmp_path):
    media_root = tmp_path / "broll"
    matching_video = media_root / "money" / "budget-crash-vertical.mp4"
    create_asset(matching_video, b"video")
    (media_root / "broll-metadata.json").write_text("{invalid json", encoding="utf-8")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget crash hit hard",
        queries=("budget crash",),
    )

    assert candidates == []

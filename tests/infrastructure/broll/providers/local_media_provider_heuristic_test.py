from src.domain.broll_models import BrollCandidate
from src.infrastructure.broll.providers.local_still_provider import LocalMediaProvider
from tests.infrastructure.broll.providers.local_media_provider_support_test import create_asset, search_candidates
from tests.infrastructure.broll.providers.support_test import build_provider_test_beat


def test_local_media_provider_falls_back_to_names_and_folders_without_manifest(tmp_path):
    media_root = tmp_path / "broll"
    matching_video = media_root / "money" / "budget-crash-vertical.mp4"
    matching_image = media_root / "city" / "night-street.png"
    ignored_video = media_root / "nature" / "forest.mp4"

    create_asset(matching_video, b"video")
    create_asset(matching_image, b"image")
    create_asset(ignored_video, b"video")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget crash hit the city",
        queries=("budget crash", "city street"),
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


def test_local_media_provider_matches_query_tokens_even_when_beat_tokens_do_not_overlap(tmp_path):
    media_root = tmp_path / "broll"
    query_only_video = media_root / "money" / "budget-crash-vertical.mp4"
    create_asset(query_only_video, b"video")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The quiet office meeting ended",
        queries=("budget crash",),
    )

    assert len(candidates) == 1
    assert candidates[0].title == "budget-crash-vertical"


def test_local_media_provider_prefers_heuristic_videos_when_overlap_is_equal(tmp_path):
    media_root = tmp_path / "broll"
    image = media_root / "city" / "z-budget-city-portrait.png"
    video = media_root / "city" / "a-budget-city-vertical.mp4"

    create_asset(image, b"image")
    create_asset(video, b"video")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget hit the city",
        queries=("budget city",),
    )

    assert [candidate.asset_type for candidate in candidates] == ["video", "image"]
    assert [candidate.orientation for candidate in candidates] == ["vertical", "vertical"]
    assert [candidate.title for candidate in candidates] == [
        "a-budget-city-vertical",
        "z-budget-city-portrait",
    ]


def test_local_media_provider_prefers_vertical_heuristic_images_when_overlap_is_equal(tmp_path):
    media_root = tmp_path / "broll"
    vertical_image = media_root / "city" / "a-budget-city-portrait.png"
    square_image = media_root / "city" / "z-budget-city-square.png"

    create_asset(vertical_image, b"image")
    create_asset(square_image, b"image")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget hit the city",
        queries=("budget city",),
    )

    assert [candidate.title for candidate in candidates] == [
        "a-budget-city-portrait",
        "z-budget-city-square",
    ]
    assert [candidate.orientation for candidate in candidates] == ["vertical", "square"]


def test_local_media_provider_returns_empty_without_search_dirs_and_keeps_prepared_candidate():
    provider = LocalMediaProvider()
    candidate = BrollCandidate(
        candidate_id="local-asset",
        provider="local_media",
        discovery_source="local_manifest",
        asset_type="video",
        asset_url="/tmp/asset.mp4",
        local_path="/tmp/asset.mp4",
        duration_ms=2000,
        width=720,
        height=1280,
        orientation="vertical",
        title="local asset",
    )

    candidates = provider.search(
        beat=build_provider_test_beat("market crash"),
        queries=("market crash",),
        cache_dir="cache",
    )

    assert candidates == []
    assert provider.prepare_asset(candidate, cache_dir="cache") == candidate


def test_local_media_provider_detects_portrait_keyword_as_vertical_without_manifest(tmp_path):
    media_root = tmp_path / "broll"
    portrait_image = media_root / "people" / "speaker-portrait-frame.png"
    create_asset(portrait_image, b"image")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The speaker portrait filled the screen",
        queries=("speaker portrait",),
    )

    assert len(candidates) == 1
    assert candidates[0].title == "speaker-portrait-frame"
    assert candidates[0].orientation == "vertical"
    assert candidates[0].asset_type == "image"


def test_local_media_provider_detects_reel_keyword_as_vertical_without_manifest(tmp_path):
    media_root = tmp_path / "broll"
    reel_image = media_root / "social" / "speaker-reel-frame.png"
    create_asset(reel_image, b"image")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The speaker reel filled the screen",
        queries=("speaker reel",),
    )

    assert len(candidates) == 1
    assert candidates[0].orientation == "vertical"


def test_local_media_provider_ignores_directories_that_look_like_media_files(tmp_path):
    media_root = tmp_path / "broll"
    fake_video_directory = media_root / "city" / "budget-crash.mp4"
    real_video = media_root / "city" / "real-budget-crash.mp4"
    fake_video_directory.mkdir(parents=True)
    create_asset(real_video, b"video")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget crash hit the city",
        queries=("budget crash",),
    )

    assert [candidate.title for candidate in candidates] == ["real-budget-crash"]
    assert [candidate.local_path for candidate in candidates] == [str(real_video)]


def test_local_media_provider_heuristic_candidates_keep_sorted_token_tags(tmp_path):
    media_root = tmp_path / "broll"
    image = media_root / "city" / "night-street.png"
    create_asset(image, b"image")

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The city street changed at night",
        queries=("night street",),
    )

    assert len(candidates) == 1
    assert candidates[0].tags == ("city", "night", "png", "street")

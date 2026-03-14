import json
from unittest.mock import patch

from src.domain.broll_models import BrollCandidate
from src.infrastructure.broll.providers.pexels_provider import PexelsBrollProvider
from src.infrastructure.broll.providers.pixabay_provider import PixabayBrollProvider
from tests.infrastructure.broll.providers.support_test import build_provider_test_beat


def json_response(payload: dict[str, object]):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        @staticmethod
        def read():
            return json.dumps(payload).encode("utf-8")

    return FakeResponse()


def test_pexels_provider_marks_candidates_with_discovery_source():
    provider = PexelsBrollProvider(api_key="test-key")

    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen",
        return_value=json_response(
            {
                "videos": [
                    {
                        "id": 123,
                        "duration": 3,
                        "width": 720,
                        "height": 1280,
                        "url": "https://pexels.example/clip",
                        "video_files": [
                            {
                                "link": "https://cdn.example/clip.mp4",
                                "width": 720,
                                "height": 1280,
                            }
                        ],
                    }
                ]
            }
        ),
    ):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert len(candidates) == 1
    assert candidates[0].provider == "pexels"
    assert candidates[0].discovery_source == "pexels"
    assert candidates[0].title == "market crash"
    assert "market" in candidates[0].tags
    assert "crash" in candidates[0].tags


def test_pexels_provider_uses_expected_headers_for_search_and_prepare():
    provider = PexelsBrollProvider(api_key="test-key")
    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen",
        return_value=json_response({"videos": []}),
    ) as mocked_urlopen:
        provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    request = mocked_urlopen.call_args.args[0]
    assert request.headers["Authorization"] == "test-key"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["User-agent"] == provider.USER_AGENT

    candidate = BrollCandidate(
        candidate_id="pexels-1",
        provider="pexels",
        discovery_source="pexels",
        asset_type="video",
        asset_url="https://cdn.example/pexels.mp4",
        local_path=None,
        duration_ms=4000,
        width=720,
        height=1280,
        orientation="vertical",
        title="market crash",
    )

    with patch.object(provider.asset_cache, "ensure_downloaded", return_value="/tmp/pexels.mp4") as ensure_downloaded:
        prepared = provider.prepare_asset(candidate, cache_dir="cache")

    assert prepared.local_path == "/tmp/pexels.mp4"
    assert ensure_downloaded.call_args.kwargs == {
        "source_url": "https://cdn.example/pexels.mp4",
        "cache_dir": "cache/pexels",
        "filename": "pexels-1",
        "headers": {
            "Authorization": "test-key",
            "Accept": "application/json",
            "User-Agent": provider.USER_AGENT,
        },
    }


def test_pexels_provider_returns_empty_without_api_key_and_keeps_local_assets():
    provider = PexelsBrollProvider(api_key=None)

    assert provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache") == []

    local_candidate = BrollCandidate(
        candidate_id="pexels-local",
        provider="pexels",
        discovery_source="pexels",
        asset_type="video",
        asset_url="https://cdn.example/pexels.mp4",
        local_path="/tmp/already-downloaded.mp4",
        duration_ms=4000,
        width=720,
        height=1280,
        orientation="vertical",
        title="market crash",
    )

    assert provider.prepare_asset(local_candidate, cache_dir="cache") == local_candidate


def test_pexels_provider_uses_first_video_file_without_link_and_adds_user_tokens():
    provider = PexelsBrollProvider(api_key="test-key")
    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen",
        return_value=json_response(
            {
                "videos": [
                    {"id": 1, "duration": 1, "video_files": []},
                    {
                        "id": 2,
                        "duration": 2.5,
                        "width": 640,
                        "height": 640,
                        "user": {"name": "Jane-Doe"},
                        "video_files": [{"width": 640, "height": 640}],
                    },
                ]
            }
        ),
    ):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert len(candidates) == 1
    assert candidates[0].asset_url == ""
    assert candidates[0].duration_ms == 2500
    assert candidates[0].orientation == "square"
    assert candidates[0].tags == ("crash", "doe", "jane", "market")


def test_pexels_provider_reads_api_key_from_environment(monkeypatch):
    monkeypatch.setenv("PEXELS_API_KEY", "env-test-key")
    provider = PexelsBrollProvider(api_key=None)

    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen",
        return_value=json_response({"videos": []}),
    ) as mocked_urlopen:
        provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    request = mocked_urlopen.call_args.args[0]
    assert provider.api_key == "env-test-key"
    assert request.headers["Authorization"] == "env-test-key"


def test_pexels_provider_returns_empty_when_response_has_no_videos_key():
    provider = PexelsBrollProvider(api_key="test-key")
    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen",
        return_value=json_response({"page": 1}),
    ):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert candidates == []


def test_pexels_provider_prefers_linked_video_file_and_uses_its_dimensions():
    provider = PexelsBrollProvider(api_key="test-key")
    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen",
        return_value=json_response(
            {
                "videos": [
                    {
                        "id": 321,
                        "duration": 4,
                        "width": 1920,
                        "height": 1080,
                        "video_files": [
                            {
                                "width": 111,
                                "height": 222,
                            },
                            {
                                "link": "https://cdn.example/preferred.mp4",
                                "width": 333,
                                "height": 777,
                            },
                        ],
                    }
                ]
            }
        ),
    ):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert len(candidates) == 1
    assert candidates[0].asset_url == "https://cdn.example/preferred.mp4"
    assert candidates[0].width == 333
    assert candidates[0].height == 777
    assert candidates[0].orientation == "vertical"


def test_pexels_provider_falls_back_to_video_dimensions_and_preserves_candidate_fields():
    provider = PexelsBrollProvider(api_key="test-key")

    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen",
        return_value=json_response(
            {
                "videos": [
                    {
                        "id": 789,
                        "duration": 4.5,
                        "width": 1080,
                        "height": 1920,
                        "video_files": [{"link": "https://cdn.example/fallback.mp4"}],
                    }
                ]
            }
        ),
    ):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert len(candidates) == 1
    assert candidates[0].candidate_id == "pexels-789"
    assert candidates[0].asset_type == "video"
    assert candidates[0].asset_url == "https://cdn.example/fallback.mp4"
    assert candidates[0].duration_ms == 4500
    assert candidates[0].width == 1080
    assert candidates[0].height == 1920
    assert candidates[0].orientation == "vertical"
    assert candidates[0].title == "market crash"


def test_pixabay_provider_marks_candidates_with_discovery_source():
    provider = PixabayBrollProvider(api_key="test-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        @staticmethod
        def read():
            return json.dumps(
                {
                    "hits": [
                        {
                            "id": 456,
                            "duration": 4,
                            "tags": "market, finance",
                            "videos": {
                                "medium": {
                                    "url": "https://cdn.example/pixabay.mp4",
                                    "width": 720,
                                    "height": 1280,
                                }
                            },
                        }
                    ]
                }
            ).encode("utf-8")

    with patch("src.infrastructure.broll.providers.pixabay_provider.urlopen", return_value=FakeResponse()):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert len(candidates) == 1
    assert candidates[0].provider == "pixabay"
    assert candidates[0].discovery_source == "pixabay"


def test_pixabay_provider_uses_referer_when_preparing_assets():
    provider = PixabayBrollProvider(api_key="test-key")
    candidate = BrollCandidate(
        candidate_id="pixabay-1",
        provider="pixabay",
        discovery_source="pixabay",
        asset_type="video",
        asset_url="https://cdn.example/pixabay.mp4",
        local_path=None,
        duration_ms=4000,
        width=720,
        height=1280,
        orientation="vertical",
        title="market crash",
    )

    with patch.object(provider.asset_cache, "ensure_downloaded", return_value="/tmp/pixabay.mp4") as ensure_downloaded:
        prepared = provider.prepare_asset(candidate, cache_dir="cache")

    assert prepared.local_path == "/tmp/pixabay.mp4"
    assert ensure_downloaded.call_args.kwargs["headers"] == {"Referer": "https://pixabay.com/"}


def test_pixabay_provider_returns_empty_without_api_key_and_keeps_local_assets(monkeypatch):
    monkeypatch.delenv("PIXABAY_API_KEY", raising=False)
    provider = PixabayBrollProvider(api_key=None)

    with patch(
        "src.infrastructure.broll.providers.pixabay_provider.urlopen",
        side_effect=AssertionError("urlopen should not be called without a Pixabay API key"),
    ) as urlopen_mock:
        assert provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache") == []

    urlopen_mock.assert_not_called()

    local_candidate = BrollCandidate(
        candidate_id="pixabay-local",
        provider="pixabay",
        discovery_source="pixabay",
        asset_type="video",
        asset_url="https://cdn.example/pixabay.mp4",
        local_path="/tmp/already-downloaded.mp4",
        duration_ms=4000,
        width=720,
        height=1280,
        orientation="vertical",
        title="market crash",
    )

    assert provider.prepare_asset(local_candidate, cache_dir="cache") == local_candidate


def test_pixabay_provider_falls_back_to_large_and_first_available_video_payload():
    provider = PixabayBrollProvider(api_key="test-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        @staticmethod
        def read():
            return json.dumps(
                {
                    "hits": [
                        {
                            "id": 456,
                            "duration": 4,
                            "tags": "market, finance",
                            "videos": {
                                "large": {
                                    "url": "https://cdn.example/pixabay-large.mp4",
                                    "width": 1280,
                                    "height": 720,
                                }
                            },
                        },
                        {
                            "id": 789,
                            "duration": 2,
                            "tags": "city, lights",
                            "videos": {
                                "tiny": {
                                    "url": "https://cdn.example/pixabay-tiny.mp4",
                                    "width": 500,
                                    "height": 500,
                                }
                            },
                        },
                    ]
                }
            ).encode("utf-8")

    with patch("src.infrastructure.broll.providers.pixabay_provider.urlopen", return_value=FakeResponse()):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert [candidate.asset_url for candidate in candidates] == [
        "https://cdn.example/pixabay-large.mp4",
        "https://cdn.example/pixabay-tiny.mp4",
    ]
    assert [candidate.orientation for candidate in candidates] == ["landscape", "square"]


def test_pixabay_provider_candidate_id_uses_lowercase_id_field():
    """Kills mutmut_86: hit.get('id') → hit.get('ID')."""
    provider = PixabayBrollProvider(api_key="test-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @staticmethod
        def read():
            return json.dumps(
                {
                    "hits": [
                        {
                            "id": 99,
                            "duration": 2,
                            "tags": "city",
                            "videos": {"medium": {"url": "https://cdn.x/v.mp4", "width": 720, "height": 1280}},
                        }
                    ]
                }
            ).encode()

    with patch("src.infrastructure.broll.providers.pixabay_provider.urlopen", return_value=FakeResponse()):
        candidates = provider.search(build_provider_test_beat(), ("city",), cache_dir="cache")

    assert candidates[0].candidate_id == "pixabay-99"


def test_pixabay_provider_asset_type_is_lowercase_video():
    """Kills mutmut_89 (XXvideoXX) and mutmut_90 (VIDEO)."""
    provider = PixabayBrollProvider(api_key="test-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        @staticmethod
        def read():
            return json.dumps(
                {
                    "hits": [
                        {
                            "id": 1,
                            "duration": 3,
                            "tags": "sky",
                            "videos": {"medium": {"url": "https://cdn.x/s.mp4", "width": 1280, "height": 720}},
                        }
                    ]
                }
            ).encode()

    with patch("src.infrastructure.broll.providers.pixabay_provider.urlopen", return_value=FakeResponse()):
        candidates = provider.search(build_provider_test_beat(), ("sky",), cache_dir="cache")

    assert candidates[0].asset_type == "video"


def test_pixabay_provider_prepare_asset_passes_exact_source_url_cache_dir_and_filename():
    """Kills mutmut_2 (source_url=None), mutmut_3 (cache_dir=None), mutmut_4 (filename=None)."""
    provider = PixabayBrollProvider(api_key="test-key")
    candidate = BrollCandidate(
        candidate_id="pixabay-42",
        provider="pixabay",
        discovery_source="pixabay",
        asset_type="video",
        asset_url="https://cdn.example/exact-url.mp4",
        local_path=None,
        duration_ms=3000,
        width=720,
        height=1280,
        orientation="vertical",
        title="city sky",
    )

    with patch.object(provider.asset_cache, "ensure_downloaded", return_value="/tmp/pixabay-42") as mock_dl:
        provider.prepare_asset(candidate, cache_dir="/custom/cache")

    call_kwargs = mock_dl.call_args.kwargs
    assert call_kwargs["source_url"] == "https://cdn.example/exact-url.mp4"
    assert call_kwargs["cache_dir"] == "/custom/cache/pixabay"
    assert call_kwargs["filename"] == "pixabay-42"

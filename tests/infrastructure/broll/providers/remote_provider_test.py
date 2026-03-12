import json
from unittest.mock import patch

from src.domain.broll_models import BrollCandidate
from src.infrastructure.broll.providers.pexels_provider import PexelsBrollProvider
from src.infrastructure.broll.providers.pixabay_provider import PixabayBrollProvider
from tests.infrastructure.broll.providers.support_test import build_provider_test_beat


def test_pexels_provider_marks_candidates_with_discovery_source():
    provider = PexelsBrollProvider(api_key="test-key")

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
            ).encode("utf-8")

    with patch("src.infrastructure.broll.providers.pexels_provider.urlopen", return_value=FakeResponse()):
        candidates = provider.search(build_provider_test_beat(), ("market crash",), cache_dir="cache")

    assert len(candidates) == 1
    assert candidates[0].provider == "pexels"
    assert candidates[0].discovery_source == "pexels"
    assert candidates[0].title == "market crash"
    assert "market" in candidates[0].tags
    assert "crash" in candidates[0].tags


def test_pexels_provider_uses_expected_headers_for_search_and_prepare():
    provider = PexelsBrollProvider(api_key="test-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        @staticmethod
        def read():
            return json.dumps({"videos": []}).encode("utf-8")

    with patch(
        "src.infrastructure.broll.providers.pexels_provider.urlopen", return_value=FakeResponse()
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
    assert ensure_downloaded.call_args.kwargs["headers"] == {
        "Authorization": "test-key",
        "Accept": "application/json",
        "User-Agent": provider.USER_AGENT,
    }


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

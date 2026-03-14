from unittest.mock import patch

from src.infrastructure.broll.asset_cache import BrollAssetCache


def test_asset_cache_reuses_existing_download(tmp_path):
    cache = BrollAssetCache()
    cached_file = tmp_path / "cache" / "asset.mp4"
    cached_file.parent.mkdir(parents=True)
    cached_file.write_bytes(b"cached")

    with patch("src.infrastructure.broll.asset_cache.urlopen") as mock_urlopen:
        result = cache.ensure_downloaded(
            source_url="https://example.com/asset.mp4",
            cache_dir=str(cached_file.parent),
            filename="asset",
        )

    assert result == str(cached_file)
    mock_urlopen.assert_not_called()


def test_asset_cache_downloads_asset_with_headers_and_preserves_suffix(tmp_path):
    cache = BrollAssetCache()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        @staticmethod
        def read():
            return b"payload"

    with patch("src.infrastructure.broll.asset_cache.urlopen", return_value=FakeResponse()) as mock_urlopen:
        result = cache.ensure_downloaded(
            source_url="https://example.com/assets/clip.webm",
            cache_dir=str(tmp_path / "cache"),
            filename="downloaded",
            headers={"Authorization": "token"},
        )

    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://example.com/assets/clip.webm"
    assert request.get_header("Authorization") == "token"
    assert request.get_header("User-agent") is not None
    assert result.endswith("downloaded.webm")
    assert (tmp_path / "cache" / "downloaded.webm").read_bytes() == b"payload"

import json

from src.infrastructure.broll.providers.local_still_provider import LocalMediaProvider
from tests.infrastructure.broll.providers.support_test import build_provider_test_beat


def create_asset(asset_path, payload: bytes) -> None:
    asset_path.parent.mkdir(parents=True, exist_ok=True)
    asset_path.write_bytes(payload)


def write_metadata(media_root, payload: dict) -> None:
    (media_root / "broll-metadata.json").write_text(json.dumps(payload), encoding="utf-8")


def search_candidates(
    tmp_path,
    *,
    search_dirs,
    beat_text: str,
    queries: tuple[str, ...],
):
    provider = LocalMediaProvider(search_dirs=tuple(str(path) for path in search_dirs))
    candidates = provider.search(
        beat=build_provider_test_beat(beat_text),
        queries=queries,
        cache_dir=str(tmp_path / "cache"),
    )
    return provider, candidates

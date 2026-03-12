import json
import os
from dataclasses import replace
from urllib.parse import quote
from urllib.request import urlopen

from src.domain.broll_models import BrollCandidate, ImpactBeat
from src.domain.ports import IBrollAssetProvider
from src.infrastructure.broll.asset_cache import BrollAssetCache


class PixabayBrollProvider(IBrollAssetProvider):
    provider_name = "pixabay"

    def __init__(self, api_key: str | None = None, asset_cache: BrollAssetCache | None = None):
        self.api_key = api_key or os.getenv("PIXABAY_API_KEY")
        self.asset_cache = asset_cache or BrollAssetCache()

    def search(
        self,
        beat: ImpactBeat,
        queries: tuple[str, ...],
        cache_dir: str,
    ) -> list[BrollCandidate]:
        del beat, cache_dir
        if not self.api_key:
            return []

        candidates: list[BrollCandidate] = []
        for query in queries:
            with urlopen(  # nosec - official provider endpoint
                f"https://pixabay.com/api/videos/?key={quote(self.api_key)}&q={quote(query)}&per_page=3&safesearch=true"
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))

            for hit in payload.get("hits", []):
                videos = hit.get("videos", {})
                file_payload = videos.get("medium") or videos.get("large") or next(iter(videos.values()), {})
                width = int(file_payload.get("width", 0) or 0)
                height = int(file_payload.get("height", 0) or 0)
                candidates.append(
                    BrollCandidate(
                        candidate_id=f"pixabay-{hit.get('id')}",
                        provider=self.provider_name,
                        discovery_source="pixabay",
                        asset_type="video",
                        asset_url=str(file_payload.get("url", "")),
                        local_path=None,
                        duration_ms=int(float(hit.get("duration", 0)) * 1000),
                        width=width,
                        height=height,
                        orientation=self._orientation(width, height),
                        title=query,
                        tags=tuple(tag.strip() for tag in str(hit.get("tags", "")).split(",") if tag.strip()),
                    )
                )
        return candidates

    def prepare_asset(self, candidate: BrollCandidate, cache_dir: str) -> BrollCandidate:
        if candidate.local_path:
            return candidate

        local_path = self.asset_cache.ensure_downloaded(
            source_url=candidate.asset_url,
            cache_dir=os.path.join(cache_dir, self.provider_name),
            filename=candidate.candidate_id,
            headers={"Referer": "https://pixabay.com/"},
        )
        return replace(candidate, local_path=local_path)

    @staticmethod
    def _orientation(width: int, height: int) -> str:
        if width <= 0 or height <= 0:
            return "unknown"
        if height > width:
            return "vertical"
        if height == width:
            return "square"
        return "landscape"

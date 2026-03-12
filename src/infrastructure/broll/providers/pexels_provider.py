import json
import os
from dataclasses import replace
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.domain.broll_models import BrollCandidate, ImpactBeat
from src.domain.ports import IBrollAssetProvider
from src.infrastructure.broll.asset_cache import BrollAssetCache
from src.infrastructure.subtitles.normalization import normalize_token


class PexelsBrollProvider(IBrollAssetProvider):
    provider_name = "pexels"
    USER_AGENT = "podcast-short-video-generator/1.0"

    def __init__(self, api_key: str | None = None, asset_cache: BrollAssetCache | None = None):
        self.api_key = api_key or os.getenv("PEXELS_API_KEY")
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
            request = Request(
                url=(f"https://api.pexels.com/videos/search?query={quote(query)}&per_page=3&orientation=portrait"),
                headers=self._request_headers(),
            )
            with urlopen(request) as response:  # nosec - official provider endpoint
                payload = json.loads(response.read().decode("utf-8"))

            for video in payload.get("videos", []):
                video_files = video.get("video_files", [])
                if not video_files:
                    continue
                file_payload = next(
                    (item for item in video_files if item.get("link")),
                    video_files[0],
                )
                width = int(file_payload.get("width", video.get("width", 0)) or 0)
                height = int(file_payload.get("height", video.get("height", 0)) or 0)
                candidates.append(
                    BrollCandidate(
                        candidate_id=f"pexels-{video.get('id')}",
                        provider=self.provider_name,
                        discovery_source="pexels",
                        asset_type="video",
                        asset_url=str(file_payload.get("link", "")),
                        local_path=None,
                        duration_ms=int(float(video.get("duration", 0)) * 1000),
                        width=width,
                        height=height,
                        orientation=self._orientation(width, height),
                        title=query,
                        tags=self._candidate_tags(query, video),
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
            headers=self._request_headers() if self.api_key else None,
        )
        return replace(candidate, local_path=local_path)

    def _request_headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": self.USER_AGENT}
        if self.api_key:
            headers["Authorization"] = self.api_key
        return headers

    @staticmethod
    def _orientation(width: int, height: int) -> str:
        if width <= 0 or height <= 0:
            return "unknown"
        if height > width:
            return "vertical"
        if height == width:
            return "square"
        return "landscape"

    @staticmethod
    def _candidate_tags(query: str, video: dict[str, object]) -> tuple[str, ...]:
        query_tokens = {
            normalized
            for token in query.replace("-", " ").replace("_", " ").split()
            if (normalized := normalize_token(token))
        }
        user_name = str(video.get("user", {}).get("name", "")).strip()
        user_tokens = {
            normalized for token in user_name.replace("-", " ").split() if (normalized := normalize_token(token))
        }
        return tuple(sorted(query_tokens | user_tokens))

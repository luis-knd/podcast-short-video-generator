from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class BrollAssetCache:
    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        )
    }

    def ensure_downloaded(
        self,
        source_url: str,
        cache_dir: str,
        filename: str,
        headers: dict[str, str] | None = None,
    ) -> str | None:
        target_dir = Path(cache_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(urlparse(source_url).path).suffix or ".mp4"
        target_path = target_dir / f"{filename}{suffix}"
        if target_path.exists():
            return str(target_path)

        request_headers = {**self.DEFAULT_HEADERS, **(headers or {})}
        request = Request(source_url, headers=request_headers)
        with urlopen(request) as response:  # nosec - source URLs come from trusted stock providers configured by user
            target_path.write_bytes(response.read())

        return str(target_path)

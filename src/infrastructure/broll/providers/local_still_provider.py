import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.domain.broll_models import BrollCandidate, ImpactBeat
from src.domain.ports import IBrollAssetProvider
from src.domain.text_utils import normalize_token


@dataclass(frozen=True)
class LocalMediaMetadataEntry:
    relative_path: str
    title: str
    tags: tuple[str, ...]
    description: str
    asset_type: str | None
    orientation: str | None
    active: bool


class LocalMediaProvider(IBrollAssetProvider):
    provider_name = "local_media"
    METADATA_FILENAME = "broll-metadata.json"
    IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}
    VIDEO_EXTENSIONS = {".m4v", ".mov", ".mp4", ".webm"}
    SEARCH_STOPWORDS = {
        "a",
        "all",
        "and",
        "con",
        "de",
        "del",
        "el",
        "en",
        "for",
        "i",
        "i'd",
        "i'm",
        "is",
        "it",
        "it's",
        "its",
        "la",
        "las",
        "los",
        "my",
        "of",
        "or",
        "para",
        "por",
        "que",
        "so",
        "the",
        "those",
        "this",
        "to",
        "un",
        "una",
        "with",
        "y",
        "your",
    }
    GENERIC_SEARCH_TOKENS = {"clip", "face", "image", "moment", "person", "scene", "text", "video"}

    def __init__(self, search_dirs: tuple[str, ...] = ()):
        self.search_dirs = search_dirs
        self._probe_cache: dict[str, tuple[int, int, int, str]] = {}

    def search(
        self,
        beat: ImpactBeat,
        queries: tuple[str, ...],
        cache_dir: str,
    ) -> list[BrollCandidate]:
        del cache_dir
        if not self.search_dirs:
            return []

        beat_tokens = self._search_tokens(beat.text.split())
        query_tokens = {token for query in queries for token in self._search_tokens(query.split())}
        expected_tokens = beat_tokens | query_tokens

        scored_candidates: list[tuple[tuple[int, int, int, str], BrollCandidate]] = []
        for search_dir in self.search_dirs:
            root = Path(search_dir)
            metadata_entries = self._load_metadata_entries(root)
            if metadata_entries is not None:
                scored_candidates.extend(self._search_manifest_entries(root, metadata_entries, expected_tokens))
                continue

            scored_candidates.extend(self._search_by_path_tokens(root, expected_tokens))

        ranked_candidates = [
            candidate for _, candidate in sorted(scored_candidates, key=lambda item: item[0], reverse=True)
        ]
        return ranked_candidates[:5]

    def prepare_asset(self, candidate: BrollCandidate, cache_dir: str) -> BrollCandidate:
        del cache_dir
        return candidate

    def _search_manifest_entries(
        self,
        root: Path,
        metadata_entries: tuple[LocalMediaMetadataEntry, ...],
        expected_tokens: set[str],
    ) -> list[tuple[tuple[int, int, int, str], BrollCandidate]]:
        scored_candidates: list[tuple[tuple[int, int, int, str], BrollCandidate]] = []
        for entry in metadata_entries:
            if not entry.active:
                continue

            asset_path = root / entry.relative_path
            if not asset_path.is_file():
                continue

            asset_type = entry.asset_type or self._asset_type_from_path(asset_path)
            if asset_type not in {"image", "video"}:
                continue

            candidate_tokens = {
                normalize_token(token) for token in self._metadata_tokens(entry) if normalize_token(token)
            }
            if expected_tokens and not candidate_tokens.intersection(expected_tokens):
                continue

            orientation = entry.orientation or self._orientation_from_name(asset_path)
            candidate = self._build_candidate(
                root=root,
                asset_path=asset_path,
                asset_type=asset_type,
                orientation=orientation,
                discovery_source="local_manifest",
                title=entry.title or asset_path.stem,
                tags=entry.tags or tuple(sorted(candidate_tokens)),
            )
            scored_candidates.append(
                (
                    self._candidate_priority(
                        expected_tokens=expected_tokens,
                        candidate_tokens=candidate_tokens,
                        asset_type=asset_type,
                        orientation=orientation,
                        title=candidate.title,
                    ),
                    candidate,
                )
            )
        return scored_candidates

    def _search_by_path_tokens(
        self,
        root: Path,
        expected_tokens: set[str],
    ) -> list[tuple[tuple[int, int, int, str], BrollCandidate]]:
        scored_candidates: list[tuple[tuple[int, int, int, str], BrollCandidate]] = []
        for path in root.rglob("*"):
            if path.suffix.lower() not in self.IMAGE_EXTENSIONS | self.VIDEO_EXTENSIONS or not path.is_file():
                continue

            stem_tokens = {normalize_token(token) for token in self._path_tokens(path, root) if normalize_token(token)}
            if expected_tokens and not stem_tokens.intersection(expected_tokens):
                continue

            asset_type = self._asset_type_from_path(path)
            orientation = self._orientation_from_name(path)
            candidate = self._build_candidate(
                root=root,
                asset_path=path,
                asset_type=asset_type,
                orientation=orientation,
                discovery_source="local_heuristic_fallback",
                title=path.stem,
                tags=tuple(sorted(stem_tokens)),
            )
            scored_candidates.append(
                (
                    self._candidate_priority(
                        expected_tokens=expected_tokens,
                        candidate_tokens=stem_tokens,
                        asset_type=asset_type,
                        orientation=orientation,
                        title=path.stem,
                    ),
                    candidate,
                )
            )
        return scored_candidates

    def _build_candidate(
        self,
        root: Path,
        asset_path: Path,
        asset_type: str,
        orientation: str,
        discovery_source: str,
        title: str,
        tags: tuple[str, ...],
    ) -> BrollCandidate:
        relative_id = str(asset_path.relative_to(root)).replace("/", "-").replace("\\", "-")
        duration_ms, width, height, probed_orientation = self._probe_asset(
            asset_path=asset_path,
            asset_type=asset_type,
            fallback_orientation=orientation,
        )
        return BrollCandidate(
            candidate_id=f"local-{relative_id}",
            provider=self.provider_name,
            discovery_source=discovery_source,
            asset_type=asset_type,
            asset_url=str(asset_path),
            local_path=str(asset_path),
            duration_ms=duration_ms,
            width=width,
            height=height,
            orientation=probed_orientation,
            title=title,
            tags=tags,
        )

    def _probe_asset(
        self,
        asset_path: Path,
        asset_type: str,
        fallback_orientation: str,
    ) -> tuple[int, int, int, str]:
        if asset_type == "image":
            orientation = fallback_orientation if fallback_orientation != "unknown" else "square"
            return 0, 1080, 1080, orientation

        cache_key = str(asset_path.resolve())
        cached = self._probe_cache.get(cache_key)
        if cached is not None:
            return cached

        probe_result = self._run_ffprobe(asset_path, fallback_orientation)
        self._probe_cache[cache_key] = probe_result
        return probe_result

    def _run_ffprobe(self, asset_path: Path, fallback_orientation: str) -> tuple[int, int, int, str]:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height:format=duration",
                    "-of",
                    "json",
                    str(asset_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout or "{}")
        except (OSError, RuntimeError, TypeError, ValueError, subprocess.CalledProcessError):
            return 0, 0, 0, fallback_orientation

        streams = payload.get("streams", [])
        stream = streams[0] if streams else {}
        width = self._safe_int(stream.get("width"))
        height = self._safe_int(stream.get("height"))
        duration_seconds = payload.get("format", {}).get("duration") or stream.get("duration")
        duration_ms = int(round(float(duration_seconds) * 1000)) if duration_seconds else 0
        orientation = self._orientation_from_dimensions(width, height, fallback_orientation)
        return duration_ms, width, height, orientation

    def _search_tokens(self, raw_tokens: list[str]) -> set[str]:
        return {
            normalized
            for token in raw_tokens
            for normalized in (normalize_token(token),)
            if normalized and normalized not in self.SEARCH_STOPWORDS and normalized not in self.GENERIC_SEARCH_TOKENS
        }

    @staticmethod
    def _path_tokens(path: Path, search_root: Path) -> list[str]:
        relative_parts = path.relative_to(search_root).parts
        raw_tokens: list[str] = []
        for part in relative_parts:
            raw_tokens.extend(part.replace("-", " ").replace("_", " ").replace(".", " ").split())
        return raw_tokens

    @staticmethod
    def _metadata_tokens(entry: LocalMediaMetadataEntry) -> list[str]:
        raw_tokens = [entry.title, entry.description, *entry.tags]
        tokens: list[str] = []
        for part in raw_tokens:
            tokens.extend(part.replace("-", " ").replace("_", " ").split())
        return tokens

    @staticmethod
    def _safe_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _orientation_from_dimensions(width: int, height: int, fallback: str) -> str:
        if width <= 0 or height <= 0:
            return fallback
        if height > width:
            return "vertical"
        if width > height:
            return "landscape"
        return "square"

    def _load_metadata_entries(self, root: Path) -> tuple[LocalMediaMetadataEntry, ...] | None:
        manifest_path = root / self.METADATA_FILENAME
        if not manifest_path.exists():
            return None

        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return ()

        assets = payload.get("assets", [])
        if not isinstance(assets, list):
            return ()

        entries: list[LocalMediaMetadataEntry] = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            relative_path = str(asset.get("path", "")).strip()
            if not relative_path:
                continue

            tags = asset.get("tags", ())
            if not isinstance(tags, list | tuple):
                tags = ()

            entries.append(
                LocalMediaMetadataEntry(
                    relative_path=relative_path,
                    title=str(asset.get("title", "")).strip(),
                    tags=tuple(str(tag).strip() for tag in tags if str(tag).strip()),
                    description=str(asset.get("description", "")).strip(),
                    asset_type=str(asset.get("asset_type", "")).strip() or None,
                    orientation=str(asset.get("orientation", "")).strip() or None,
                    active=bool(asset.get("active", True)),
                )
            )
        return tuple(entries)

    def _orientation_from_name(self, path: Path) -> str:
        normalized_name = normalize_token(path.stem)
        if any(token in normalized_name for token in ("vertical", "portrait", "reel", "short", "9x16")):
            return "vertical"
        if any(token in normalized_name for token in ("square", "1x1")):
            return "square"
        return "square" if path.suffix.lower() in self.IMAGE_EXTENSIONS else "unknown"

    def _asset_type_from_path(self, path: Path) -> str:
        return "image" if path.suffix.lower() in self.IMAGE_EXTENSIONS else "video"

    @staticmethod
    def _candidate_priority(
        expected_tokens: set[str],
        candidate_tokens: set[str],
        asset_type: str,
        orientation: str,
        title: str,
    ) -> tuple[int, int, int, str]:
        overlap = len(expected_tokens & candidate_tokens)
        orientation_priority = {"vertical": 2, "square": 1}.get(orientation, 0)
        asset_priority = 1 if asset_type == "video" else 0
        return overlap, orientation_priority, asset_priority, title.lower()


LocalStillProvider = LocalMediaProvider

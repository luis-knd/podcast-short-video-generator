import hashlib
import json
from pathlib import Path


class AlignmentCache:
    RAW_CACHE_DIR = "raw_asr"
    RECONCILED_CACHE_DIR = "reconciled"

    def __init__(self, cache_root: Path):
        self.cache_root = cache_root
        self.raw_cache_root = self.cache_root / self.RAW_CACHE_DIR
        self.reconciled_cache_root = self.cache_root / self.RECONCILED_CACHE_DIR
        self.raw_cache_root.mkdir(parents=True, exist_ok=True)
        self.reconciled_cache_root.mkdir(exist_ok=True)

    @classmethod
    def from_output_filepath(cls, output_ass_filepath: str) -> "AlignmentCache":
        output_path = Path(output_ass_filepath)
        return cls(output_path.parent / ".cache" / "subtitle_alignment")

    @staticmethod
    def _hash_payload(payload: dict[str, object]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _hash_file(filepath: str) -> str:
        file_path = Path(filepath)
        with open(file_path, "rb") as file_handle:
            return hashlib.sha256(file_handle.read()).hexdigest()

    @staticmethod
    def _file_fingerprint(filepath: str) -> dict[str, object]:
        file_path = Path(filepath)
        stats = file_path.stat()
        return {
            "path": str(file_path.resolve()),
            "size_bytes": stats.st_size,
            "mtime_ns": stats.st_mtime_ns,
        }

    def build_raw_key(
        self,
        media_filepath: str,
        aligner_name: str,
        model_name: str,
        compute_type: str,
        language: str | None,
    ) -> str:
        payload = {
            "media": self._file_fingerprint(media_filepath),
            "aligner": aligner_name,
            "model": model_name,
            "compute_type": compute_type,
            "language": language,
        }
        return self._hash_payload(payload)

    def build_reconciled_key(
        self,
        subtitle_filepath: str,
        raw_key: str,
        reconciliation_version: str,
    ) -> str:
        payload = {
            "subtitle": {
                **self._file_fingerprint(subtitle_filepath),
                "sha256": self._hash_file(subtitle_filepath),
            },
            "raw_key": raw_key,
            "reconciliation_version": reconciliation_version,
        }
        return self._hash_payload(payload)

    def load_raw(self, raw_key: str) -> dict[str, object] | None:
        return self._load(self.raw_cache_root / f"{raw_key}.json")

    def save_raw(self, raw_key: str, payload: dict[str, object]):
        self._save(self.raw_cache_root / f"{raw_key}.json", payload)

    def load_reconciled(self, reconciled_key: str) -> dict[str, object] | None:
        return self._load(self.reconciled_cache_root / f"{reconciled_key}.json")

    def save_reconciled(self, reconciled_key: str, payload: dict[str, object]):
        self._save(self.reconciled_cache_root / f"{reconciled_key}.json", payload)

    @staticmethod
    def _load(cache_path: Path) -> dict[str, object] | None:
        if not cache_path.exists():
            return None

        with open(cache_path, encoding="utf-8") as cache_file:
            return json.load(cache_file)

    @staticmethod
    def _save(cache_path: Path, payload: dict[str, object]):
        with open(cache_path, "w", encoding="utf-8") as cache_file:
            json.dump(payload, cache_file, ensure_ascii=True, indent=2)

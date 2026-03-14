import json
from pathlib import Path

from src.domain.manual_broll_overrides import ManualBrollOverride


class ManualBrollOverrideLoader:
    def __init__(self, filepath: str | Path | None = None):
        self.filepath = Path(filepath) if filepath else self._default_filepath()

    def load(self) -> tuple[ManualBrollOverride, ...]:
        if not self.filepath.exists():
            return ()

        try:
            payload = json.loads(self.filepath.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError):
            return ()

        overrides = payload.get("overrides", [])
        if not isinstance(overrides, list):
            return ()

        loaded_overrides: list[ManualBrollOverride] = []
        for raw_override in overrides:
            if not isinstance(raw_override, dict):
                continue

            short_id = str(raw_override.get("short_id", "")).strip()
            anchor_text = str(raw_override.get("anchor_text", "")).strip()
            asset_path = str(raw_override.get("asset_path", "")).strip()
            mode = str(raw_override.get("mode", "")).strip() or "full_frame_cutaway"
            if not short_id or not anchor_text or not asset_path:
                continue

            resolved_asset_path = self._resolve_asset_path(asset_path)
            loaded_overrides.append(
                ManualBrollOverride(
                    short_id=short_id,
                    anchor_text=anchor_text,
                    asset_path=str(resolved_asset_path),
                    mode=mode,
                    start_ms=self._optional_int(raw_override.get("start_ms")),
                    end_ms=self._optional_int(raw_override.get("end_ms")),
                    mute_asset_audio=bool(raw_override.get("mute_asset_audio", True)),
                    priority=int(raw_override.get("priority", 100)),
                    active=bool(raw_override.get("active", True)),
                )
            )

        return tuple(loaded_overrides)

    @staticmethod
    def _default_filepath() -> Path:
        return Path(__file__).resolve().parents[3] / "inputs" / "broll-overrides.json"

    def _resolve_asset_path(self, asset_path: str) -> Path:
        candidate_path = Path(asset_path)
        if candidate_path.is_absolute():
            return candidate_path
        overrides_relative_path = (self.filepath.parent / candidate_path).resolve()
        if overrides_relative_path.exists():
            return overrides_relative_path
        return (self._default_filepath().parents[1] / candidate_path).resolve()

    @staticmethod
    def _optional_int(value) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

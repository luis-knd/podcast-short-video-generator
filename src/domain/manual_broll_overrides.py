from dataclasses import dataclass


@dataclass(frozen=True)
class ManualBrollOverride:
    short_id: str
    anchor_text: str
    asset_path: str
    mode: str
    start_ms: int | None = None
    end_ms: int | None = None
    mute_asset_audio: bool = True
    priority: int = 100
    active: bool = True

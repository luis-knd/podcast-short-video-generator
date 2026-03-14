import json
from datetime import UTC, datetime
from pathlib import Path

from src.domain.broll_models import ImpactBeat, ShortEditingPlan
from src.domain.subtitle_models import SubtitleTimeline


class BrollPlanJsonWriter:
    def write_impact_beats(
        self,
        short_id: str,
        timeline: SubtitleTimeline,
        beats: list[ImpactBeat],
        output_dir: Path,
    ):
        payload = {
            "short_id": short_id,
            "interval": {
                "start_ms": timeline.interval_start_ms,
                "end_ms": timeline.interval_end_ms,
            },
            "timeline_quality": timeline.quality_score,
            "beats": [beat.to_dict() for beat in beats],
        }
        self._write(output_dir / f"{short_id}.impact_beats.json", payload)

    def write_broll_candidates(
        self,
        short_id: str,
        beats: list[dict[str, object]],
        output_dir: Path,
    ):
        payload = {
            "short_id": short_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "beats": beats,
        }
        self._write(output_dir / f"{short_id}.broll_candidates.json", payload)

    def write_broll_plan(
        self,
        short_id: str,
        plan: ShortEditingPlan,
        output_dir: Path,
    ):
        payload = plan.to_dict()
        payload["short_id"] = short_id
        self._write(output_dir / f"{short_id}.broll_plan.json", payload)

    @staticmethod
    def _write(filepath: Path, payload: dict[str, object]):
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

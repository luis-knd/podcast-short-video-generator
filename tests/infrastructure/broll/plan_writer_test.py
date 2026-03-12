import json

from src.domain.broll_models import BeatScoreBreakdown, BrollInsertion, ImpactBeat, ShortEditingPlan
from src.domain.subtitle_models import SubtitleTimeline
from src.infrastructure.broll.plan_writer import BrollPlanJsonWriter


def test_broll_plan_writer_persists_candidate_discovery_source(tmp_path):
    writer = BrollPlanJsonWriter()

    writer.write_broll_candidates(
        short_id="short_0",
        beats=[
            {
                "beat_id": "beat-1",
                "queries": ["market crash"],
                "candidates": [
                    {
                        "candidate_id": "cand-1",
                        "provider": "local_media",
                        "discovery_source": "local_manifest",
                    }
                ],
                "provider_attempts": [
                    {
                        "provider": "pexels",
                        "configured": True,
                        "attempted": True,
                        "queries": [
                            {
                                "provider": "pexels",
                                "query": "market crash",
                                "configured": True,
                                "attempted": True,
                                "result_count": 2,
                                "error": None,
                            }
                        ],
                        "total_results": 2,
                    }
                ],
            }
        ],
        output_dir=tmp_path,
    )

    payload = json.loads((tmp_path / "short_0.broll_candidates.json").read_text(encoding="utf-8"))

    assert payload["beats"][0]["candidates"][0]["provider"] == "local_media"
    assert payload["beats"][0]["candidates"][0]["discovery_source"] == "local_manifest"
    assert payload["beats"][0]["provider_attempts"][0]["provider"] == "pexels"
    assert payload["beats"][0]["provider_attempts"][0]["queries"][0]["result_count"] == 2


def test_broll_plan_writer_persists_impact_beats_and_plan_payloads(tmp_path):
    writer = BrollPlanJsonWriter()
    timeline = SubtitleTimeline(0, 10000, (), (), 0.87)
    beat = ImpactBeat(
        beat_id="beat-1",
        text="market crash",
        start_ms=1000,
        end_ms=2200,
        duration_ms=1200,
        timing_mode="aligned",
        word_confidence_avg=0.91,
        cue_quality_score=0.88,
        scores=BeatScoreBreakdown(
            total=0.9,
            visualizability=0.8,
            emotional_load=0.7,
            contrast=0.6,
            narrative_turn=0.5,
            verbal_force=0.6,
            duration_fit=0.8,
            timing_confidence=0.95,
        ),
        reasons=("strong beat",),
    )
    plan = ShortEditingPlan(
        short_id="short_0",
        enabled=True,
        strategy_version="broll-plan-v1",
        insertions=(
            BrollInsertion(
                insertion_id="insert-1",
                beat_id="beat-1",
                mode="overlay",
                asset_provider="local_media",
                asset_path="/tmp/clip.mp4",
                start_ms=900,
                end_ms=2400,
                source_beat_score=0.9,
                candidate_score=0.8,
                x=0,
                y=120,
                width=800,
                height=500,
                opacity=0.96,
                asset_in_ms=0,
                asset_out_ms=1500,
            ),
        ),
    )

    writer.write_impact_beats("short_0", timeline, [beat], tmp_path)
    writer.write_broll_plan("short_0", plan, tmp_path)

    impact_payload = json.loads((tmp_path / "short_0.impact_beats.json").read_text(encoding="utf-8"))
    plan_payload = json.loads((tmp_path / "short_0.broll_plan.json").read_text(encoding="utf-8"))

    assert impact_payload["timeline_quality"] == 0.87
    assert impact_payload["beats"][0]["beat_id"] == "beat-1"
    assert plan_payload["strategy_version"] == "broll-plan-v1"
    assert plan_payload["insertions"][0]["asset_provider"] == "local_media"

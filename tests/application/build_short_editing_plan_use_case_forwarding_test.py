from pathlib import Path

from src.application.broll import BuildShortEditingPlanUseCase
from src.domain.broll_models import BeatCandidateSelection, ShortEditingPlan
from tests.application.build_short_editing_plan_use_case_support_test import (
    DualQueryGenerator,
    FakeManualOverrideLoader,
    FakeWriter,
    SingleQueryGenerator,
    UnconfiguredProvider,
    _build_candidate,
    _build_detected_beat,
    _build_timeline,
    build_manual_override,
)


class RecordingInsertionPlanner:
    def __init__(self, plan: ShortEditingPlan):
        self.returned_plan = plan
        self.short_id = None
        self.timeline = None
        self.beat_candidates = None
        self.target_width = None
        self.target_height = None

    def plan(self, short_id, timeline, beat_candidates, target_width, target_height):
        self.short_id = short_id
        self.timeline = timeline
        self.beat_candidates = tuple(beat_candidates)
        self.target_width = target_width
        self.target_height = target_height
        return self.returned_plan


class RecordingProvider:
    provider_name = "recording"

    def __init__(self, candidate):
        self.candidate = candidate
        self.received_beat = None
        self.received_queries = None
        self.received_cache_dir = None

    def search(self, beat, queries, cache_dir):
        self.received_beat = beat
        self.received_queries = queries
        self.received_cache_dir = cache_dir
        return [self.candidate]

    @staticmethod
    def prepare_asset(candidate, cache_dir):
        del cache_dir
        return candidate


class SingleBeatDetector:
    def __init__(self, beat):
        self.beat = beat

    def detect(self, timeline):
        del timeline
        return [self.beat]


def test_build_short_editing_plan_use_case_forwards_output_root_and_planner_arguments(tmp_path):
    writer = FakeWriter()
    returned_plan = ShortEditingPlan(
        short_id="short-forwarding",
        enabled=True,
        strategy_version="broll-plan-v1",
        insertions=(),
    )
    planner = RecordingInsertionPlanner(returned_plan)
    timeline = _build_timeline(0, 12000)
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=writer,
        beat_detector=type("NoBeatDetector", (), {"detect": staticmethod(lambda timeline: [])})(),
        insertion_planner=planner,
        enabled=True,
    )

    plan = use_case.build(
        short_id="short-forwarding",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan is returned_plan
    assert writer.candidate_payload[0] == "short-forwarding"
    assert writer.candidate_payload[2] == Path(tmp_path)
    assert writer.plan_payload == ("short-forwarding", returned_plan, Path(tmp_path))
    assert planner.short_id == "short-forwarding"
    assert planner.timeline is timeline
    assert planner.target_width == 1080
    assert planner.target_height == 1920
    assert planner.beat_candidates == ()


def test_build_short_editing_plan_use_case_passes_detected_beat_to_provider_search(tmp_path):
    writer = FakeWriter()
    beat = _build_detected_beat("beat-search", "launch product office", 2000, 3600, 0.91)
    provider = RecordingProvider(
        _build_candidate(
            candidate_id="recording-1",
            provider="recording",
            discovery_source="local_manifest",
            local_path=str(tmp_path / "recording-1.mp4"),
            title="launch product office",
            tags=("launch", "product", "office"),
        )
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=SingleBeatDetector(beat),
        query_generator=SingleQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short-search-beat",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert provider.received_beat is beat
    assert provider.received_queries == ("launch product office",)
    assert provider.received_cache_dir == str(Path(tmp_path) / ".cache" / "broll" / "assets")


def test_build_short_editing_plan_use_case_records_every_unconfigured_query_attempt(tmp_path):
    writer = FakeWriter()
    use_case = BuildShortEditingPlanUseCase(
        providers=(UnconfiguredProvider(),),
        plan_writer=writer,
        query_generator=DualQueryGenerator(),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short-unconfigured-queries",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.insertions == ()
    attempt = writer.candidate_payload[1][0]["provider_attempts"][0]
    assert [query_attempt["query"] for query_attempt in attempt["queries"]] == [
        "launch product office",
        "confusing negatives",
    ]
    assert all(query_attempt["configured"] is False for query_attempt in attempt["queries"])
    assert all(query_attempt["attempted"] is False for query_attempt in attempt["queries"])
    assert all(query_attempt["result_count"] == 0 for query_attempt in attempt["queries"])
    assert all(query_attempt["error"] is None for query_attempt in attempt["queries"])


def test_build_short_editing_plan_use_case_keeps_processing_synthetic_manual_overrides_after_matched_one(tmp_path):
    writer = FakeWriter()
    matched_asset = tmp_path / "matched.mp4"
    synthetic_asset = tmp_path / "synthetic.mp4"
    matched_asset.write_bytes(b"matched")
    synthetic_asset.write_bytes(b"synthetic")
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=writer,
        beat_detector=SingleBeatDetector(
            _build_detected_beat("beat-0001", "negative thoughts alone", 2000, 3600, 0.89)
        ),
        manual_override_loader=FakeManualOverrideLoader(
            (
                build_manual_override(
                    short_id="short-manual-loop",
                    anchor_text="negative thoughts",
                    asset_path=str(matched_asset),
                    mode="full_frame_cutaway",
                    priority=300,
                ),
                build_manual_override(
                    short_id="short-manual-loop",
                    anchor_text="confusing negatives",
                    asset_path=str(synthetic_asset),
                    mode="full_frame_cutaway",
                    priority=200,
                ),
            )
        ),
        enabled=True,
    )

    plan = use_case.build(
        short_id="short-manual-loop",
        timeline=_build_timeline(0, 12000),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    assert [payload["beat_id"] for payload in writer.candidate_payload[1]] == [
        "beat-0001",
        "manual-beat-0001",
    ]
    assert writer.candidate_payload[1][0]["selection_source"] == "manual_override"
    assert writer.candidate_payload[1][1]["selection_source"] == "manual_override"
    assert writer.candidate_payload[1][1]["anchor_text"] == "confusing negatives"


def test_build_short_editing_plan_use_case_prefer_local_candidates_drops_remote_when_disallowed():
    selection = BeatCandidateSelection(
        beat=_build_detected_beat("beat-local-priority", "launch product office", 2000, 3600, 0.9),
        candidates=(
            _build_candidate(
                candidate_id="remote-1",
                provider="pexels",
                discovery_source="pexels",
                local_path="/tmp/remote-1.mp4",
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
            _build_candidate(
                candidate_id="heuristic-1",
                provider="local_media",
                discovery_source="local_heuristic_fallback",
                local_path="/tmp/heuristic-1.mp4",
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
            _build_candidate(
                candidate_id="local-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path="/tmp/local-1.mp4",
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
        ),
        priority=900,
    )

    prioritized = BuildShortEditingPlanUseCase._prefer_local_candidates(selection, allow_remote=False)

    assert [candidate.candidate_id for candidate in prioritized.candidates] == ["local-1", "heuristic-1"]
    assert prioritized.priority == 900
    assert prioritized.beat is selection.beat


def test_build_short_editing_plan_use_case_load_manual_overrides_handles_none_and_loader_values(tmp_path):
    override_asset = tmp_path / "manual.mp4"
    override_asset.write_bytes(b"video")
    override = build_manual_override(
        short_id="short-load-overrides",
        anchor_text="job interview",
        asset_path=str(override_asset),
        mode="full_frame_cutaway",
        priority=250,
    )
    without_loader = BuildShortEditingPlanUseCase(providers=(), plan_writer=FakeWriter(), enabled=True)
    with_loader = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=FakeWriter(),
        manual_override_loader=FakeManualOverrideLoader((override,)),
        enabled=True,
    )

    assert without_loader._load_manual_overrides() == ()
    assert with_loader._load_manual_overrides() == (override,)


def test_build_short_editing_plan_use_case_prepare_candidates_only_prepares_first_two_known_provider_assets(tmp_path):
    class TrackingProvider:
        provider_name = "recording"

        def __init__(self):
            self.prepared_ids = []

        def prepare_asset(self, candidate, cache_dir):
            self.prepared_ids.append((candidate.candidate_id, cache_dir))
            return type(candidate)(
                **{**candidate.__dict__, "local_path": str(Path(cache_dir) / f"{candidate.candidate_id}.mp4")}
            )

    provider = TrackingProvider()
    cache_dir = str(tmp_path / ".cache" / "broll" / "assets")
    prepared = BuildShortEditingPlanUseCase._prepare_candidates(
        ranked_candidates=[
            _build_candidate(
                candidate_id="prepare-1",
                provider="recording",
                discovery_source="pexels",
                local_path=None,
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
            _build_candidate(
                candidate_id="prepare-2",
                provider="recording",
                discovery_source="pexels",
                local_path=None,
                title="confusing negatives",
                tags=("confusing", "negatives"),
            ),
            _build_candidate(
                candidate_id="prepare-3",
                provider="recording",
                discovery_source="pexels",
                local_path=None,
                title="job interview",
                tags=("job", "interview"),
            ),
        ],
        providers_by_name={"recording": provider},
        cache_dir=cache_dir,
    )

    assert provider.prepared_ids == [("prepare-1", cache_dir), ("prepare-2", cache_dir)]
    assert [candidate.local_path for candidate in prepared] == [
        str(Path(cache_dir) / "prepare-1.mp4"),
        str(Path(cache_dir) / "prepare-2.mp4"),
        None,
    ]


def test_build_short_editing_plan_use_case_candidate_payload_includes_only_present_optional_fields():
    beat = _build_detected_beat("beat-payload", "launch product office", 2000, 3600, 0.9)
    candidate = _build_candidate(
        candidate_id="payload-1",
        provider="local_media",
        discovery_source="local_manifest",
        local_path="/tmp/payload-1.mp4",
        title="launch product office",
        tags=("launch", "product", "office"),
    )
    base_selection = BeatCandidateSelection(beat=beat, candidates=(candidate,), selection_source="automatic")
    forced_selection = BeatCandidateSelection(
        beat=beat,
        candidates=(candidate,),
        forced_mode="full_frame_cutaway",
        anchor_text="launch product",
        selection_source="manual_override",
    )

    base_payload = BuildShortEditingPlanUseCase._candidate_payload(
        beat=beat,
        queries=("launch product office",),
        candidates=(candidate,),
        selection=base_selection,
    )
    forced_payload = BuildShortEditingPlanUseCase._candidate_payload(
        beat=beat,
        queries=(),
        candidates=(candidate,),
        selection=forced_selection,
        provider_attempts=[{"provider": "pexels", "attempted": True}],
    )

    assert "provider_attempts" not in base_payload
    assert "anchor_text" not in base_payload
    assert "forced_mode" not in base_payload
    assert forced_payload["provider_attempts"] == [{"provider": "pexels", "attempted": True}]
    assert forced_payload["anchor_text"] == "launch product"
    assert forced_payload["forced_mode"] == "full_frame_cutaway"

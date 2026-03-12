from pathlib import Path

from src.application.broll import BuildShortEditingPlanUseCase
from src.domain.broll_models import BrollCandidate, ImpactBeat
from src.domain.manual_broll_overrides import ManualBrollOverride
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline


class FakeWriter:
    def __init__(self):
        self.impact_payload = None
        self.candidate_payload = None
        self.plan_payload = None

    def write_impact_beats(self, short_id, timeline, beats, output_dir):
        self.impact_payload = (short_id, timeline, beats, output_dir)

    def write_broll_candidates(self, short_id, beats, output_dir):
        self.candidate_payload = (short_id, beats, output_dir)

    def write_broll_plan(self, short_id, plan, output_dir):
        self.plan_payload = (short_id, plan, output_dir)


class FakeProvider:
    provider_name = "fake"

    def __init__(self):
        self.prepare_calls = 0
        self.search_calls = 0

    def search(self, beat, queries, cache_dir):
        del cache_dir
        self.search_calls += 1
        candidate_title = queries[0] if queries else beat.text
        candidate_tags = tuple(token for token in candidate_title.split()[:3] if token)
        return [
            BrollCandidate(
                candidate_id="fake-1",
                provider="fake",
                discovery_source="fake",
                asset_type="video",
                asset_url="https://example.com/fake.mp4",
                local_path=None,
                duration_ms=2500,
                width=1080,
                height=1920,
                orientation="vertical",
                title=candidate_title,
                tags=candidate_tags,
            )
        ]

    def prepare_asset(self, candidate, cache_dir):
        self.prepare_calls += 1
        return BrollCandidate(**{**candidate.__dict__, "local_path": str(Path(cache_dir) / "fake-1.mp4")})


class FakeDetector:
    @staticmethod
    def detect(timeline):
        del timeline
        return [
            ImpactBeat(
                beat_id="beat-0001",
                text="launch product in office",
                start_ms=2000,
                end_ms=3600,
                duration_ms=1600,
                timing_mode="reconciled_asr",
                word_confidence_avg=0.81,
                cue_quality_score=0.85,
                scores=type(
                    "Scores",
                    (),
                    {
                        "total": 0.89,
                        "to_dict": lambda self: {"total": 0.89},
                    },
                )(),
                reasons=("contains concrete or visual anchors",),
            )
        ]


class TwoBeatDetector:
    @staticmethod
    def detect(timeline):
        del timeline
        return [
            _build_detected_beat("beat-0001", "negative thoughts alone", 2000, 3600, 0.89),
            _build_detected_beat("beat-0002", "confusing negatives", 8000, 9600, 0.82),
        ]


class ConfusingBeatDetector:
    @staticmethod
    def detect(timeline):
        del timeline
        return [
            ImpactBeat(
                beat_id="beat-confusing",
                text="It's so confusing with all those negatives.",
                start_ms=2000,
                end_ms=3960,
                duration_ms=1960,
                timing_mode="reconciled_asr",
                word_confidence_avg=0.94,
                cue_quality_score=0.95,
                scores=type(
                    "Scores",
                    (),
                    {
                        "total": 0.35,
                        "to_dict": lambda self: {"total": 0.35},
                    },
                )(),
                reasons=("manual target phrase",),
            )
        ]


def test_build_short_editing_plan_use_case_returns_disabled_plan_when_feature_is_off(tmp_path):
    writer = FakeWriter()
    use_case = BuildShortEditingPlanUseCase(
        providers=(),
        plan_writer=writer,
        enabled=False,
    )

    plan = use_case.build(
        short_id="short_0",
        timeline=SubtitleTimeline(0, 1000, (), (), 0.0),
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.enabled is False
    assert plan.insertions == ()
    assert writer.impact_payload is None


def test_build_short_editing_plan_use_case_writes_artifacts_and_prepares_candidates(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=10000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="launch product in office",
                start_ms=2000,
                end_ms=3600,
                timing_mode="reconciled_asr",
                quality_score=0.85,
                words=(
                    ProjectedWord("launch", 2000, 2400, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 2400, 3000, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("office", 3000, 3600, 0.8, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.85,
    )

    plan = use_case.build(
        short_id="short_0",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.enabled is True
    assert len(plan.insertions) == 1
    assert provider.prepare_calls == 2
    assert writer.impact_payload[0] == "short_0"
    assert writer.candidate_payload[0] == "short_0"
    assert writer.plan_payload[0] == "short_0"
    assert writer.candidate_payload[1][0]["candidates"][0]["discovery_source"] == "fake"
    assert writer.candidate_payload[1][0]["provider_attempts"][0]["provider"] == "fake"
    assert writer.candidate_payload[1][0]["provider_attempts"][0]["queries"][0]["result_count"] == 1


def test_build_short_editing_plan_use_case_creates_insertion_for_confusing_phrase(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="It's so confusing with all those negatives.",
                start_ms=2000,
                end_ms=3960,
                timing_mode="reconciled_asr",
                quality_score=0.95,
                words=(
                    ProjectedWord("It's", 2000, 2280, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("so", 2280, 2560, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("confusing", 2560, 2840, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("with", 2840, 3120, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("all", 3120, 3400, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("those", 3400, 3680, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("negatives.", 3680, 3960, 0.94, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.95,
    )

    plan = use_case.build(
        short_id="short_1",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert plan.enabled is True
    assert len(plan.insertions) == 1
    assert writer.impact_payload[2][0].text == "It's so confusing with all those negatives."
    assert writer.candidate_payload[1][0]["candidates"][0]["discovery_source"] == "fake"


class FakeManualOverrideLoader:
    def __init__(self, overrides):
        self.overrides = overrides

    def load(self):
        return self.overrides


class FailingProvider:
    provider_name = "pexels"
    api_key = "configured-token"

    @staticmethod
    def search(beat, queries, cache_dir):
        del beat, queries, cache_dir
        raise RuntimeError("boom")

    @staticmethod
    def prepare_asset(candidate, cache_dir):
        del candidate, cache_dir
        raise AssertionError("prepare_asset should not be called")


def test_build_short_editing_plan_use_case_prefers_manual_override_and_bypasses_auto_provider(tmp_path):
    writer = FakeWriter()
    provider = FakeProvider()
    manual_asset = tmp_path / "manual-confusing.mp4"
    manual_asset.write_bytes(b"video")
    use_case = BuildShortEditingPlanUseCase(
        providers=(provider,),
        plan_writer=writer,
        beat_detector=ConfusingBeatDetector(),
        manual_override_loader=FakeManualOverrideLoader(
            (
                ManualBrollOverride(
                    short_id="short_0",
                    anchor_text="so confusing",
                    asset_path=str(manual_asset),
                    mode="full_frame_cutaway",
                    priority=250,
                ),
            )
        ),
        enabled=True,
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="It's so confusing with all those negatives.",
                start_ms=2000,
                end_ms=3960,
                timing_mode="reconciled_asr",
                quality_score=0.95,
                words=(
                    ProjectedWord("It's", 2000, 2280, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("so", 2280, 2560, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("confusing", 2560, 2840, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("with", 2840, 3120, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("all", 3120, 3400, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("those", 3400, 3680, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("negatives.", 3680, 3960, 0.94, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.95,
    )

    plan = use_case.build(
        short_id="short_0",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].mode == "full_frame_cutaway"
    assert plan.insertions[0].asset_provider == "manual_override"
    assert plan.insertions[0].discovery_source == "manual_override"
    assert provider.search_calls == 0
    assert writer.candidate_payload[1][0]["selection_source"] == "manual_override"


def test_build_short_editing_plan_use_case_audits_provider_errors_in_candidate_payload(tmp_path):
    writer = FakeWriter()
    use_case = BuildShortEditingPlanUseCase(
        providers=(FailingProvider(),),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )
    timeline = _build_timeline(0, 12000)

    plan = use_case.build(
        short_id="short_provider_audit",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 0
    attempt = writer.candidate_payload[1][0]["provider_attempts"][0]
    assert attempt["provider"] == "pexels"
    assert attempt["configured"] is True
    assert attempt["attempted"] is True
    assert attempt["queries"][0]["error"] == "RuntimeError: boom"
    assert attempt["queries"][0]["result_count"] == 0


def test_build_short_editing_plan_use_case_prefers_local_candidates_over_remote_when_target_is_met(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
            _build_candidate(
                candidate_id="local-2",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-2.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="remote-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "remote-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    timeline = _build_timeline(0, 24000)
    plan = use_case.build(
        short_id="short_local_first",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    assert all(insertion.asset_provider == "local_media" for insertion in plan.insertions)
    assert all(insertion.discovery_source == "local_manifest" for insertion in plan.insertions)
    assert all(insertion.mode == "full_frame_cutaway" for insertion in plan.insertions)


def test_build_short_editing_plan_use_case_uses_remote_when_local_density_is_insufficient(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="remote-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "remote-1.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    timeline = _build_timeline(0, 24000)
    plan = use_case.build(
        short_id="short_remote_fallback",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    assert any(insertion.asset_provider == "pixabay" for insertion in plan.insertions)
    assert any(insertion.asset_provider == "local_media" for insertion in plan.insertions)


def test_build_short_editing_plan_use_case_uses_remote_when_local_match_is_semantically_too_weak(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-1.mp4"),
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
            _build_candidate(
                candidate_id="local-2",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / "local-2.mp4"),
                title="negatives",
                tags=("negatives",),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="remote-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "remote-1.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    timeline = _build_timeline(0, 24000)
    plan = use_case.build(
        short_id="short_remote_semantic_fallback",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    second_insertion = next(insertion for insertion in plan.insertions if insertion.beat_id == "beat-0002")
    assert second_insertion.asset_provider == "pixabay"
    assert second_insertion.discovery_source == "pixabay"


def test_build_short_editing_plan_use_case_uses_remote_when_local_asset_would_repeat_within_short(tmp_path):
    writer = FakeWriter()
    shared_local = str(tmp_path / "local-shared.mp4")
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id="local-shared-1",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=shared_local,
                title="negative thoughts alone",
                tags=("negative", "thoughts", "alone"),
            ),
            _build_candidate(
                candidate_id="local-shared-2",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=shared_local,
                title="confusing negatives",
                tags=("confusing", "negatives"),
            ),
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pexels",
        candidates=[
            _build_candidate(
                candidate_id="pexels-1",
                provider="pexels",
                discovery_source="pexels",
                local_path=str(tmp_path / "pexels-1.mp4"),
                title="confusing negatives",
                tags=("confusing", "negatives"),
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=TwoBeatDetector(),
        enabled=True,
    )

    timeline = _build_timeline(0, 24000)
    plan = use_case.build(
        short_id="short_remote_after_local_repeat",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 2
    first_insertion = next(insertion for insertion in plan.insertions if insertion.beat_id == "beat-0001")
    second_insertion = next(insertion for insertion in plan.insertions if insertion.beat_id == "beat-0002")
    assert first_insertion.asset_provider == "local_media"
    assert second_insertion.asset_provider == "pexels"
    assert second_insertion.discovery_source == "pexels"


def test_build_short_editing_plan_use_case_keeps_remote_candidates_beyond_top_local_slots(tmp_path):
    writer = FakeWriter()
    local_provider = FakeStaticProvider(
        provider_name="local_media",
        candidates=[
            _build_candidate(
                candidate_id=f"local-{index}",
                provider="local_media",
                discovery_source="local_manifest",
                local_path=str(tmp_path / f"local-{index}.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
            )
            for index in range(6)
        ],
    )
    remote_provider = FakeStaticProvider(
        provider_name="pexels",
        candidates=[
            _build_candidate(
                candidate_id="pexels-1",
                provider="pexels",
                discovery_source="pexels",
                local_path=str(tmp_path / "pexels-1.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(remote_provider, local_provider),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )

    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=10000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="launch product in office",
                start_ms=2000,
                end_ms=3600,
                timing_mode="reconciled_asr",
                quality_score=0.85,
                words=(
                    ProjectedWord("launch", 2000, 2400, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 2400, 3000, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("office", 3000, 3600, 0.8, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.85,
    )

    use_case.build(
        short_id="short_keep_remote_candidates",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    candidate_payload = writer.candidate_payload[1][0]["candidates"]
    assert any(candidate["discovery_source"] == "pexels" for candidate in candidate_payload)


def test_build_short_editing_plan_use_case_prefers_pexels_over_pixabay_within_remote_fallback(tmp_path):
    writer = FakeWriter()
    pexels_provider = FakeStaticProvider(
        provider_name="pexels",
        candidates=[
            _build_candidate(
                candidate_id="pexels-1",
                provider="pexels",
                discovery_source="pexels",
                local_path=str(tmp_path / "pexels-1.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
            ),
        ],
    )
    pixabay_provider = FakeStaticProvider(
        provider_name="pixabay",
        candidates=[
            _build_candidate(
                candidate_id="pixabay-1",
                provider="pixabay",
                discovery_source="pixabay",
                local_path=str(tmp_path / "pixabay-1.mp4"),
                title="launch product office",
                tags=("launch", "product", "office"),
                width=2560,
                height=1440,
            ),
        ],
    )
    use_case = BuildShortEditingPlanUseCase(
        providers=(pixabay_provider, pexels_provider),
        plan_writer=writer,
        beat_detector=FakeDetector(),
        enabled=True,
    )

    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=10000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="launch product in office",
                start_ms=2000,
                end_ms=3600,
                timing_mode="reconciled_asr",
                quality_score=0.85,
                words=(
                    ProjectedWord("launch", 2000, 2400, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("product", 2400, 3000, 0.8, "reconciled", "exact_normalized"),
                    ProjectedWord("office", 3000, 3600, 0.8, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.85,
    )

    plan = use_case.build(
        short_id="short_pexels_remote_priority",
        timeline=timeline,
        output_dir=str(tmp_path),
        target_width=1080,
        target_height=1920,
    )

    assert len(plan.insertions) == 1
    assert plan.insertions[0].asset_provider == "pexels"
    assert plan.insertions[0].discovery_source == "pexels"


class FakeStaticProvider:
    def __init__(self, provider_name, candidates):
        self.provider_name = provider_name
        self.candidates = candidates

    def search(self, beat, queries, cache_dir):
        del cache_dir
        reference_text = " ".join(queries) or beat.text
        reference_tokens = {token.lower() for token in reference_text.replace(".", "").split() if token}
        matched_candidates = []
        for candidate in self.candidates:
            candidate_tokens = {
                token.lower()
                for token in " ".join((candidate.title, *candidate.tags)).replace(".", "").split()
                if token
            }
            if candidate_tokens & reference_tokens:
                matched_candidates.append(candidate)
        return matched_candidates

    @staticmethod
    def prepare_asset(candidate, cache_dir):
        del cache_dir
        return candidate


def _build_detected_beat(beat_id: str, text: str, start_ms: int, end_ms: int, total: float) -> ImpactBeat:
    return ImpactBeat(
        beat_id=beat_id,
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.92,
        cue_quality_score=0.9,
        scores=type(
            "Scores",
            (),
            {
                "total": total,
                "to_dict": lambda self: {"total": total},
            },
        )(),
        reasons=("contains concrete or visual anchors",),
    )


def _build_candidate(
    candidate_id: str,
    provider: str,
    discovery_source: str,
    local_path: str | None,
    title: str,
    tags: tuple[str, ...],
    width: int = 1080,
    height: int = 1920,
) -> BrollCandidate:
    return BrollCandidate(
        candidate_id=candidate_id,
        provider=provider,
        discovery_source=discovery_source,
        asset_type="video",
        asset_url=f"https://example.com/{candidate_id}.mp4",
        local_path=local_path,
        duration_ms=2500,
        width=width,
        height=height,
        orientation="vertical" if height >= width else "landscape",
        title=title,
        tags=tags,
    )


def _build_timeline(start_ms: int, end_ms: int) -> SubtitleTimeline:
    return SubtitleTimeline(
        interval_start_ms=start_ms,
        interval_end_ms=end_ms,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="negative thoughts alone",
                start_ms=2000,
                end_ms=3600,
                timing_mode="reconciled_asr",
                quality_score=0.9,
                words=(
                    ProjectedWord("negative", 2000, 2500, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("thoughts", 2500, 3000, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("alone", 3000, 3600, 0.9, "reconciled", "exact_normalized"),
                ),
            ),
            ProjectedCue(
                cue_id="cue-2",
                speaker="Speaker 2",
                original_text="confusing negatives",
                start_ms=8000,
                end_ms=9600,
                timing_mode="reconciled_asr",
                quality_score=0.9,
                words=(
                    ProjectedWord("confusing", 8000, 8800, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("negatives", 8800, 9600, 0.9, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.9,
    )

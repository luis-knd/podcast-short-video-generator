from pathlib import Path

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
        self.search_cache_dirs = []
        self.prepare_cache_dirs = []

    def search(self, beat, queries, cache_dir):
        self.search_calls += 1
        self.search_cache_dirs.append(cache_dir)
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
        self.prepare_cache_dirs.append(cache_dir)
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


class CandidateOnlyDetector:
    @staticmethod
    def detect_candidates(timeline):
        del timeline
        return [_build_detected_beat("beat-candidate", "launch product office", 2000, 3600, 0.91)]

    @staticmethod
    def detect(_timeline):
        raise AssertionError("detect should not be called when detect_candidates exists")


class EmptyQueryGenerator:
    @staticmethod
    def generate(_beat):
        return ()


class SingleQueryGenerator:
    @staticmethod
    def generate(_beat):
        return ("launch product office",)


class DualQueryGenerator:
    @staticmethod
    def generate(_beat):
        return ("launch product office", "confusing negatives")


class UnconfiguredProvider:
    provider_name = "pixabay"
    api_key = ""

    @staticmethod
    def search(_beat, _queries, _cache_dir):
        raise AssertionError("search should not be called when provider is not configured")

    @staticmethod
    def prepare_asset(candidate, cache_dir):
        del cache_dir
        return candidate


class RaisingLoader:
    @staticmethod
    def load():
        raise TypeError("invalid overrides")


class TimelineTrackingDetector:
    def __init__(self, beat):
        self.beat = beat
        self.seen_timeline = None

    def detect(self, timeline):
        self.seen_timeline = timeline
        return [self.beat]


class RaiseOnPrepareProvider:
    provider_name = "local_media"

    def __init__(self, candidate):
        self.candidate = candidate
        self.prepare_calls = 0

    def search(self, beat, queries, cache_dir):
        del beat, queries, cache_dir
        return [self.candidate]

    def prepare_asset(self, candidate, cache_dir):
        del candidate, cache_dir
        self.prepare_calls += 1
        raise OSError("cannot prepare")


class TrackingFailingProvider:
    provider_name = "pexels"
    api_key = "configured-token"

    def __init__(self):
        self.searched_queries = []

    def search(self, beat, queries, cache_dir):
        del beat, cache_dir
        self.searched_queries.append(queries[0])
        raise RuntimeError("boom")

    @staticmethod
    def prepare_asset(candidate, cache_dir):
        del candidate, cache_dir
        raise AssertionError("prepare_asset should not be called")


class ClassNameFallbackProvider:
    def __init__(self):
        self.prepare_calls = 0

    @staticmethod
    def search(beat, queries, cache_dir):
        del beat, queries, cache_dir
        return [
            BrollCandidate(
                candidate_id="class-name-1",
                provider="classnamefallback",
                discovery_source="pexels",
                asset_type="video",
                asset_url="https://example.com/class-name.mp4",
                local_path=None,
                duration_ms=2000,
                width=1080,
                height=1920,
                orientation="vertical",
                title="launch product office",
                tags=("launch", "product", "office"),
            )
        ]

    def prepare_asset(self, candidate, cache_dir):
        self.prepare_calls += 1
        return BrollCandidate(**{**candidate.__dict__, "local_path": str(Path(cache_dir) / "class-name-1.mp4")})


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


def build_manual_override(short_id: str, anchor_text: str, asset_path: str, mode: str, priority: int):
    return ManualBrollOverride(
        short_id=short_id,
        anchor_text=anchor_text,
        asset_path=asset_path,
        mode=mode,
        priority=priority,
    )


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

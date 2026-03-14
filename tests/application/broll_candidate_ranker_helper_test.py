from src.application.broll.broll_candidate_ranker import BrollCandidateRanker
from src.domain.broll_models import BeatScoreBreakdown, BrollCandidate, ImpactBeat


def test_candidate_ranker_semantic_match_uses_query_tokens_and_filename_tokens():
    score = BrollCandidateRanker._semantic_match(
        _build_beat("alpha"),
        ("beta gamma",),
        _build_candidate(
            "filename-match",
            "",
            "https://cdn.example/beta_gamma-launch.mp4",
            (),
            1600,
            720,
            1280,
            "vertical",
            "/tmp/filename-match.mp4",
        ),
    )

    assert score == 0.6667


def test_candidate_ranker_semantic_match_caps_overlap_score_at_one():
    score = BrollCandidateRanker._semantic_match(
        _build_beat("one two three four five six"),
        (),
        _build_candidate(
            "capped",
            "one two three four five",
            "https://cdn.example/six-seven.mp4",
            (),
            1600,
            720,
            1280,
            "vertical",
            "/tmp/capped.mp4",
        ),
    )

    assert score == 1.0


def test_candidate_ranker_duration_fit_distinguishes_local_zero_duration_from_remote_only():
    beat = _build_beat("market launch")

    assert (
        BrollCandidateRanker._duration_fit(
            beat,
            _build_candidate(
                "local-zero",
                "market",
                "https://cdn.example/local.mp4",
                (),
                0,
                0,
                0,
                "unknown",
                "/tmp/local.mp4",
            ),
        )
        == 0.65
    )
    assert (
        BrollCandidateRanker._duration_fit(
            beat,
            _build_candidate(
                "remote-zero",
                "market",
                "https://cdn.example/remote.mp4",
                (),
                0,
                0,
                0,
                "unknown",
                None,
            ),
        )
        == 0.0
    )


def test_candidate_ranker_duration_fit_uses_partial_coverage_ratio_with_rounding():
    beat = _build_beat("market launch")

    assert (
        BrollCandidateRanker._duration_fit(
            beat,
            _build_candidate(
                "partial-coverage",
                "market",
                "https://cdn.example/partial.mp4",
                (),
                1000,
                720,
                1280,
                "vertical",
                "/tmp/partial.mp4",
            ),
        )
        == 0.625
    )


def test_candidate_ranker_technical_quality_distinguishes_local_and_remote_missing_dimensions():
    assert (
        BrollCandidateRanker._technical_quality(
            _build_candidate(
                "local-missing",
                "market",
                "https://cdn.example/local.mp4",
                (),
                1600,
                0,
                0,
                "unknown",
                "/tmp/local.mp4",
            ),
        )
        == 0.40
    )
    assert (
        BrollCandidateRanker._technical_quality(
            _build_candidate(
                "remote-missing",
                "market",
                "https://cdn.example/remote.mp4",
                (),
                1600,
                0,
                0,
                "unknown",
                None,
            ),
        )
        == 0.25
    )


def test_candidate_ranker_visual_and_orientation_helpers_keep_expected_mapping_values():
    assert (
        BrollCandidateRanker._visual_fit(
            _build_candidate(
                "vertical-video",
                "market",
                "https://cdn.example/vertical.mp4",
                (),
                1600,
                720,
                1280,
                "vertical",
                "/tmp/vertical.mp4",
            ),
        )
        == 0.95
    )
    assert (
        BrollCandidateRanker._visual_fit(
            _build_candidate(
                "square-image",
                "market",
                "https://cdn.example/still.png",
                (),
                0,
                1080,
                1080,
                "square",
                "/tmp/still.png",
                asset_type="image",
            ),
        )
        == 0.68
    )
    assert (
        BrollCandidateRanker._orientation_fit(
            _build_candidate(
                "landscape",
                "market",
                "https://cdn.example/landscape.mp4",
                (),
                1600,
                1280,
                720,
                "landscape",
                "/tmp/landscape.mp4",
            ),
        )
        == 0.55
    )
    assert (
        BrollCandidateRanker._orientation_fit(
            _build_candidate(
                "unknown",
                "market",
                "https://cdn.example/unknown.mp4",
                (),
                1600,
                1280,
                720,
                "unknown",
                "/tmp/unknown.mp4",
            ),
        )
        == 0.40
    )


def _build_beat(text: str) -> ImpactBeat:
    return ImpactBeat(
        beat_id="beat-1",
        text=text,
        start_ms=1000,
        end_ms=2600,
        duration_ms=1600,
        timing_mode="aligned",
        word_confidence_avg=0.92,
        cue_quality_score=0.9,
        scores=BeatScoreBreakdown(
            total=0.9,
            visualizability=0.8,
            emotional_load=0.7,
            contrast=0.6,
            narrative_turn=0.5,
            verbal_force=0.7,
            duration_fit=0.9,
            timing_confidence=0.95,
        ),
        reasons=("visual anchors",),
    )


def _build_candidate(
    candidate_id: str,
    title: str,
    asset_url: str,
    tags: tuple[str, ...],
    duration_ms: int,
    width: int,
    height: int,
    orientation: str,
    local_path: str | None,
    asset_type: str = "video",
    provider: str = "test",
    discovery_source: str = "test",
) -> BrollCandidate:
    return BrollCandidate(
        candidate_id=candidate_id,
        provider=provider,
        discovery_source=discovery_source,
        asset_type=asset_type,
        asset_url=asset_url,
        local_path=local_path,
        duration_ms=duration_ms,
        width=width,
        height=height,
        orientation=orientation,
        title=title,
        tags=tags,
    )

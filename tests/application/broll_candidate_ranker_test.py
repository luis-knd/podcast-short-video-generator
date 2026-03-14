import pytest

from src.application.broll.broll_candidate_ranker import BrollCandidateRanker
from src.domain.broll_models import BeatScoreBreakdown, BrollCandidate, ImpactBeat


def test_candidate_ranker_orders_candidates_and_scores_semantic_fit():
    ranker = BrollCandidateRanker()
    beat = _build_beat("budget crash in office")

    ranked = ranker.rank(
        beat,
        ("budget crash",),
        [
            _build_candidate(
                candidate_id="weak",
                title="",
                asset_url="",
                tags=(),
                duration_ms=0,
                width=0,
                height=0,
                orientation="unknown",
                local_path=None,
            ),
            _build_candidate(
                candidate_id="strong",
                title="budget office crash",
                asset_url="https://example.com/office-crash.mp4",
                tags=("budget", "office"),
                duration_ms=1600,
                width=720,
                height=1280,
                orientation="vertical",
                local_path="/tmp/strong.mp4",
            ),
        ],
    )

    assert [candidate.candidate_id for candidate in ranked] == ["strong", "weak"]
    assert ranked[0].semantic_match > ranked[1].semantic_match
    assert ranked[1].semantic_match == 0.0
    assert ranked[1].duration_fit == 0.0
    assert ranked[1].orientation_fit == 0.40
    assert ranked[1].technical_quality == 0.25


@pytest.mark.parametrize(
    ("width", "height", "local_path", "expected_quality"),
    [
        (0, 0, "/tmp/local.mp4", 0.40),
        (1920, 1080, "/tmp/hd.mp4", 1.0),
        (1280, 720, "/tmp/720p.mp4", 0.80),
        (720, 720, "/tmp/square.mp4", 0.60),
        (320, 240, "/tmp/small.mp4", 0.40),
    ],
)
def test_candidate_ranker_scores_technical_quality_thresholds(width, height, local_path, expected_quality):
    ranker = BrollCandidateRanker()
    beat = _build_beat("market launch")

    ranked = ranker.rank(
        beat,
        ("market launch",),
        [
            _build_candidate(
                candidate_id="candidate",
                title="market launch",
                asset_url="https://example.com/market.mp4",
                tags=("market",),
                duration_ms=1800,
                width=width,
                height=height,
                orientation="landscape",
                local_path=local_path,
            )
        ],
    )

    assert ranked[0].technical_quality == expected_quality


def test_candidate_ranker_scores_image_duration_and_square_visual_fit():
    ranker = BrollCandidateRanker()
    beat = _build_beat("city street")

    ranked = ranker.rank(
        beat,
        ("city street",),
        [
            _build_candidate(
                candidate_id="image",
                asset_type="image",
                title="city street",
                asset_url="https://example.com/street.png",
                tags=("city", "street"),
                duration_ms=0,
                width=1080,
                height=1080,
                orientation="square",
                local_path="/tmp/street.png",
            )
        ],
    )

    assert ranked[0].duration_fit == 0.70
    assert ranked[0].visual_fit == 0.68
    assert ranked[0].orientation_fit == 0.75


def test_candidate_ranker_treats_longer_videos_as_trim_capable():
    ranker = BrollCandidateRanker()
    beat = _build_beat("negative thoughts")

    ranked = ranker.rank(
        beat,
        ("negative thoughts",),
        [
            _build_candidate(
                candidate_id="trim-capable",
                title="negative thought cloud",
                asset_url="https://example.com/thought-cloud.mp4",
                tags=("negative", "thoughts"),
                duration_ms=5200,
                width=464,
                height=832,
                orientation="vertical",
                local_path="/tmp/thought-cloud.mp4",
            )
        ],
    )

    assert ranked[0].duration_fit == 1.0
    assert ranked[0].total_score > 0.55


def test_candidate_ranker_prefers_vertical_pexels_when_semantics_are_comparable():
    ranker = BrollCandidateRanker()
    beat = _build_beat("negative thoughts")

    ranked = ranker.rank(
        beat,
        ("bad negative thoughts",),
        [
            _build_candidate(
                candidate_id="pixabay-landscape",
                title="bad negative thoughts",
                asset_url="https://example.com/pixabay.mp4",
                tags=("negative", "thoughts"),
                duration_ms=4000,
                width=1280,
                height=720,
                orientation="landscape",
                local_path="/tmp/pixabay.mp4",
                provider="pixabay",
                discovery_source="pixabay",
            ),
            _build_candidate(
                candidate_id="pexels-vertical",
                title="bad negative thoughts",
                asset_url="https://example.com/pexels.mp4",
                tags=("negative", "thoughts"),
                duration_ms=4000,
                width=720,
                height=1280,
                orientation="vertical",
                local_path="/tmp/pexels.mp4",
                provider="pexels",
                discovery_source="pexels",
            ),
        ],
    )

    assert ranked[0].candidate_id == "pexels-vertical"
    assert ranked[0].total_score > ranked[1].total_score


def test_candidate_ranker_diversity_bonus_is_point10_with_tags_and_point05_without():
    ranker = BrollCandidateRanker()
    beat = _build_beat("office workspace")

    ranked = ranker.rank(
        beat,
        ("office",),
        [
            _build_candidate(
                "with-tags",
                "office workspace",
                "https://x.com/c.mp4",
                ("office",),
                2000,
                720,
                1280,
                "vertical",
                "/tmp/a.mp4",
            ),
            _build_candidate("no-tags", "", "https://x.com/d.mp4", (), 2000, 720, 1280, "vertical", "/tmp/b.mp4"),
        ],
    )

    with_tags = next(c for c in ranked if c.candidate_id == "with-tags")
    without_tags = next(c for c in ranked if c.candidate_id == "no-tags")
    assert with_tags.diversity_bonus == 0.10
    assert without_tags.diversity_bonus == 0.05


@pytest.mark.parametrize(
    ("provider", "orientation", "expected_bonus"),
    [
        ("pexels", "vertical", 0.03),
        ("pixabay", "landscape", -0.01),
        ("local", "vertical", 0.0),
        ("pexels", "landscape", 0.0),
    ],
)
def test_candidate_ranker_source_preference_bonus_is_added_to_total_score(provider, orientation, expected_bonus):
    ranker = BrollCandidateRanker()
    beat = _build_beat("office workspace")

    ranked = ranker.rank(
        beat,
        ("office workspace",),
        [
            _build_candidate(
                "cand",
                "office workspace",
                "https://cdn.example/clip.mp4",
                ("office", "workspace"),
                5000,
                720,
                1280,
                orientation,
                "/tmp/cand.mp4",
                provider=provider,
                discovery_source=provider,
            )
        ],
    )

    c = ranked[0]
    score_without_bonus = round(
        0.40 * c.semantic_match
        + 0.20 * c.visual_fit
        + 0.15 * c.duration_fit
        + 0.10 * c.orientation_fit
        + 0.10 * c.diversity_bonus
        + 0.05 * c.technical_quality,
        4,
    )
    assert abs(c.total_score - (score_without_bonus + expected_bonus)) < 0.0005


def test_candidate_ranker_total_score_uses_exact_weight_coefficients():
    ranker = BrollCandidateRanker()
    beat = _build_beat("office workspace")

    ranked = ranker.rank(
        beat,
        ("office workspace",),
        [
            _build_candidate(
                "scored",
                "office workspace",
                "https://cdn.example/clip.mp4",
                ("office", "workspace"),
                5000,
                1280,
                720,
                "vertical",
                "/tmp/scored.mp4",
                provider="pexels",
                discovery_source="pexels",
            )
        ],
    )

    c = ranked[0]
    assert c.semantic_match == 1.0
    assert c.visual_fit == 0.95
    assert c.duration_fit == 1.0
    assert c.orientation_fit == 1.0
    assert c.diversity_bonus == 0.10
    assert c.technical_quality == 0.80
    expected = round(
        0.40 * 1.0 + 0.20 * 0.95 + 0.15 * 1.0 + 0.10 * 1.0 + 0.10 * 0.10 + 0.05 * 0.80 + 0.03,
        4,
    )
    assert c.total_score == pytest.approx(expected, abs=1e-4)


def test_candidate_ranker_total_score_rounds_to_four_decimal_places():
    ranker = BrollCandidateRanker()
    beat = _build_beat("alpha beta gamma")

    ranked = ranker.rank(
        beat,
        ("alpha beta gamma",),
        [
            _build_candidate(
                "landscape-cand",
                "alpha",
                "https://cdn.example/clip.mp4",
                (),
                5000,
                320,
                240,
                "landscape",
                "/tmp/lc.mp4",
            )
        ],
    )

    c = ranked[0]
    assert c.semantic_match == 0.3333
    assert c.total_score == 0.5273


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

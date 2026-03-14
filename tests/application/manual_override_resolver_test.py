from src.application.broll.manual_override_resolver import ManualBrollOverrideResolver
from src.domain.broll_models import BeatScoreBreakdown, ImpactBeat
from src.domain.manual_broll_overrides import ManualBrollOverride
from src.domain.subtitle_models import ProjectedCue, ProjectedWord, SubtitleTimeline


def test_manual_override_resolver_matches_detected_beat_and_builds_manual_candidate(tmp_path):
    asset = tmp_path / "confusing.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short_2",
        anchor_text="so confusing",
        asset_path=str(asset),
        mode="full_frame_cutaway",
        priority=250,
    )
    detected_beat = _build_detected_beat("It's so confusing with all those negatives.", 2400, 3920, total=0.32)

    selections = resolver.resolve(
        short_id="short_2",
        timeline=_build_confusing_timeline(),
        detected_beats=[detected_beat],
        overrides=(override,),
    )

    assert len(selections) == 1
    selection = selections[0]
    assert selection.beat.beat_id == detected_beat.beat_id
    assert selection.forced_mode == "full_frame_cutaway"
    assert selection.selection_source == "manual_override"
    assert selection.candidates[0].discovery_source == "manual_override"
    assert selection.candidates[0].local_path == str(asset)


def test_manual_override_resolver_creates_synthetic_beat_when_detector_misses_phrase(tmp_path):
    asset = tmp_path / "job-interview.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short_5",
        anchor_text="job interview",
        asset_path=str(asset),
        mode="full_frame_cutaway",
    )

    selections = resolver.resolve(
        short_id="short_5",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(override,),
    )

    assert len(selections) == 1
    selection = selections[0]
    assert selection.beat.beat_id == "manual-beat-0001"
    assert selection.beat.text == "job interview"
    assert selection.beat.start_ms == 3000
    assert selection.beat.end_ms == 3900
    assert selection.candidates[0].asset_type == "video"
    assert selection.candidates[0].total_score == 1.0


def test_manual_override_resolver_prefers_highest_priority_override_for_same_detected_beat(tmp_path):
    asset = tmp_path / "confusing.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    high_priority_override = ManualBrollOverride(
        short_id="short_2",
        anchor_text="so confusing",
        asset_path=str(asset),
        mode="full_frame_cutaway",
        priority=250,
    )
    low_priority_override = ManualBrollOverride(
        short_id="short_2",
        anchor_text="so confusing",
        asset_path=str(asset),
        mode="overlay",
        priority=100,
    )
    detected_beats = [
        _build_detected_beat("This is so confusing today.", 2000, 3600, total=0.42),
        _build_detected_beat("It stays so confusing.", 2300, 2900, total=0.36),
    ]

    selections = resolver.resolve(
        short_id="short_2",
        timeline=_build_confusing_timeline(),
        detected_beats=detected_beats,
        overrides=(low_priority_override, high_priority_override),
    )

    assert len(selections) == 1
    selection = selections[0]
    assert selection.beat.start_ms == 2300
    assert selection.beat.end_ms == 2900
    assert selection.priority == 250
    assert selection.forced_mode == "full_frame_cutaway"


def test_manual_override_resolver_builds_square_image_candidate_from_cue_text_when_words_do_not_match(tmp_path):
    asset = tmp_path / "still-frame.png"
    asset.write_bytes(b"image")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short_7",
        anchor_text="already nervous",
        asset_path=str(asset),
        mode="full_frame_cutaway",
    )
    timeline = SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=14000,
        cues=(
            ProjectedCue(
                cue_id="cue-7",
                speaker="Speaker 1",
                original_text="I walked in already nervous about the meeting.",
                start_ms=4000,
                end_ms=5200,
                timing_mode="reconciled_asr",
                quality_score=0.91,
                words=(),
            ),
        ),
        segments=(),
        quality_score=0.91,
    )

    selections = resolver.resolve(
        short_id="short_7",
        timeline=timeline,
        detected_beats=[],
        overrides=(override,),
    )

    assert len(selections) == 1
    selection = selections[0]
    assert selection.beat.text == "already nervous"
    assert selection.beat.word_confidence_avg == 0.0
    assert selection.candidates[0].asset_type == "image"
    assert selection.candidates[0].orientation == "square"
    assert selection.candidates[0].width == 1080
    assert selection.candidates[0].height == 1080


def test_manual_override_resolver_ignores_override_without_normalized_anchor(tmp_path):
    asset = tmp_path / "clip.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = ManualBrollOverride(
        short_id="short_8",
        anchor_text="!!!",
        asset_path=str(asset),
        mode="full_frame_cutaway",
    )

    selections = resolver.resolve(
        short_id="short_8",
        timeline=_build_confusing_timeline(),
        detected_beats=[],
        overrides=(override,),
    )

    assert selections == ()


def test_manual_override_resolver_ignores_inactive_and_foreign_short_overrides(tmp_path):
    asset = tmp_path / "job_interview.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()

    selections = resolver.resolve(
        short_id="short_target",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(
            _build_override("other_short", "job interview", str(asset), priority=300),
            _build_override("short_target", "job interview", str(asset), priority=250, active=False),
            _build_override("short_target", "job interview", str(asset), priority=100),
        ),
    )

    assert len(selections) == 1
    assert selections[0].priority == 100
    assert selections[0].beat.beat_id == "manual-beat-0001"


def test_manual_override_resolver_continues_after_invalid_asset_and_unmatched_override(tmp_path):
    asset = tmp_path / "job_interview.mp4"
    asset.write_bytes(b"video")
    missing_asset = tmp_path / "missing.mp4"
    resolver = ManualBrollOverrideResolver()

    selections = resolver.resolve(
        short_id="short_9",
        timeline=_build_job_interview_timeline(),
        detected_beats=[],
        overrides=(
            _build_override("short_9", "job interview", str(missing_asset), priority=300),
            _build_override("short_9", "no match here", str(asset), priority=200),
            _build_override("short_9", "job interview", str(asset), priority=100),
        ),
    )

    assert len(selections) == 1
    assert selections[0].candidates[0].asset_url == str(asset)
    assert selections[0].beat.text == "job interview"


def test_manual_override_resolver_assigns_incremental_ids_to_multiple_synthetic_beats(tmp_path):
    asset_one = tmp_path / "job_interview.mp4"
    asset_one.write_bytes(b"video")
    asset_two = tmp_path / "already_nervous.mp4"
    asset_two.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()

    selections = resolver.resolve(
        short_id="short_10",
        timeline=_build_multi_anchor_timeline(),
        detected_beats=[],
        overrides=(
            _build_override("short_10", "job interview", str(asset_one), priority=200),
            _build_override("short_10", "already nervous", str(asset_two), priority=100),
        ),
    )

    assert [selection.beat.beat_id for selection in selections] == ["manual-beat-0001", "manual-beat-0002"]
    assert [selection.beat.text for selection in selections] == ["job interview", "already nervous."]


def test_manual_override_resolver_keeps_later_distinct_selection_after_duplicate_beat(tmp_path):
    duplicate_asset = tmp_path / "job_interview.mp4"
    duplicate_asset.write_bytes(b"video")
    distinct_asset = tmp_path / "already_nervous.mp4"
    distinct_asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    detected_beat = _build_detected_beat("The job interview started.", 3000, 3900, total=0.5)

    selections = resolver.resolve(
        short_id="short_11",
        timeline=_build_multi_anchor_timeline(),
        detected_beats=[detected_beat],
        overrides=(
            _build_override("short_11", "job interview", str(duplicate_asset), priority=300),
            _build_override("short_11", "job interview", str(duplicate_asset), priority=200),
            _build_override("short_11", "already nervous", str(distinct_asset), priority=100),
        ),
    )

    assert len(selections) == 2
    assert [selection.beat.beat_id for selection in selections] == ["beat-0001", "manual-beat-0001"]


def test_manual_override_resolver_ignores_unrelated_shorter_detected_beat(tmp_path):
    asset = tmp_path / "confusing.mp4"
    asset.write_bytes(b"video")
    resolver = ManualBrollOverrideResolver()
    override = _build_override("short_12", "so confusing", str(asset), priority=250)
    detected_beats = [
        _build_detected_beat("completely unrelated", 2100, 2300, total=0.6),
        _build_detected_beat("This stays so confusing today.", 2400, 3920, total=0.4),
    ]

    selections = resolver.resolve(
        short_id="short_12",
        timeline=_build_confusing_timeline(),
        detected_beats=detected_beats,
        overrides=(override,),
    )

    assert len(selections) == 1
    assert selections[0].beat.text == "This stays so confusing today."
    assert selections[0].beat.start_ms == 2400


def _build_detected_beat(text: str, start_ms: int, end_ms: int, total: float) -> ImpactBeat:
    return ImpactBeat(
        beat_id="beat-0001",
        text=text,
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=end_ms - start_ms,
        timing_mode="reconciled_asr",
        word_confidence_avg=0.92,
        cue_quality_score=0.94,
        scores=BeatScoreBreakdown(
            total=total,
            visualizability=0.4,
            emotional_load=0.5,
            contrast=0.4,
            narrative_turn=0.4,
            verbal_force=0.5,
            duration_fit=0.9,
            timing_confidence=0.95,
            semantic_salience=0.5,
        ),
        reasons=("test beat",),
    )


def _build_confusing_timeline() -> SubtitleTimeline:
    return SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=12000,
        cues=(
            ProjectedCue(
                cue_id="cue-1",
                speaker="Speaker 1",
                original_text="It's so confusing with all those negatives.",
                start_ms=2000,
                end_ms=3920,
                timing_mode="reconciled_asr",
                quality_score=0.96,
                words=(
                    ProjectedWord("It's", 2000, 2280, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("so", 2280, 2560, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("confusing", 2560, 2840, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("with", 2840, 3120, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("all", 3120, 3400, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("those", 3400, 3680, 0.94, "reconciled", "exact_normalized"),
                    ProjectedWord("negatives.", 3680, 3920, 0.94, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.96,
    )


def _build_job_interview_timeline() -> SubtitleTimeline:
    return SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=14000,
        cues=(
            ProjectedCue(
                cue_id="cue-2",
                speaker="Speaker 1",
                original_text="I walked into the job interview already nervous.",
                start_ms=2000,
                end_ms=5200,
                timing_mode="reconciled_asr",
                quality_score=0.93,
                words=(
                    ProjectedWord("I", 2000, 2200, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("walked", 2200, 2500, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("into", 2500, 2800, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("the", 2800, 3000, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("job", 3000, 3400, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("interview", 3400, 3900, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("already", 3900, 4400, 0.9, "reconciled", "exact_normalized"),
                    ProjectedWord("nervous.", 4400, 5200, 0.9, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.93,
    )


def _build_multi_anchor_timeline() -> SubtitleTimeline:
    return SubtitleTimeline(
        interval_start_ms=0,
        interval_end_ms=14000,
        cues=(
            _build_job_interview_timeline().cues[0],
            ProjectedCue(
                cue_id="cue-3",
                speaker="Speaker 1",
                original_text="I walked in already nervous about the meeting.",
                start_ms=6000,
                end_ms=7600,
                timing_mode="reconciled_asr",
                quality_score=0.88,
                words=(
                    ProjectedWord("I", 6000, 6200, 0.87, "reconciled", "exact_normalized"),
                    ProjectedWord("walked", 6200, 6500, 0.87, "reconciled", "exact_normalized"),
                    ProjectedWord("in", 6500, 6700, 0.87, "reconciled", "exact_normalized"),
                    ProjectedWord("already", 6700, 7100, 0.87, "reconciled", "exact_normalized"),
                    ProjectedWord("nervous", 7100, 7600, 0.87, "reconciled", "exact_normalized"),
                ),
            ),
        ),
        segments=(),
        quality_score=0.9,
    )


def _build_override(
    short_id: str,
    anchor_text: str,
    asset_path: str,
    *,
    priority: int = 100,
    active: bool = True,
) -> ManualBrollOverride:
    return ManualBrollOverride(
        short_id=short_id,
        anchor_text=anchor_text,
        asset_path=asset_path,
        mode="full_frame_cutaway",
        priority=priority,
        active=active,
    )

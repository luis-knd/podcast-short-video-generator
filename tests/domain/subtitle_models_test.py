from dataclasses import FrozenInstanceError

import pytest

from src.domain.subtitle_models import AlignedWord, ReconciledCue, ReconciledWord, SubtitleCue


def test_subtitle_model_dict_roundtrip_preserves_values():
    aligned_word = AlignedWord(
        text="Hello",
        normalized_text="hello",
        start_ms=100,
        end_ms=250,
        confidence=0.9,
    )
    reconciled_word = ReconciledWord(
        display_text="Hello,",
        start_ms=100,
        end_ms=250,
        confidence=0.9,
        source="reconciled",
        match_method="exact_normalized",
        fallback_used=False,
    )

    assert AlignedWord.from_dict(aligned_word.to_dict()) == aligned_word
    assert ReconciledWord.from_dict(reconciled_word.to_dict()) == reconciled_word


def test_reconciled_cue_uses_source_bounds_without_words_and_filters_invalid_payloads():
    cue = ReconciledCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        original_text="",
        source_cue_start_ms=1000,
        source_cue_end_ms=1500,
        timing_mode="approximate",
        quality_score=0.0,
        words=(),
    )

    assert cue.start_ms == 1000
    assert cue.end_ms == 1500
    assert cue.to_dict()["words"] == []

    restored = ReconciledCue.from_dict(
        {
            "cue_id": "cue-2",
            "speaker": "Speaker 2",
            "original_text": "Hello world",
            "source_cue_start_ms": 2000,
            "source_cue_end_ms": 2600,
            "timing_mode": "reconciled_asr",
            "quality_score": 0.8,
            "words": "invalid",
        }
    )

    assert restored.words == ()
    assert restored.start_ms == 2000
    assert restored.end_ms == 2600


def test_subtitle_models_are_frozen_and_apply_default_dict_values():
    cue = SubtitleCue(
        cue_id="cue-1",
        speaker="Speaker 1",
        text="hello",
        start_ms=0,
        end_ms=100,
    )
    aligned_word = AlignedWord(
        text="hello",
        normalized_text="hello",
        start_ms=0,
        end_ms=100,
    )

    with pytest.raises(FrozenInstanceError):
        cue.text = "changed"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        aligned_word.confidence = 1.0  # type: ignore[misc]

    default_aligned = AlignedWord.from_dict({})
    assert default_aligned.text == ""
    assert default_aligned.normalized_text == ""
    assert default_aligned.start_ms == 0
    assert default_aligned.end_ms == 0
    assert default_aligned.confidence == 0.0

    default_reconciled_word = ReconciledWord.from_dict({})
    assert default_reconciled_word.display_text == ""
    assert default_reconciled_word.start_ms == 0
    assert default_reconciled_word.end_ms == 0
    assert default_reconciled_word.confidence == 0.0
    assert default_reconciled_word.source == "approximate"
    assert default_reconciled_word.match_method == "approximate"
    assert default_reconciled_word.fallback_used is False

    default_reconciled_cue = ReconciledCue.from_dict({})
    assert default_reconciled_cue.cue_id == ""
    assert default_reconciled_cue.speaker == "Speaker Unknown"
    assert default_reconciled_cue.original_text == ""
    assert default_reconciled_cue.source_cue_start_ms == 0
    assert default_reconciled_cue.source_cue_end_ms == 0
    assert default_reconciled_cue.timing_mode == "approximate"
    assert default_reconciled_cue.quality_score == 0.0

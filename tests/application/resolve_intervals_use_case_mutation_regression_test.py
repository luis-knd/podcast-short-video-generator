import pytest

from src.application.use_cases import ResolveIntervalsUseCase
from src.domain.exceptions import ShortGeneratorError


class _GeneratorStub:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload if payload is not None else []
        self.error = error
        self.calls: list[str] = []

    def generate(self, subtitles_filepath: str):
        self.calls.append(subtitles_filepath)
        if self.error is not None:
            raise self.error
        return self.payload


def test_resolve_intervals_use_case_default_force_auto_is_false_and_manual_payload_wins():
    generator = _GeneratorStub(payload=[{"time": "00:10:00,000 - 00:10:20,000"}])
    use_case = ResolveIntervalsUseCase(interval_generator=generator)

    resolved = use_case.execute(
        subtitles_filepath="captions.srt",
        manual_intervals_json=[{"time": "00:00:10,000 - 00:00:20,000"}],
    )

    assert resolved.intervals_json == [{"time": "00:00:10,000 - 00:00:20,000"}]
    assert resolved.source == "manual"
    assert resolved.warning_message is None
    assert generator.calls == []


def test_resolve_intervals_use_case_returns_exact_warning_when_auto_generation_fails_and_manual_exists():
    generator = _GeneratorStub(error=ShortGeneratorError("boom"))
    use_case = ResolveIntervalsUseCase(interval_generator=generator)

    resolved = use_case.execute(
        subtitles_filepath="captions.srt",
        manual_intervals_json=[{"time": "00:00:10,000 - 00:00:20,000"}],
        force_auto_generation=True,
    )

    assert resolved.intervals_json == [{"time": "00:00:10,000 - 00:00:20,000"}]
    assert resolved.source == "manual"
    assert resolved.warning_message == (
        "Warning: Automatic interval generation failed; using existing intervals file instead. Reason: boom"
    )
    assert generator.calls == ["captions.srt"]


def test_resolve_intervals_use_case_returns_exact_warning_when_auto_generation_produces_no_candidates():
    generator = _GeneratorStub(payload=[])
    use_case = ResolveIntervalsUseCase(interval_generator=generator)

    resolved = use_case.execute(
        subtitles_filepath="captions.srt",
        manual_intervals_json=[{"time": "00:00:10,000 - 00:00:20,000"}],
        force_auto_generation=True,
    )

    assert resolved.intervals_json == [{"time": "00:00:10,000 - 00:00:20,000"}]
    assert resolved.source == "manual"
    assert resolved.warning_message == (
        "Warning: Automatic interval generation produced no candidates; using existing intervals file instead."
    )


def test_resolve_intervals_use_case_raises_exact_error_when_auto_generation_produces_no_candidates_without_manual():
    generator = _GeneratorStub(payload=[])
    use_case = ResolveIntervalsUseCase(interval_generator=generator)

    with pytest.raises(ShortGeneratorError) as exc_info:
        use_case.execute(
            subtitles_filepath="captions.srt",
            manual_intervals_json=None,
            force_auto_generation=True,
        )

    assert str(exc_info.value) == "Automatic interval generation produced no candidates"

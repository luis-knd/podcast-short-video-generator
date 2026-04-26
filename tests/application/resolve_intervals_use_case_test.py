from unittest.mock import Mock

import pytest

from src.application.use_cases import ResolvedIntervals, ResolveIntervalsUseCase
from src.domain.exceptions import ShortGeneratorError
from src.domain.ports import ISubtitleIntervalGenerator

_SUBTITLES_FILEPATH = "inputs/video.srt"


def test_resolve_intervals_use_case_prefers_manual_intervals_when_auto_is_not_forced():
    interval_generator = Mock(spec=ISubtitleIntervalGenerator)
    use_case = ResolveIntervalsUseCase(interval_generator=interval_generator)
    manual_intervals = [{"time": "00:00:10,000 - 00:00:30,000"}]

    resolved = use_case.execute(
        subtitles_filepath=_SUBTITLES_FILEPATH,
        manual_intervals_json=manual_intervals,
        force_auto_generation=False,
    )

    assert resolved == ResolvedIntervals(
        intervals_json=manual_intervals,
        source="manual",
        warning_message=None,
    )
    interval_generator.generate.assert_not_called()


def test_resolve_intervals_use_case_generates_intervals_when_manual_file_is_missing():
    interval_generator = Mock(spec=ISubtitleIntervalGenerator)
    interval_generator.generate.return_value = [{"time": "00:00:40,000 - 00:01:02,000"}]
    use_case = ResolveIntervalsUseCase(interval_generator=interval_generator)

    resolved = use_case.execute(
        subtitles_filepath=_SUBTITLES_FILEPATH,
        manual_intervals_json=None,
        force_auto_generation=False,
    )

    assert resolved == ResolvedIntervals(
        intervals_json=[{"time": "00:00:40,000 - 00:01:02,000"}],
        source="auto",
        warning_message=None,
    )
    interval_generator.generate.assert_called_once_with(_SUBTITLES_FILEPATH)


def test_resolve_intervals_use_case_falls_back_to_manual_intervals_when_auto_generation_fails():
    interval_generator = Mock(spec=ISubtitleIntervalGenerator)
    interval_generator.generate.side_effect = ShortGeneratorError("boom")
    use_case = ResolveIntervalsUseCase(interval_generator=interval_generator)
    manual_intervals = [{"time": "00:01:10,000 - 00:01:34,000"}]

    resolved = use_case.execute(
        subtitles_filepath=_SUBTITLES_FILEPATH,
        manual_intervals_json=manual_intervals,
        force_auto_generation=True,
    )

    assert resolved.intervals_json == manual_intervals
    assert resolved.source == "manual"
    assert resolved.warning_message is not None and "boom" in resolved.warning_message
    interval_generator.generate.assert_called_once_with(_SUBTITLES_FILEPATH)


def test_resolve_intervals_use_case_raises_when_auto_generation_fails_without_manual_fallback():
    interval_generator = Mock(spec=ISubtitleIntervalGenerator)
    interval_generator.generate.side_effect = OSError("cannot parse")
    use_case = ResolveIntervalsUseCase(interval_generator=interval_generator)

    with pytest.raises(ShortGeneratorError, match="cannot parse"):
        use_case.execute(
            subtitles_filepath=_SUBTITLES_FILEPATH,
            manual_intervals_json=None,
            force_auto_generation=False,
        )

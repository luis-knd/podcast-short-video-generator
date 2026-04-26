from dataclasses import dataclass
from socket import timeout as SocketTimeout
from typing import cast

import pytest

from src.domain.ports import ISubtitleIntervalGenerator
from src.domain.subtitle_models import SubtitleCue
from src.infrastructure.subtitles.llm_interval_generator import (
    GeminiIntervalSelectionClient,
    LlmSubtitleIntervalGenerator,
)
from src.infrastructure.subtitles.parser import SubtitleParser

EPISODE_SRT = "episode.srt"
INTERVAL_24_SECONDS = {"time": "00:00:00,000 - 00:00:24,000"}
SPEAKER_1 = "Speaker 1"


@dataclass
class _FakeHttpResponse:
    payload: bytes

    def read(self) -> bytes:
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FallbackGenerator:
    def __init__(self, payload: list[dict[str, str]]):
        self.payload = payload
        self.calls: list[str] = []

    def generate(self, subtitles_filepath: str) -> list[dict[str, str]]:
        self.calls.append(subtitles_filepath)
        return self.payload


class _ParserStub:
    def __init__(self, cues: list[SubtitleCue]):
        self.cues = cues
        self.calls: list[str] = []

    def parse(self, subtitles_filepath: str) -> list[SubtitleCue]:
        self.calls.append(subtitles_filepath)
        return self.cues


class _LlmClientStub:
    def __init__(self, segments: list[dict[str, str]] | None = None, error: Exception | None = None, model=None):
        self.segments = segments or []
        self.error = error
        self.model = model

    def select_segments(self, cues, target_count: int, min_duration_ms: int, max_duration_ms: int):
        del cues, target_count, min_duration_ms, max_duration_ms
        if self.error is not None:
            raise self.error
        return self.segments


def _sample_cues() -> list[SubtitleCue]:
    return [
        SubtitleCue("cue-1", SPEAKER_1, "Hook question", 0, 8_000),
        SubtitleCue("cue-2", SPEAKER_1, "Problem setup", 8_000, 16_000),
        SubtitleCue("cue-3", SPEAKER_1, "Safer swap", 16_000, 24_000),
        SubtitleCue("cue-4", SPEAKER_1, "Extra context", 24_000, 32_000),
        SubtitleCue("cue-5", SPEAKER_1, "Second hook", 32_000, 40_000),
        SubtitleCue("cue-6", SPEAKER_1, "Second payoff", 40_000, 48_000),
    ]


EXPECTED_PROMPT = (
    "# CONTEXT\n"
    "You are selecting the best moments from a YouTube podcast transcript to create shorts that maximize CTR, "
    "virality, retention and stop-scroll potential.\n"
    "The downstream application will generate the short videos from a recortes.json file.\n\n"
    "# TASK\n"
    "Select only the moments that feel like complete, high-value clips.\n"
    "Prioritize segments that:\n"
    "- open with curiosity, conflict, surprise, practical value or emotional tension\n"
    "- end on a complete thought, payoff, punchline, resolution or memorable line\n"
    "- can stand alone without requiring too much missing context\n"
    "- are likely to improve CTR, viralidad and stop-scroll\n"
    "Avoid segments that are welcome lines, transitions, sponsor/CTA boilerplate, "
    "weak setup, or mid-thought endings.\n\n"
    "# OUTPUT CONTRACT\n"
    "Return exactly one JSON object with this schema and no extra prose:\n"
    '{"segments": [{"start_cue_id": "cue-10", "end_cue_id": "cue-16"}]}\n'
    "Select up to 2 segments. Preferred duration range: 18000-42000 ms.\n"
    "Use only cue ids that exist below. The final result will be converted into recortes.json.\n\n"
    "# TRANSCRIPT CUES\n"
    "cue-1 | 00:00:00,000 | 00:00:05,000 | Hook line\n"
    "cue-2 | 00:00:05,000 | 00:00:10,000 | Payoff line"
)


def test_gemini_interval_selection_client_initializes_with_sanitized_defaults():
    def transport(request, timeout):
        return (request, timeout)

    client = GeminiIntervalSelectionClient(
        api_key="  test-key  ",
        model="   ",
        retry_attempts=0,
        transport=transport,
    )

    assert client.api_key == "test-key"
    assert client.model == "gemini-2.5-flash"
    assert client.timeout_seconds == pytest.approx(20.0)
    assert client.temperature == pytest.approx(0.2)
    assert client.retry_attempts == 1
    assert client.transport is transport


def test_gemini_interval_selection_client_builds_exact_prompt_headers_and_request_body():
    client = GeminiIntervalSelectionClient(api_key="test-key", model="gemini-test", temperature=0.35)
    cues = [
        {"cue_id": "cue-1", "start": "00:00:00,000", "end": "00:00:05,000", "text": "Hook line"},
        {"cue_id": "cue-2", "start": "00:00:05,000", "end": "00:00:10,000", "text": "Payoff line"},
    ]

    prompt = client._build_prompt(cues, target_count=2, min_duration_ms=18_000, max_duration_ms=42_000)
    body = client._build_request_body(cues, target_count=2, min_duration_ms=18_000, max_duration_ms=42_000)

    assert prompt == EXPECTED_PROMPT
    assert client._request_headers() == {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "podcast-short-video-generator/1.0",
    }
    assert body.decode("utf-8") == (
        '{"contents": [{"parts": [{"text": "'
        + EXPECTED_PROMPT.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        + '"}]}], "generationConfig": {"temperature": 0.35, "responseMimeType": "application/json"}}'
    )


def test_gemini_interval_selection_client_normalizes_subtitle_cues_and_raises_after_retries_exhaust():
    attempts = {"count": 0}

    def _timeout_transport(request, timeout: float):
        del request, timeout
        attempts["count"] += 1
        raise SocketTimeout("timed out")

    client = GeminiIntervalSelectionClient(api_key="test-key", retry_attempts=3, transport=_timeout_transport)
    cue = SubtitleCue("cue-9", SPEAKER_1, "  Trim me  ", 12_345, 23_456)

    normalized = client._normalize_cue(cue)

    assert normalized == {
        "cue_id": "cue-9",
        "start": "00:00:12,345",
        "end": "00:00:23,456",
        "text": "Trim me",
    }
    assert client._compact_cue_line(cue) == "cue-9 | 00:00:12,345 | 00:00:23,456 | Trim me"

    try:
        client.select_segments([cue], target_count=1, min_duration_ms=18_000, max_duration_ms=42_000)
    except SocketTimeout as exc:
        assert str(exc) == "timed out"
    else:
        raise AssertionError("Expected SocketTimeout after exhausting retries")

    assert attempts["count"] == 3


def test_llm_interval_generator_returns_empty_list_when_parser_has_no_cues():
    fallback = _FallbackGenerator(payload=[INTERVAL_24_SECONDS])
    parser = _ParserStub(cues=[])
    generator = LlmSubtitleIntervalGenerator(
        llm_client=cast(
            GeminiIntervalSelectionClient, _LlmClientStub(segments=[{"start_cue_id": "cue-1", "end_cue_id": "cue-3"}])
        ),
        fallback_generator=cast(ISubtitleIntervalGenerator, fallback),
        subtitle_parser=cast(SubtitleParser, parser),
    )

    intervals = generator.generate(EPISODE_SRT)

    assert intervals == []
    assert parser.calls == [EPISODE_SRT]
    assert fallback.calls == []
    assert generator.last_generation_message is None


def test_llm_interval_generator_filters_invalid_segments_and_emits_exact_success_message():
    generator = LlmSubtitleIntervalGenerator(
        llm_client=cast(
            GeminiIntervalSelectionClient,
            _LlmClientStub(
                segments=[
                    {"start_cue_id": "cue-x", "end_cue_id": "cue-3"},
                    {"start_cue_id": "cue-4", "end_cue_id": "cue-2"},
                    {"start_cue_id": "cue-1", "end_cue_id": "cue-3"},
                    {"start_cue_id": "cue-2", "end_cue_id": "cue-4"},
                    {"start_cue_id": "cue-4", "end_cue_id": "cue-6"},
                    {"start_cue_id": "cue-1", "end_cue_id": "cue-6"},
                ],
                model="gemini-9",
            ),
        ),
        fallback_generator=cast(ISubtitleIntervalGenerator, _FallbackGenerator(payload=[])),
        subtitle_parser=cast(SubtitleParser, _ParserStub(cues=_sample_cues())),
        target_count=2,
        min_duration_ms=18_000,
        max_duration_ms=30_000,
        max_overlap_ratio=0.65,
    )

    intervals = generator.generate(EPISODE_SRT)

    assert intervals == [
        INTERVAL_24_SECONDS,
        {"time": "00:00:24,000 - 00:00:48,000"},
    ]
    assert generator.last_generation_message == "Gemini interval selection succeeded with model gemini-9."


def test_llm_interval_generator_falls_back_with_exact_warning_when_segments_are_not_usable():
    fallback = _FallbackGenerator(payload=[{"time": "00:00:08,000 - 00:00:32,000"}])
    generator = LlmSubtitleIntervalGenerator(
        llm_client=cast(
            GeminiIntervalSelectionClient, _LlmClientStub(segments=[{"start_cue_id": "cue-x", "end_cue_id": "cue-y"}])
        ),
        fallback_generator=cast(ISubtitleIntervalGenerator, fallback),
        subtitle_parser=cast(SubtitleParser, _ParserStub(cues=_sample_cues())),
        target_count=2,
        min_duration_ms=18_000,
        max_duration_ms=30_000,
    )

    intervals = generator.generate(EPISODE_SRT)

    assert intervals == [{"time": "00:00:08,000 - 00:00:32,000"}]
    assert fallback.calls == [EPISODE_SRT]
    assert generator.last_generation_message == (
        "Warning: Gemini returned no valid cue-bounded segments; using heuristic interval selection instead."
    )


def test_llm_interval_generator_uses_configured_model_placeholder_when_client_has_no_model_attr():
    class _ModelLessClient:
        @staticmethod
        def select_segments(cues, target_count: int, min_duration_ms: int, max_duration_ms: int):
            del cues, target_count, min_duration_ms, max_duration_ms
            return [{"start_cue_id": "cue-1", "end_cue_id": "cue-3"}]

    generator = LlmSubtitleIntervalGenerator(
        llm_client=cast(GeminiIntervalSelectionClient, _ModelLessClient()),
        fallback_generator=cast(ISubtitleIntervalGenerator, _FallbackGenerator(payload=[])),
        subtitle_parser=cast(SubtitleParser, _ParserStub(cues=_sample_cues())),
        target_count=2,
        min_duration_ms=18_000,
        max_duration_ms=30_000,
    )

    intervals = generator.generate(EPISODE_SRT)

    assert intervals == [INTERVAL_24_SECONDS]
    assert generator.last_generation_message == "Gemini interval selection succeeded with model configured-model."


def test_llm_interval_generator_overlap_ratio_and_format_ms_cover_edge_cases():
    assert LlmSubtitleIntervalGenerator._overlap_ratio((0, 24_000), (24_000, 48_000)) == pytest.approx(0.0)
    assert LlmSubtitleIntervalGenerator._overlap_ratio((0, 24_000), (8_000, 32_000)) == pytest.approx(2 / 3)
    assert LlmSubtitleIntervalGenerator._overlap_ratio((0, 0), (0, 24_000)) == pytest.approx(0.0)
    assert LlmSubtitleIntervalGenerator.format_ms(3_723_456) == "01:02:03,456"

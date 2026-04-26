from dataclasses import dataclass

from src.infrastructure.subtitles.llm_interval_generator import (
    GeminiIntervalSelectionClient,
    LlmSubtitleIntervalGenerator,
)


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


class _StubLlmClient:
    def __init__(self, segments: list[dict[str, str]] | None = None, error: Exception | None = None):
        self.segments = segments or []
        self.error = error

    def select_segments(self, cues, target_count: int, min_duration_ms: int, max_duration_ms: int):
        del cues, target_count, min_duration_ms, max_duration_ms
        if self.error is not None:
            raise self.error
        return self.segments


def test_llm_interval_generator_uses_valid_llm_segments_and_keeps_cue_boundaries(tmp_path):
    srt_file = tmp_path / "episode.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:06,000\n"
        "You are making this mistake in English.\n"
        "\n"
        "2\n"
        "00:00:06,000 --> 00:00:12,000\n"
        "Here is why it hurts your credibility at work.\n"
        "\n"
        "3\n"
        "00:00:12,000 --> 00:00:18,000\n"
        "Instead, use this safer phrase with your manager.\n"
        "\n"
        "4\n"
        "00:00:18,000 --> 00:00:24,000\n"
        "That way you sound clear, calm and professional.\n",
        encoding="utf-8",
    )
    fallback_generator = _FallbackGenerator(payload=[{"time": "00:00:00,000 - 00:00:24,000"}])
    generator = LlmSubtitleIntervalGenerator(
        llm_client=_StubLlmClient(segments=[{"start_cue_id": "cue-1", "end_cue_id": "cue-4"}]),
        fallback_generator=fallback_generator,
        target_count=3,
        min_duration_ms=18_000,
        max_duration_ms=30_000,
    )

    intervals = generator.generate(str(srt_file))

    assert intervals == [{"time": "00:00:00,000 - 00:00:24,000"}]
    assert fallback_generator.calls == []


def test_llm_interval_generator_falls_back_when_llm_response_is_invalid(tmp_path):
    srt_file = tmp_path / "episode.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:10,000\n"
        "Welcome back everyone.\n"
        "\n"
        "2\n"
        "00:00:10,000 --> 00:00:22,000\n"
        "Why does this phrase make you sound rude?\n"
        "\n"
        "3\n"
        "00:00:22,000 --> 00:00:34,000\n"
        "Because native speakers hear it as a direct attack.\n",
        encoding="utf-8",
    )
    fallback_payload = [{"time": "00:00:10,000 - 00:00:34,000"}]
    fallback_generator = _FallbackGenerator(payload=fallback_payload)
    generator = LlmSubtitleIntervalGenerator(
        llm_client=_StubLlmClient(segments=[{"start_cue_id": "cue-9", "end_cue_id": "cue-10"}]),
        fallback_generator=fallback_generator,
        target_count=3,
        min_duration_ms=18_000,
        max_duration_ms=35_000,
    )

    intervals = generator.generate(str(srt_file))

    assert intervals == fallback_payload
    assert fallback_generator.calls == [str(srt_file)]


def test_gemini_interval_selection_client_parses_json_response_from_transport():
    captured = {}

    def _transport(request, timeout: float):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = request.data.decode("utf-8")
        response_payload = (
            b'{"candidates":[{"content":{"parts":['
            b'{"text":"{\\"segments\\":[{\\"start_cue_id\\":\\"cue-2\\",\\"end_cue_id\\":\\"cue-5\\"}]}"}'
            b"]}}]}"
        )
        return _FakeHttpResponse(payload=response_payload)

    client = GeminiIntervalSelectionClient(
        api_key="test-key",
        model="gemini-test",
        timeout_seconds=9,
        transport=_transport,
    )

    segments = client.select_segments(
        cues=[
            {"cue_id": "cue-1", "start": "00:00:00,000", "end": "00:00:04,000", "text": "Hook"},
            {"cue_id": "cue-2", "start": "00:00:04,000", "end": "00:00:08,000", "text": "Problem"},
        ],
        target_count=4,
        min_duration_ms=18_000,
        max_duration_ms=38_000,
    )

    assert segments == [{"start_cue_id": "cue-2", "end_cue_id": "cue-5"}]
    assert "gemini-test:generateContent" in captured["url"]
    assert captured["timeout"] == 9
    assert '"responseMimeType": "application/json"' in captured["body"]


def test_llm_interval_generator_falls_back_when_gemini_payload_shape_is_invalid(tmp_path):
    srt_file = tmp_path / "episode.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:10,000\n"
        "Why does this fail in real life?\n"
        "\n"
        "2\n"
        "00:00:10,000 --> 00:00:22,000\n"
        "Because the phrase sounds aggressive outside the song.\n"
        "\n"
        "3\n"
        "00:00:22,000 --> 00:00:34,000\n"
        "Use this calmer alternative instead.\n",
        encoding="utf-8",
    )
    fallback_payload = [{"time": "00:00:10,000 - 00:00:34,000"}]
    fallback_generator = _FallbackGenerator(payload=fallback_payload)
    generator = LlmSubtitleIntervalGenerator(
        llm_client=_StubLlmClient(error=ValueError("Gemini returned an invalid candidate payload")),
        fallback_generator=fallback_generator,
        target_count=3,
        min_duration_ms=18_000,
        max_duration_ms=35_000,
    )

    intervals = generator.generate(str(srt_file))

    assert intervals == fallback_payload
    assert fallback_generator.calls == [str(srt_file)]

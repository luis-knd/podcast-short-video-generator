from socket import timeout as SocketTimeout

from src.infrastructure.subtitles.llm_interval_generator import GeminiIntervalSelectionClient


class _FakeHttpResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_gemini_client_prompt_includes_manual_editorial_criteria():
    client = GeminiIntervalSelectionClient(api_key="test-key", model="gemini-test")

    prompt = client._build_prompt(
        cues=[
            {"cue_id": "cue-1", "start": "00:00:00,000", "end": "00:00:05,000", "text": "Hook line"},
            {"cue_id": "cue-2", "start": "00:00:05,000", "end": "00:00:10,000", "text": "Payoff line"},
        ],
        target_count=5,
        min_duration_ms=18_000,
        max_duration_ms=42_000,
    )

    assert "CTR" in prompt
    assert "stop-scroll" in prompt
    assert "viral" in prompt.lower()
    assert "recortes.json" in prompt
    assert "complete thought" in prompt
    assert "cue-1 | 00:00:00,000 | 00:00:05,000 | Hook line" in prompt


def test_gemini_client_retries_after_timeout():
    attempts = {"count": 0}

    def _transport(request, timeout: float):
        del request, timeout
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise SocketTimeout("timed out")
        return _FakeHttpResponse(
            b'{"candidates":[{"content":{"parts":[{"text":"{\\"segments\\":[{\\"start_cue_id\\":\\"cue-1\\",\\"end_cue_id\\":\\"cue-4\\"}]}"}]}}]}'
        )

    client = GeminiIntervalSelectionClient(
        api_key="test-key",
        model="gemini-test",
        timeout_seconds=5,
        retry_attempts=2,
        transport=_transport,
    )

    segments = client.select_segments(
        cues=[{"cue_id": "cue-1", "start": "00:00:00,000", "end": "00:00:05,000", "text": "Hook line"}],
        target_count=3,
        min_duration_ms=18_000,
        max_duration_ms=42_000,
    )

    assert attempts["count"] == 2
    assert segments == [{"start_cue_id": "cue-1", "end_cue_id": "cue-4"}]

import json
from socket import timeout as SocketTimeout
from urllib.parse import quote
from urllib.request import Request, urlopen

from src.domain.ports import ISubtitleIntervalGenerator
from src.domain.subtitle_models import SubtitleCue
from src.infrastructure.subtitles.parser import SubtitleParser


class GeminiIntervalSelectionClient:
    API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    USER_AGENT = "podcast-short-video-generator/1.0"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout_seconds: float = 20.0,
        temperature: float = 0.2,
        retry_attempts: int = 2,
        transport=None,
    ):
        self.api_key = api_key.strip()
        self.model = model.strip() or "gemini-2.5-flash"
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.retry_attempts = max(1, retry_attempts)
        self.transport = urlopen if transport is None else transport

    def select_segments(
        self,
        cues: list[SubtitleCue] | list[dict[str, str]],
        target_count: int,
        min_duration_ms: int,
        max_duration_ms: int,
    ) -> list[dict[str, str]]:
        request = Request(
            url=self.API_URL_TEMPLATE.format(model=quote(self.model, safe=""), api_key=quote(self.api_key, safe="")),
            data=self._build_request_body(cues, target_count, min_duration_ms, max_duration_ms),
            headers=self._request_headers(),
            method="POST",
        )

        last_error = None
        for _ in range(self.retry_attempts):
            try:
                with self._open_response(request) as response:  # nosec - official Gemini endpoint
                    payload = json.loads(response.read().decode("utf-8"))
                return self._extract_segments(payload)
            except SocketTimeout as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise last_error

        raise ValueError("Gemini request failed without a response")

    def _open_response(self, request: Request):
        return self.transport(request, timeout=self.timeout_seconds)

    def _build_request_body(
        self,
        cues: list[SubtitleCue] | list[dict[str, str]],
        target_count: int,
        min_duration_ms: int,
        max_duration_ms: int,
    ) -> bytes:
        prompt = self._build_prompt(cues, target_count, min_duration_ms, max_duration_ms)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
            },
        }
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def _build_prompt(
        self,
        cues: list[SubtitleCue] | list[dict[str, str]],
        target_count: int,
        min_duration_ms: int,
        max_duration_ms: int,
    ) -> str:
        cue_lines = "\n".join(self._compact_cue_line(cue) for cue in cues)
        return (
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
            f"Select up to {target_count} segments. Preferred duration range: {min_duration_ms}-{max_duration_ms} ms.\n"
            "Use only cue ids that exist below. The final result will be converted into recortes.json.\n\n"
            "# TRANSCRIPT CUES\n"
            f"{cue_lines}"
        )

    @staticmethod
    def _normalize_cue(cue: SubtitleCue | dict[str, str]) -> dict[str, str]:
        if isinstance(cue, dict):
            return {
                "cue_id": str(cue.get("cue_id", "")),
                "start": str(cue.get("start", "")),
                "end": str(cue.get("end", "")),
                "text": str(cue.get("text", "")).strip(),
            }
        return {
            "cue_id": cue.cue_id,
            "start": LlmSubtitleIntervalGenerator.format_ms(cue.start_ms),
            "end": LlmSubtitleIntervalGenerator.format_ms(cue.end_ms),
            "text": cue.text.strip(),
        }

    @classmethod
    def _compact_cue_line(cls, cue: SubtitleCue | dict[str, str]) -> str:
        normalized_cue = cls._normalize_cue(cue)
        return (
            f"{normalized_cue['cue_id']} | {normalized_cue['start']} | {normalized_cue['end']} | "
            f"{normalized_cue['text']}"
        )

    @staticmethod
    def _extract_segments(payload: dict[str, object]) -> list[dict[str, str]]:
        candidates = payload.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Gemini returned no candidates")

        first_candidate = candidates[0]
        if not isinstance(first_candidate, dict):
            raise ValueError("Gemini returned an invalid candidate payload")

        content = first_candidate.get("content", {})
        if not isinstance(content, dict):
            raise ValueError("Gemini returned invalid content metadata")

        parts = content.get("parts", [])
        if not isinstance(parts, list) or not parts:
            raise ValueError("Gemini returned no content parts")

        first_part = parts[0]
        if not isinstance(first_part, dict):
            raise ValueError("Gemini returned an invalid content part")

        text = str(first_part.get("text", "")).strip()
        if not text:
            raise ValueError("Gemini returned empty JSON content")
        parsed = json.loads(text)
        segments = parsed.get("segments", []) if isinstance(parsed, dict) else []
        if not isinstance(segments, list):
            raise ValueError("Gemini response does not contain a valid segments list")
        return [segment for segment in segments if isinstance(segment, dict)]

    def _request_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.USER_AGENT,
        }


class LlmSubtitleIntervalGenerator(ISubtitleIntervalGenerator):
    DEFAULT_TARGET_COUNT = 11
    DEFAULT_MIN_DURATION_MS = 18_000
    DEFAULT_MAX_DURATION_MS = 42_000
    DEFAULT_MAX_OVERLAP_RATIO = 0.65

    def __init__(
        self,
        llm_client: GeminiIntervalSelectionClient,
        fallback_generator: ISubtitleIntervalGenerator,
        subtitle_parser: SubtitleParser | None = None,
        target_count: int | None = None,
        min_duration_ms: int | None = None,
        max_duration_ms: int | None = None,
        max_overlap_ratio: float | None = None,
    ):
        self.llm_client = llm_client
        self.fallback_generator = fallback_generator
        self.subtitle_parser = subtitle_parser or SubtitleParser()
        self.target_count = self.DEFAULT_TARGET_COUNT if target_count is None else target_count
        self.min_duration_ms = self.DEFAULT_MIN_DURATION_MS if min_duration_ms is None else min_duration_ms
        self.max_duration_ms = self.DEFAULT_MAX_DURATION_MS if max_duration_ms is None else max_duration_ms
        self.max_overlap_ratio = self.DEFAULT_MAX_OVERLAP_RATIO if max_overlap_ratio is None else max_overlap_ratio
        self.last_generation_message: str | None = None

    def generate(self, subtitles_filepath: str) -> list[dict[str, str]]:
        self.last_generation_message = None
        cues = self.subtitle_parser.parse(subtitles_filepath)
        if not cues:
            return []
        try:
            segments = self.llm_client.select_segments(
                cues=cues,
                target_count=self.target_count,
                min_duration_ms=self.min_duration_ms,
                max_duration_ms=self.max_duration_ms,
            )
        except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.last_generation_message = (
                f"Warning: Gemini interval selection failed; using heuristic interval selection instead. Reason: {exc}"
            )
            return self.fallback_generator.generate(subtitles_filepath)

        intervals = self._segments_to_intervals(cues, segments)
        if intervals:
            model_name = getattr(self.llm_client, "model", "configured-model")
            self.last_generation_message = f"Gemini interval selection succeeded with model {model_name}."
            return intervals

        self.last_generation_message = (
            "Warning: Gemini returned no valid cue-bounded segments; using heuristic interval selection instead."
        )
        return self.fallback_generator.generate(subtitles_filepath)

    def _segments_to_intervals(
        self,
        cues: list[SubtitleCue],
        segments: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        cue_by_id = {cue.cue_id: cue for cue in cues}
        cue_index = {cue.cue_id: index for index, cue in enumerate(cues)}
        selected_ranges: list[tuple[int, int]] = []
        intervals: list[dict[str, str]] = []

        for segment in segments:
            start_cue_id = str(segment.get("start_cue_id", "")).strip()
            end_cue_id = str(segment.get("end_cue_id", "")).strip()
            if start_cue_id not in cue_by_id or end_cue_id not in cue_by_id:
                continue
            if cue_index[start_cue_id] > cue_index[end_cue_id]:
                continue

            start_ms = cue_by_id[start_cue_id].start_ms
            end_ms = cue_by_id[end_cue_id].end_ms
            duration_ms = end_ms - start_ms
            if duration_ms < self.min_duration_ms or duration_ms > self.max_duration_ms:
                continue
            if any(
                self._overlap_ratio((start_ms, end_ms), existing) > self.max_overlap_ratio
                for existing in selected_ranges
            ):
                continue

            selected_ranges.append((start_ms, end_ms))
            intervals.append({"time": f"{self.format_ms(start_ms)} - {self.format_ms(end_ms)}"})
            if len(intervals) >= self.target_count:
                break

        return sorted(intervals, key=lambda interval: interval["time"])

    @staticmethod
    def _overlap_ratio(first: tuple[int, int], second: tuple[int, int]) -> float:
        overlap_start = max(first[0], second[0])
        overlap_end = min(first[1], second[1])
        overlap_ms = max(0, overlap_end - overlap_start)
        if overlap_ms == 0:
            return 0.0
        shortest_duration = min(first[1] - first[0], second[1] - second[0])
        return overlap_ms / shortest_duration if shortest_duration else 0.0

    @staticmethod
    def format_ms(total_ms: int) -> str:
        hours, remaining_ms = divmod(total_ms, 3_600_000)
        minutes, remaining_ms = divmod(remaining_ms, 60_000)
        seconds, milliseconds = divmod(remaining_ms, 1_000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

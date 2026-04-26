from collections.abc import Callable
from dataclasses import dataclass

from src.application.use_cases import ResolvedIntervals
from src.domain.entities import ShortVideo
from src.domain.exceptions import ShortGeneratorError
from src.interfaces.cli_utils import IntervalsFileResolution, OutroResolution


@dataclass(frozen=True)
class CliExecutionRequest:
    video_filepath: str
    subtitles_filepath: str
    intervals_filepath: str
    output_dir: str
    enable_outro: bool
    outro_filepath: str
    fade_duration: float
    auto_intervals: bool


@dataclass(frozen=True)
class CliExecutionResult:
    exit_code: int
    output_messages: tuple[str, ...]
    generated_shorts: tuple[ShortVideo, ...] = ()


class RunShortsCliUseCase:
    def __init__(
        self,
        file_exists: Callable[[str], bool],
        resolve_outro: Callable,
        load_intervals: Callable,
        interval_generator_factory: Callable,
        create_interval_resolver: Callable,
        persist_intervals: Callable,
        generate_shorts: Callable,
        ensure_output_dir: Callable[[str], None],
    ):
        self.file_exists = file_exists
        self.resolve_outro = resolve_outro
        self.load_intervals = load_intervals
        self.interval_generator_factory = interval_generator_factory
        self.create_interval_resolver = create_interval_resolver
        self.persist_intervals = persist_intervals
        self.generate_shorts = generate_shorts
        self.ensure_output_dir = ensure_output_dir

    def execute(self, request: CliExecutionRequest) -> CliExecutionResult:
        validation_error = self._validate_request(request)
        if validation_error is not None:
            return self._failure_result(validation_error)

        self.ensure_output_dir(request.output_dir)
        messages: list[str] = []
        outro_filepath = self._resolve_outro_filepath(request, messages)
        intervals_file_resolution = self._resolve_existing_intervals(request, messages)
        if isinstance(intervals_file_resolution, CliExecutionResult):
            return intervals_file_resolution
        manual_intervals_json = intervals_file_resolution.payload

        interval_generator_resolution = self.interval_generator_factory()
        self._append_message(messages, interval_generator_resolution.info_message)
        self._append_message(messages, interval_generator_resolution.warning_message)
        interval_generator = interval_generator_resolution.generator
        interval_resolver = self.create_interval_resolver(interval_generator)

        if manual_intervals_json is not None and not request.auto_intervals:
            messages.append(
                "Using existing intervals file without regeneration. "
                "Pass --auto-intervals to rebuild it with the configured automatic selector."
            )

        resolved_intervals = self._resolve_intervals(interval_resolver, request, manual_intervals_json)
        if isinstance(resolved_intervals, CliExecutionResult):
            return resolved_intervals

        self._append_message(messages, resolved_intervals.warning_message)
        generation_message = getattr(interval_generator, "last_generation_message", None)
        if generation_message and resolved_intervals.source == "auto":
            messages.append(generation_message)

        self._persist_generated_intervals(request, manual_intervals_json, resolved_intervals, messages)
        messages.append(f"Generating {len(resolved_intervals.intervals_json)} shorts...")
        generated_shorts = self._generate_shorts(request, resolved_intervals, outro_filepath)
        if isinstance(generated_shorts, CliExecutionResult):
            return generated_shorts

        messages.append(f"Successfully generated {len(generated_shorts)} shorts in {request.output_dir}/")
        messages.extend(f" - {short.filepath}" for short in generated_shorts)
        return CliExecutionResult(
            exit_code=0,
            output_messages=tuple(messages),
            generated_shorts=tuple(generated_shorts),
        )

    def _generate_shorts(
        self,
        request: CliExecutionRequest,
        resolved_intervals: ResolvedIntervals,
        outro_filepath: str | None,
    ) -> list[ShortVideo] | CliExecutionResult:
        try:
            return self.generate_shorts(
                video_filepath=request.video_filepath,
                subtitles_filepath=request.subtitles_filepath,
                intervals_json=resolved_intervals.intervals_json,
                output_dir=request.output_dir,
                outro_filepath=outro_filepath,
                fade_duration=request.fade_duration,
            )
        except ShortGeneratorError as exc:
            return self._failure_result(f"An error occurred during processing: {exc}")

    def _persist_generated_intervals(
        self,
        request: CliExecutionRequest,
        manual_intervals_json: list[dict[str, str]] | None,
        resolved_intervals: ResolvedIntervals,
        messages: list[str],
    ) -> None:
        if resolved_intervals.source != "auto":
            return
        if manual_intervals_json is not None and resolved_intervals.intervals_json == manual_intervals_json:
            messages.append(
                "Automatic interval generation finished, but the resulting JSON matches the existing intervals file."
            )
        self.persist_intervals(request.intervals_filepath, resolved_intervals.intervals_json)
        messages.append(
            f"Generated {len(resolved_intervals.intervals_json)} intervals and saved them to "
            f"{request.intervals_filepath}"
        )

    def _resolve_existing_intervals(
        self,
        request: CliExecutionRequest,
        messages: list[str],
    ) -> IntervalsFileResolution | CliExecutionResult:
        try:
            resolution = self.load_intervals(
                request.intervals_filepath,
                allow_invalid_json_warning=bool(request.auto_intervals),
            )
        except ValueError as exc:
            return self._failure_result(f"Error: Invalid JSON formulation in {request.intervals_filepath}\n{exc}")
        self._append_message(messages, resolution.warning_message)
        return resolution

    def _resolve_intervals(
        self,
        interval_resolver: Callable,
        request: CliExecutionRequest,
        manual_intervals_json: list[dict[str, str]] | None,
    ) -> ResolvedIntervals | CliExecutionResult:
        try:
            return interval_resolver(
                subtitles_filepath=request.subtitles_filepath,
                manual_intervals_json=manual_intervals_json,
                force_auto_generation=bool(request.auto_intervals),
            )
        except ShortGeneratorError as exc:
            return self._failure_result(f"An error occurred during processing: {exc}")

    def _resolve_outro_filepath(self, request: CliExecutionRequest, messages: list[str]) -> str | None:
        resolution: OutroResolution = self.resolve_outro(
            enable_outro=request.enable_outro,
            outro_filepath=request.outro_filepath,
        )
        self._append_message(messages, resolution.warning_message)
        return resolution.filepath

    def _validate_request(self, request: CliExecutionRequest) -> str | None:
        if not self.file_exists(request.video_filepath):
            return f"Error: Video file not found: {request.video_filepath}"
        if not self.file_exists(request.subtitles_filepath):
            return f"Error: Subtitles file not found: {request.subtitles_filepath}"
        if request.fade_duration < 0:
            return "Error: --fade-duration must be greater than or equal to 0"
        return None

    @staticmethod
    def _failure_result(message: str) -> CliExecutionResult:
        return CliExecutionResult(exit_code=1, output_messages=(message,))

    @staticmethod
    def _append_message(messages: list[str], message: str | None) -> None:
        if message:
            messages.append(message)

import argparse
import os
import sys

from src.application.cli_runner import CliExecutionRequest, RunShortsCliUseCase
from src.application.use_cases import GenerateShortUseCase, ResolveIntervalsUseCase
from src.infrastructure.ffmpeg_processor import FFmpegVideoProcessor
from src.infrastructure.subtitles import IntervalGeneratorFactory
from src.interfaces.cli_utils import persist_intervals_json, resolve_existing_intervals_file, resolve_outro_filepath


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate Shorts from a video with subtitles.")
    parser.add_argument(
        "--video",
        type=str,
        default="inputs/video.mp4",
        help="Path to the input video (.mp4) (default: inputs/video.mp4)",
    )
    parser.add_argument(
        "--subs",
        type=str,
        default="inputs/video.srt",
        help="Path to the subtitles file (.srt or .vtt) (default: inputs/video.srt)",
    )
    parser.add_argument(
        "--intervals",
        type=str,
        default="inputs/recortes.json",
        help="Path to a JSON file containing intervals (default: inputs/recortes.json)",
    )
    parser.add_argument(
        "--auto-intervals",
        action="store_true",
        help="Force automatic interval generation from the subtitles file and persist it to --intervals",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs",
        help="Directory to save shorts (default: outputs)",
    )
    parser.add_argument(
        "--enable-outro",
        action="store_true",
        help="Enable optional outro concatenation at the end of every short",
    )
    parser.add_argument(
        "--outro",
        type=str,
        default="inputs/outroShort.mp4",
        help="Path to outro video used when --enable-outro is set",
    )
    parser.add_argument(
        "--fade-duration",
        type=float,
        default=0.7,
        help="Fade transition duration in seconds (default: 0.7)",
    )
    return parser


def build_cli_use_case() -> RunShortsCliUseCase:
    processor = FFmpegVideoProcessor()
    generate_short_use_case = GenerateShortUseCase(video_processor=processor)

    return RunShortsCliUseCase(
        file_exists=os.path.exists,
        resolve_outro=resolve_outro_filepath,
        load_intervals=resolve_existing_intervals_file,
        interval_generator_factory=IntervalGeneratorFactory.build,
        create_interval_resolver=create_interval_resolver,
        persist_intervals=persist_intervals_json,
        generate_shorts=generate_short_use_case.execute,
        ensure_output_dir=ensure_output_dir,
    )


def create_interval_resolver(interval_generator):
    return ResolveIntervalsUseCase(interval_generator=interval_generator).execute


def ensure_output_dir(output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)


def to_cli_execution_request(args: argparse.Namespace) -> CliExecutionRequest:
    return CliExecutionRequest(
        video_filepath=args.video,
        subtitles_filepath=args.subs,
        intervals_filepath=args.intervals,
        output_dir=args.output,
        enable_outro=args.enable_outro,
        outro_filepath=args.outro,
        fade_duration=args.fade_duration,
        auto_intervals=bool(args.auto_intervals),
    )


def main():
    parser = build_argument_parser()
    args = parser.parse_args()
    result = build_cli_use_case().execute(to_cli_execution_request(args))

    for message in result.output_messages:
        print(message)

    if result.exit_code != 0:
        sys.exit(result.exit_code)


if __name__ == "__main__":
    main()

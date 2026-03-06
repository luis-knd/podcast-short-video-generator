import argparse
import json
import os
import sys

from src.application.use_cases import GenerateShortUseCase
from src.domain.exceptions import ShortGeneratorError
from src.infrastructure.ffmpeg_processor import FFmpegVideoProcessor
from src.interfaces.cli_utils import resolve_outro_filepath


def main():
    parser = argparse.ArgumentParser(
        description="Generate Shorts from a video with subtitles."
    )
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

    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)

    if not os.path.exists(args.subs):
        print(f"Error: Subtitles file not found: {args.subs}")
        sys.exit(1)

    if not os.path.exists(args.intervals):
        print(f"Error: Intervals JSON file not found: {args.intervals}")
        sys.exit(1)
    if args.fade_duration < 0:
        print("Error: --fade-duration must be greater than or equal to 0")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    outro_filepath, outro_warning = resolve_outro_filepath(
        enable_outro=args.enable_outro, outro_filepath=args.outro
    )
    if outro_warning:
        print(outro_warning)

    with open(args.intervals) as f:
        try:
            intervals_json = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON formulation in {args.intervals}\n{e}")
            sys.exit(1)

    # Dependency Injection
    processor = FFmpegVideoProcessor()
    use_case = GenerateShortUseCase(video_processor=processor)

    print(f"Generating {len(intervals_json)} shorts...")

    try:
        shorts = use_case.execute(
            video_filepath=args.video,
            subtitles_filepath=args.subs,
            intervals_json=intervals_json,
            output_dir=args.output,
            outro_filepath=outro_filepath,
            fade_duration=args.fade_duration,
        )

        print(f"Successfully generated {len(shorts)} shorts in {args.output}/")
        for short in shorts:
            print(f" - {short.filepath}")

    except ShortGeneratorError as e:
        print(f"An error occurred during processing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

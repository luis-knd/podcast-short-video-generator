from pathlib import Path

import ffmpeg

from src.application.broll import (
    BrollInsertionPlanner,
    BuildShortEditingPlanUseCase,
    ImpactBeatDetector,
    ManualBrollOverrideResolver,
)
from src.domain.entities import ShortVideo, Video
from src.domain.exceptions import InfrastructureError
from src.domain.ports import IVideoProcessor
from src.domain.value_objects import TimeInterval, VideoFormat
from src.infrastructure.broll.manual_override_loader import ManualBrollOverrideLoader
from src.infrastructure.broll.plan_writer import BrollPlanJsonWriter
from src.infrastructure.broll.providers import LocalMediaProvider, PexelsBrollProvider, PixabayBrollProvider
from src.infrastructure.config import ConfigManager
from src.infrastructure.subtitle_processor import SubtitleProcessor


class FFmpegVideoProcessor(IVideoProcessor):
    IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}
    _LEFT_SPEAKER_CROP_X = "in_w/16"
    _RIGHT_SPEAKER_CROP_X = "in_w/2-in_w/16"

    def __init__(
        self,
        subtitle_processor: SubtitleProcessor | None = None,
        editing_plan_builder: BuildShortEditingPlanUseCase | None = None,
    ):
        self.subtitle_processor = subtitle_processor or SubtitleProcessor()
        self.editing_plan_builder = editing_plan_builder or self._build_editing_plan_builder()

    def generate_short(
        self,
        video: Video,
        interval: TimeInterval,
        target_format: VideoFormat,
        output_filepath: str,
        outro_filepath: str | None = None,
        fade_duration: float = 0.7,
    ) -> ShortVideo:
        duration = interval.end_seconds - interval.start_seconds

        ass_filepath = output_filepath.replace(".mp4", ".ass")
        timeline = self.subtitle_processor.build_timeline(
            srt_filepath=video.subtitles_filepath,
            interval=interval,
            output_ass_filepath=ass_filepath,
            media_filepath=video.filepath,
        )
        self.subtitle_processor.write_ass_from_timeline(timeline, ass_filepath)

        stream = ffmpeg.input(video.filepath, ss=interval.start_seconds, t=duration)
        video_stream = self._build_split_screen_video_stream(
            source_video_stream=stream.video,
            target_format=target_format,
        )
        audio_stream = stream.audio
        editing_plan = self._build_editing_plan(
            output_filepath=output_filepath,
            timeline=timeline,
            target_format=target_format,
        )
        video_stream = self._apply_editing_plan(video_stream, editing_plan, target_format)

        safe_ass_filepath = ass_filepath.replace("\\", "/").replace(":", "\\:")
        video_stream = ffmpeg.filter(video_stream, "ass", safe_ass_filepath)

        video_stream, audio_stream = self._append_outro_if_enabled(
            base_video_stream=video_stream,
            base_audio_stream=audio_stream,
            target_format=target_format,
            base_duration=duration,
            outro_filepath=outro_filepath,
            fade_duration=fade_duration,
        )

        out = ffmpeg.output(
            video_stream,
            audio_stream,
            output_filepath,
            vcodec="libx264",
            acodec="aac",
            preset="fast",
        )

        out = out.global_args("-loglevel", "warning", "-y")
        try:
            out.run()
        except ffmpeg.Error as e:
            raise InfrastructureError(f"FFmpeg processing failed: {e}") from e

        return ShortVideo(
            filepath=output_filepath,
            original_video=video,
            interval=interval,
            format=target_format,
        )

    def _build_editing_plan(self, output_filepath: str, timeline, target_format: VideoFormat):
        try:
            return self.editing_plan_builder.build(
                short_id=Path(output_filepath).stem,
                timeline=timeline,
                output_dir=str(Path(output_filepath).parent),
                target_width=target_format.width,
                target_height=target_format.height,
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            return None

    @staticmethod
    def _build_split_screen_video_stream(source_video_stream, target_format: VideoFormat):
        split = source_video_stream.split()
        left = FFmpegVideoProcessor._build_speaker_stream(
            speaker_stream=split[0],
            speaker_crop_x=FFmpegVideoProcessor._LEFT_SPEAKER_CROP_X,
            target_format=target_format,
        )
        right = FFmpegVideoProcessor._build_speaker_stream(
            speaker_stream=split[1],
            speaker_crop_x=FFmpegVideoProcessor._RIGHT_SPEAKER_CROP_X,
            target_format=target_format,
        )
        return ffmpeg.filter([left, right], "vstack")

    @staticmethod
    def _build_speaker_stream(speaker_stream, speaker_crop_x: str, target_format: VideoFormat):
        speaker_stream = speaker_stream.filter("crop", "in_w/2", "in_h", speaker_crop_x, "0")
        speaker_stream = speaker_stream.filter("scale", target_format.width, "-1")
        return speaker_stream.filter(
            "crop",
            target_format.width,
            target_format.height // 2,
            "0",
            "(in_h-out_h)/2",
        )

    @staticmethod
    def _append_outro_if_enabled(
        base_video_stream,
        base_audio_stream,
        target_format: VideoFormat,
        base_duration: float,
        outro_filepath: str | None,
        fade_duration: float,
    ):
        if not outro_filepath:
            return base_video_stream, base_audio_stream

        effective_fade_duration = min(max(fade_duration, 0.0), base_duration)
        if effective_fade_duration > 0:
            fade_out_start = max(base_duration - effective_fade_duration, 0.0)
            base_video_stream = base_video_stream.filter(
                "fade",
                type="out",
                start_time=fade_out_start,
                duration=effective_fade_duration,
            )
            base_audio_stream = base_audio_stream.filter(
                "afade",
                type="out",
                start_time=fade_out_start,
                duration=effective_fade_duration,
            )

        outro_input_stream = ffmpeg.input(outro_filepath)
        outro_video_stream = outro_input_stream.video
        outro_audio_stream = outro_input_stream.audio

        # Keep output format stable for concat by normalizing outro dimensions.
        outro_video_stream = outro_video_stream.filter(
            "scale",
            target_format.width,
            target_format.height,
            force_original_aspect_ratio="decrease",
        )
        outro_video_stream = outro_video_stream.filter(
            "pad",
            target_format.width,
            target_format.height,
            "(ow-iw)/2",
            "(oh-ih)/2",
        )

        if effective_fade_duration > 0:
            outro_video_stream = outro_video_stream.filter(
                "fade",
                type="in",
                start_time=0,
                duration=effective_fade_duration,
            )
            outro_audio_stream = outro_audio_stream.filter(
                "afade",
                type="in",
                start_time=0,
                duration=effective_fade_duration,
            )

        concat_node = ffmpeg.concat(
            base_video_stream,
            base_audio_stream,
            outro_video_stream,
            outro_audio_stream,
            v=1,
            a=1,
        ).node
        return concat_node[0], concat_node[1]

    def _apply_editing_plan(self, base_video_stream, editing_plan, target_format: VideoFormat):
        if editing_plan is None or not editing_plan.enabled or not editing_plan.insertions:
            return base_video_stream

        video_stream = base_video_stream
        for insertion in editing_plan.insertions:
            asset_stream = self._build_broll_stream(insertion, target_format)
            enable_expr = f"between(t,{insertion.start_ms / 1000:.3f},{insertion.end_ms / 1000:.3f})"
            video_stream = ffmpeg.overlay(
                video_stream,
                asset_stream,
                x=insertion.x,
                y=insertion.y,
                enable=enable_expr,
                eof_action="pass",
            )
        return video_stream

    def _build_broll_stream(self, insertion, target_format: VideoFormat):
        insertion_duration = max((insertion.end_ms - insertion.start_ms) / 1000, 0.3)
        asset_path = insertion.asset_path
        if self._is_still_image(asset_path):
            asset_stream = ffmpeg.input(asset_path, loop=1, framerate=30, t=insertion_duration).video
        else:
            asset_stream = ffmpeg.input(asset_path, ss=insertion.asset_in_ms / 1000, t=insertion_duration).video

        asset_stream = asset_stream.filter(
            "setpts",
            f"PTS-STARTPTS+{insertion.start_ms / 1000:.3f}/TB",
        )

        if insertion.mode in {"cutaway", "full_frame_cutaway"}:
            asset_stream = asset_stream.filter(
                "scale",
                target_format.width,
                target_format.height,
                force_original_aspect_ratio="increase",
            )
            return asset_stream.filter(
                "crop",
                target_format.width,
                target_format.height,
                "(in_w-out_w)/2",
                "(in_h-out_h)/2",
            )

        asset_stream = asset_stream.filter(
            "scale",
            insertion.width,
            insertion.height,
            force_original_aspect_ratio="decrease",
        )
        asset_stream = asset_stream.filter(
            "pad",
            insertion.width,
            insertion.height,
            "(ow-iw)/2",
            "(oh-ih)/2",
        )
        if insertion.opacity < 1.0:
            asset_stream = asset_stream.filter("format", "rgba")
            asset_stream = asset_stream.filter("colorchannelmixer", aa=insertion.opacity)
        return asset_stream

    @staticmethod
    def _build_editing_plan_builder() -> BuildShortEditingPlanUseCase:
        config = ConfigManager()
        local_dirs = config.get_broll_setting("local_search_dirs", [])
        if not isinstance(local_dirs, list):
            local_dirs = []

        beat_threshold = float(config.get_broll_setting("beat_score_threshold", 0.68))
        cutaway_threshold = float(config.get_broll_setting("cutaway_score_threshold", 0.82))
        min_gap_ms = int(config.get_broll_setting("min_gap_ms", 4500))
        overlay_top_y = int(config.get_broll_setting("overlay_top_y", 120))
        overrides_filepath = config.get_broll_setting("overrides_filepath", None)

        return BuildShortEditingPlanUseCase(
            providers=(
                LocalMediaProvider(search_dirs=tuple(local_dirs)),
                PexelsBrollProvider(),
                PixabayBrollProvider(),
            ),
            plan_writer=BrollPlanJsonWriter(),
            beat_detector=ImpactBeatDetector(
                minimum_score=beat_threshold,
            ),
            insertion_planner=BrollInsertionPlanner(
                minimum_gap_ms=min_gap_ms,
                beat_score_threshold=beat_threshold,
                cutaway_score_threshold=cutaway_threshold,
                overlay_top_y=overlay_top_y,
            ),
            manual_override_loader=ManualBrollOverrideLoader(filepath=overrides_filepath),
            manual_override_resolver=ManualBrollOverrideResolver(),
            enabled=bool(config.get_broll_setting("enabled", False)),
        )

    def _is_still_image(self, asset_path: str) -> bool:
        return Path(asset_path).suffix.lower() in self.IMAGE_EXTENSIONS

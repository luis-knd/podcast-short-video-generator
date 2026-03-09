import ffmpeg

from src.domain.entities import ShortVideo, Video
from src.domain.exceptions import InfrastructureError
from src.domain.ports import IVideoProcessor
from src.domain.value_objects import TimeInterval, VideoFormat
from src.infrastructure.subtitle_processor import SubtitleProcessor


class FFmpegVideoProcessor(IVideoProcessor):
    def __init__(self, subtitle_processor: SubtitleProcessor | None = None):
        self.subtitle_processor = subtitle_processor or SubtitleProcessor()

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

        # Process subtitles and get speaker segments
        ass_filepath = output_filepath.replace(".mp4", ".ass")
        self.subtitle_processor.process_subtitles(
            video.subtitles_filepath,
            interval,
            ass_filepath,
            media_filepath=video.filepath,
        )

        stream = ffmpeg.input(video.filepath, ss=interval.start_seconds, t=duration)
        video_stream = self._build_split_screen_video_stream(
            source_video_stream=stream.video,
            target_format=target_format,
        )
        audio_stream = stream.audio

        # Burn progressive subtitles
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

    @staticmethod
    def _build_split_screen_video_stream(source_video_stream, target_format: VideoFormat):
        # Create two streams for left and right speakers
        split = source_video_stream.split()
        left = split[0]
        right = split[1]

        # Left speaker: crop left half, scale to 1080 width, crop center to half-height
        left = left.filter("crop", "in_w/2", "in_h", "0", "0")
        left = left.filter("scale", target_format.width, "-1")
        left = left.filter(
            "crop",
            target_format.width,
            target_format.height // 2,
            "0",
            "(in_h-out_h)/2",
        )

        # Right speaker: crop right half, scale to 1080 width, crop center to half-height
        right = right.filter("crop", "in_w/2", "in_h", "in_w/2", "0")
        right = right.filter("scale", target_format.width, "-1")
        right = right.filter(
            "crop",
            target_format.width,
            target_format.height // 2,
            "0",
            "(in_h-out_h)/2",
        )

        # Stack them vertically to form a 1080x1920 video
        return ffmpeg.filter([left, right], "vstack")

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

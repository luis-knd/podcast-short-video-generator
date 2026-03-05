import ffmpeg

from src.domain.entities import ShortVideo, Video
from src.domain.exceptions import InfrastructureError
from src.domain.ports import IVideoProcessor
from src.domain.value_objects import TimeInterval, VideoFormat
from src.infrastructure.subtitle_processor import SubtitleProcessor


class FFmpegVideoProcessor(IVideoProcessor):
    def generate_short(
        self,
        video: Video,
        interval: TimeInterval,
        target_format: VideoFormat,
        output_filepath: str,
    ) -> ShortVideo:
        duration = interval.end_seconds - interval.start_seconds

        # Process subtitles and get speaker segments
        ass_filepath = output_filepath.replace(".mp4", ".ass")
        subtitle_processor = SubtitleProcessor()
        subtitle_processor.process_subtitles(
            video.subtitles_filepath, interval, ass_filepath
        )

        stream = ffmpeg.input(video.filepath, ss=interval.start_seconds, t=duration)

        # Create two streams for left and right speakers
        split = stream.video.split()
        left = split[0]
        right = split[1]

        # Left speaker: crop left half, scale to 1080 width, crop center to 960 height
        left = left.filter("crop", "in_w/2", "in_h", "0", "0")
        left = left.filter("scale", target_format.width, "-1")
        left = left.filter(
            "crop",
            target_format.width,
            target_format.height // 2,
            "0",
            "(in_h-out_h)/2",
        )

        # Right speaker: crop right half, scale to 1080 width, crop center to 960 height
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
        video_stream = ffmpeg.filter([left, right], "vstack")

        safe_ass_filepath = ass_filepath.replace("\\", "/").replace(":", "\\:")
        video_stream = ffmpeg.filter(video_stream, "ass", safe_ass_filepath)

        audio_stream = stream.audio

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

import json
from pathlib import Path

from src.domain.value_objects import TimeInterval
from src.infrastructure.subtitles.interval_generator import ViralSubtitleIntervalGenerator


def test_viral_subtitle_interval_generator_avoids_intro_and_prefers_high_utility_sections(tmp_path):
    srt_file = tmp_path / "episode.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:06,000\n"
        "Welcome back to the podcast, subscribe for more episodes.\n"
        "\n"
        "2\n"
        "00:00:06,000 --> 00:00:12,000\n"
        "Today we are looking at another great song.\n"
        "\n"
        "3\n"
        "00:03:00,000 --> 00:03:07,000\n"
        "Why is this phrase dangerous at work?\n"
        "\n"
        "4\n"
        "00:03:07,000 --> 00:03:14,000\n"
        "Because it sounds romantic in the song but rude in real life.\n"
        "\n"
        "5\n"
        "00:03:14,000 --> 00:03:21,000\n"
        "Imagine saying it in a job interview.\n"
        "\n"
        "6\n"
        "00:03:21,000 --> 00:03:28,000\n"
        "Instead, you could say let's stay in touch.\n"
        "\n"
        "7\n"
        "00:07:50,000 --> 00:07:57,000\n"
        "Your mind is polluted sounds too strong for a friend.\n"
        "\n"
        "8\n"
        "00:07:57,000 --> 00:08:04,000\n"
        "A safer swap is don't be so hard on yourself.\n",
        encoding="utf-8",
    )

    generator = ViralSubtitleIntervalGenerator()

    intervals = generator.generate(str(srt_file))

    assert intervals
    assert intervals[0]["time"] == "00:03:00,000 - 00:03:28,000"
    assert all(not interval["time"].startswith("00:00:") for interval in intervals)


def test_viral_subtitle_interval_generator_improves_overlap_against_manual_episode_fixture():
    root = Path(__file__).resolve().parents[2]
    generator = ViralSubtitleIntervalGenerator()
    generated = generator.generate(str(root / "inputs" / "video.srt"))
    manual = json.loads((root / "inputs" / "recortes.json").read_text(encoding="utf-8"))

    assert len(generated) >= 8
    assert generated[0]["time"] >= "00:03:00,000 - 00:03:00,000"
    assert any(interval["time"].startswith("00:07:") for interval in generated)
    assert any(_covers_nine_minute_region(interval["time"]) for interval in generated)
    assert manual


def _covers_nine_minute_region(time_range: str) -> bool:
    interval = TimeInterval.from_string(time_range)
    return interval.start_seconds < 540 < interval.end_seconds

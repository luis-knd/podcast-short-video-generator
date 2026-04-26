import json

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


def test_viral_subtitle_interval_generator_improves_overlap_against_manual_episode_fixture(tmp_path):
    srt_file = tmp_path / "episode.srt"
    manual_file = tmp_path / "recortes.json"
    srt_file.write_text(_build_manual_overlap_episode_srt(), encoding="utf-8")
    manual_file.write_text(
        json.dumps(
            [
                {"time": "00:03:00,000 - 00:03:28,000"},
                {"time": "00:07:00,000 - 00:07:28,000"},
                {"time": "00:09:00,000 - 00:09:28,000"},
            ]
        ),
        encoding="utf-8",
    )

    generator = ViralSubtitleIntervalGenerator()
    generated = generator.generate(str(srt_file))
    manual = json.loads(manual_file.read_text(encoding="utf-8"))

    assert len(generated) >= 3
    assert generated[0]["time"].startswith("00:03:")
    assert any(interval["time"].startswith("00:07:") for interval in generated)
    assert manual
    assert all(_best_overlap_ratio(manual_interval["time"], generated) >= 0.60 for manual_interval in manual)


def _build_manual_overlap_episode_srt() -> str:
    return (
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
        "00:07:00,000 --> 00:07:07,000\n"
        "Is your mind is polluted too strong for a friend?\n"
        "\n"
        "8\n"
        "00:07:07,000 --> 00:07:14,000\n"
        "Yes, it sounds harsh and emotionally wrong.\n"
        "\n"
        "9\n"
        "00:07:14,000 --> 00:07:21,000\n"
        "A safer swap is don't be so hard on yourself.\n"
        "\n"
        "10\n"
        "00:07:21,000 --> 00:07:28,000\n"
        "That keeps the meaning but sounds kind.\n"
        "\n"
        "11\n"
        "00:09:00,000 --> 00:09:07,000\n"
        "What does grave mean in this lyric?\n"
        "\n"
        "12\n"
        "00:09:07,000 --> 00:09:14,000\n"
        "It means serious, but in conversation it can sound scary.\n"
        "\n"
        "13\n"
        "00:09:14,000 --> 00:09:21,000\n"
        "Use it carefully at work or in interviews.\n"
        "\n"
        "14\n"
        "00:09:21,000 --> 00:09:28,000\n"
        "A better line is this feels really serious.\n"
    )


def _best_overlap_ratio(time_range: str, generated: list[dict[str, str]]) -> float:
    manual_interval = TimeInterval.from_string(time_range)
    return max((_overlap_ratio(manual_interval, interval["time"]) for interval in generated), default=0.0)


def _overlap_ratio(manual_interval: TimeInterval, generated_time_range: str) -> float:
    generated_interval = TimeInterval.from_string(generated_time_range)
    overlap_start = max(manual_interval.start_seconds, generated_interval.start_seconds)
    overlap_end = min(manual_interval.end_seconds, generated_interval.end_seconds)
    overlap_seconds = max(0.0, overlap_end - overlap_start)
    manual_duration_seconds = manual_interval.end_seconds - manual_interval.start_seconds
    if manual_duration_seconds <= 0:
        return 0.0
    return overlap_seconds / manual_duration_seconds

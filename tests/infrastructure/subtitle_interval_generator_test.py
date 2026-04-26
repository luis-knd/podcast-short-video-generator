from src.infrastructure.subtitles.interval_generator import HeuristicSubtitleIntervalGenerator


def test_heuristic_subtitle_interval_generator_skips_cta_intro_and_keeps_the_stronger_candidate(tmp_path):
    srt_file = tmp_path / "episode.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:06,000\n"
        "Welcome to the podcast, please subscribe and like.\n"
        "\n"
        "2\n"
        "00:00:10,000 --> 00:00:17,000\n"
        "Why is this song so emotional?\n"
        "\n"
        "3\n"
        "00:00:17,000 --> 00:00:24,000\n"
        "Because it mixes loyalty, fear, and exaggeration.\n"
        "\n"
        "4\n"
        "00:00:24,000 --> 00:00:31,000\n"
        "Let's break down the core phrase together.\n"
        "\n"
        "5\n"
        "00:00:31,000 --> 00:00:36,000\n"
        "This example even works at work.\n",
        encoding="utf-8",
    )

    generator = HeuristicSubtitleIntervalGenerator()

    assert generator.generate(str(srt_file)) == [{"time": "00:00:10,000 - 00:00:31,000"}]


def test_heuristic_subtitle_interval_generator_prefers_the_highest_scoring_window_from_a_long_run(tmp_path):
    srt_file = tmp_path / "long.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:08,000\n"
        "Let's start with the first big idea.\n"
        "\n"
        "2\n"
        "00:00:08,000 --> 00:00:16,000\n"
        "This example shows how the idiom changes in context.\n"
        "\n"
        "3\n"
        "00:00:16,000 --> 00:00:24,000\n"
        "Why does it matter so much in conversation?\n"
        "\n"
        "4\n"
        "00:00:24,000 --> 00:00:32,000\n"
        "Because the wrong register can sound rude at work.\n"
        "\n"
        "5\n"
        "00:00:32,000 --> 00:00:40,000\n"
        "Now let's move to the second scenario.\n"
        "\n"
        "6\n"
        "00:00:40,000 --> 00:00:48,000\n"
        "Imagine saying the lyric in a job interview.\n"
        "\n"
        "7\n"
        "00:00:48,000 --> 00:00:56,000\n"
        "That sounds memorable, but completely wrong.\n",
        encoding="utf-8",
    )

    generator = HeuristicSubtitleIntervalGenerator()
    intervals = generator.generate(str(srt_file))

    assert intervals == [{"time": "00:00:16,000 - 00:00:48,000"}]


def test_heuristic_subtitle_interval_generator_returns_empty_list_for_empty_srt(tmp_path):
    srt_file = tmp_path / "empty.srt"
    srt_file.write_text("", encoding="utf-8")

    generator = HeuristicSubtitleIntervalGenerator()

    assert generator.generate(str(srt_file)) == []

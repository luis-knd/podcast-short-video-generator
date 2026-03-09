import os
import tempfile

import pytest

from src.domain.value_objects import TimeInterval
from src.infrastructure.subtitle_processor import SubtitleProcessor


class TruthyEmptyColors:
    def __bool__(self):
        return True

    def __iter__(self):
        return iter(())


def _make_segment(words: list[str], start_ms: int = 0, step_ms: int = 500):
    current = start_ms
    timed_words = []
    for word in words:
        timed_words.append({"text": word, "start": current, "end": current + step_ms})
        current += step_ms

    return [
        {
            "speaker": "Speaker 1",
            "phrase_text": " ".join(words),
            "start_ms": start_ms,
            "end_ms": current,
            "words": timed_words,
        }
    ]


@pytest.fixture
def sample_srt_content():
    return """1
00:04:48,000 --> 00:04:50,500
Speaker 0: Hola, bienvenidos al episodio 8.

2
00:04:50,500 --> 00:04:52,000
Speaker 1: Gracias por la invitación.

3
00:04:52,000 --> 00:04:55,000
Speaker 0: Hoy vamos a hablar de cómo procesar videos de forma automática.
"""


def test_subtitle_processor_extracts_and_shifts_time(sample_srt_content):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False) as f:
        f.write(sample_srt_content)
        srt_path = f.name

    ass_path = srt_path.replace(".srt", ".ass")

    try:
        processor = SubtitleProcessor()
        # Interval from 04:50 to 04:53
        interval = TimeInterval.from_string("04:50 - 04:53")

        # It should extract the 1st, 2nd, and 3rd subtitle blocks (1st overlaps slightly)

        parsed_data = processor.process_subtitles(srt_path, interval, ass_path)

        # Verify the parsed data contains speakers
        assert len(parsed_data) == 3
        assert parsed_data[0]["speaker"] == "Speaker 0"
        assert parsed_data[0]["phrase_text"] == "8."
        assert parsed_data[1]["speaker"] == "Speaker 1"
        assert parsed_data[1]["phrase_text"] == "Gracias por la invitación."
        assert parsed_data[2]["speaker"] == "Speaker 0"
        assert parsed_data[2]["phrase_text"] == "Hoy vamos a hablar"

        # Verify ASS file is created
        assert os.path.exists(ass_path)

        with open(ass_path) as ass_f:
            ass_content = ass_f.read()

        # The file time should be shifted.
        # Original: 00:04:50,500 -> Shifted (-00:04:50,000): 00:00:00.50

        # Exact format string assertions to kill syntax mutants
        expected_header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
            " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,"
            " ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
            " Alignment, MarginL, MarginR, MarginV, Encoding"
        )
        assert expected_header in ass_content

        expected_events = """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""
        assert expected_events in ass_content

        assert "Style: BaseLayer," in ass_content
        assert "Style: ActiveLayer," in ass_content
        assert "&H000000FF," in ass_content
        assert "&H80000000,-1,0,0,0,100,100,0,0,1,6,3,5,10,10,250,1" in ass_content

        assert "Dialogue: 0," in ass_content
        assert "Dialogue: 1," in ass_content
        assert "\\an5\\pos" in ass_content
        assert "\\t(0,120,\\fscx120\\fscy120)" in ass_content

        # Exact position assertions to kill layout math mutants
        assert "{\\an5\\pos(540,1050)}8." in ass_content
        assert "{\\an5\\pos(418,993)}Gracias" in ass_content
        assert "{\\an5\\pos(654,993)}por" in ass_content
        assert "{\\an5\\pos(540,1107)}invitación." in ass_content

    finally:
        os.remove(srt_path)
        if os.path.exists(ass_path):
            os.remove(ass_path)


def test_subtitle_phrase_grouping():
    processor = SubtitleProcessor()

    words = ["Hola,", "bienvenidos", "al", "episodio", "8."]
    phrases = processor._group_into_phrases(words, words_per_phrase=4)
    assert phrases == [["Hola,", "bienvenidos", "al", "episodio"], ["8."]]

    # Test default args
    phrases_default = processor._group_into_phrases(["A", "B", "C", "D", "E"])
    assert phrases_default == [["A", "B", "C", "D"], ["E"]]


def test_subtitle_duration_calculation():
    processor = SubtitleProcessor()
    # 2.5 seconds total for "Hola, bienvenidos al episodio 8." (5 words) -> 0.5s per word
    chunks = ["Hola,", "bienvenidos", "al", "episodio", "8."]
    start_ms = 4 * 60 * 1000 + 48 * 1000  # 4:48.000
    end_ms = start_ms + 2500  # 4:50.500

    timed_chunks = processor._calculate_chunk_times(chunks, start_ms, end_ms)

    assert len(timed_chunks) == 5
    assert timed_chunks[0]["text"] == "Hola,"
    assert timed_chunks[0]["start"] == start_ms
    assert timed_chunks[0]["end"] == start_ms + 500

    assert timed_chunks[1]["text"] == "bienvenidos"
    assert timed_chunks[1]["start"] == start_ms + 500
    assert timed_chunks[1]["end"] == start_ms + 1000

    assert timed_chunks[4]["text"] == "8."
    assert timed_chunks[4]["start"] == start_ms + 2000
    assert timed_chunks[4]["end"] == start_ms + 2500


def test_subtitle_duration_calculation_empty():
    processor = SubtitleProcessor()
    # Test empty chunks branch
    assert processor._calculate_chunk_times([], 0, 1000) == []
    assert processor._calculate_chunk_times(["", "  "], 0, 1000) == []


def test_parse_time_to_ms():
    processor = SubtitleProcessor()
    assert processor._parse_time_to_ms("01:02:03,004") == 3723004
    assert processor._parse_time_to_ms("  01:02:03,004  ") == 3723004
    assert processor._parse_time_to_ms("00:00:00,000") == 0
    assert processor._parse_time_to_ms("01:00:00,000") == 3600000
    assert processor._parse_time_to_ms("00:01:00,000") == 60000
    assert processor._parse_time_to_ms("00:00:01,000") == 1000


def test_format_ms_to_ass_time():
    processor = SubtitleProcessor()
    # Format: H:MM:SS.cs
    # 3723004 ms -> 1:02:03.00
    # wait, cs is ms // 10
    # 4 ms // 10 = 0 -> 00
    assert processor._format_ms_to_ass_time(3723004) == "1:02:03.00"

    # Let's test non-zero centiseconds
    # 57 ms -> 5 cs
    assert processor._format_ms_to_ass_time(3723057) == "1:02:03.05"
    assert processor._format_ms_to_ass_time(0) == "0:00:00.00"
    # Rounding up or truncation?
    assert processor._format_ms_to_ass_time(99) == "0:00:00.09"

    assert processor._format_ms_to_ass_time(3600000) == "1:00:00.00"
    assert processor._format_ms_to_ass_time(60000) == "0:01:00.00"
    assert processor._format_ms_to_ass_time(1000) == "0:00:01.00"


def test_get_text_width():
    processor = SubtitleProcessor()
    font_size = 100

    assert processor._get_text_width(" ", font_size) == 25

    # Thin chars: il1!.,;:| (48 * 0.4 = 19)
    assert processor._get_text_width("i", font_size) == 19
    assert processor._get_text_width("1!", font_size) == 38

    # Wide chars: wmWM (48 * 1.5 = 72)
    assert processor._get_text_width("w", font_size) == 72
    assert processor._get_text_width("WM", font_size) == 144

    # Medium chars: tfjI (48 * 0.6 = 28)
    assert processor._get_text_width("t", font_size) == 28

    # Uppercase (not previously matched): A-Z (48 * 1.1 = 52)
    assert processor._get_text_width("A", font_size) == 52

    # Default char: a-z (48)
    assert processor._get_text_width("a", font_size) == 48

    # Catch mutation of += to =
    assert processor._get_text_width("AA", font_size) == 104

    # Catch string inclusion mutation: test character not in the lists
    assert processor._get_text_width("X", font_size) == 52

    # Combined string
    # "I " -> I (28) + Space (25) = 53
    assert processor._get_text_width("I ", font_size) == 53


def test_subtitle_processor_complex_edge_cases(tmp_path):
    processor = SubtitleProcessor()

    srt_content = """1
00:00:07,500 --> 00:00:08,500
Speaker 1: Exact overlap on start boundary happens here

2
00:00:08,600 --> 00:00:09,000
Line one
Line two

3
00:00:09,000 --> 00:00:10,500
This is a very long text that contains more than six words exactly.

4
00:00:10,000 --> 00:00:10,010
"""
    # Block 4 is empty words!

    temp_srt = tmp_path / "test.srt"
    temp_srt.write_text(srt_content, encoding="utf-8")

    from src.domain.value_objects import TimeInterval

    interval = TimeInterval(8.0, 10.0)
    output_ass = str(tmp_path / "output.ass")

    # We mock config to guarantee font_name, colors, to exactly match the header
    from unittest.mock import patch

    with (
        patch("src.infrastructure.config.ConfigManager.get_subtitle_setting") as mock_get_setting,
        patch("src.infrastructure.config.ConfigManager.get_brand_colors") as mock_colors,
    ):

        def mock_setting(key, default):
            settings = {
                "font_name": "Montserrat",
                "font_size": 85,
                "base_color_hex": "#FFFFFF",
                "active_border_color_hex": "#000000",
                "y_position": 1050,
            }
            return settings.get(key, default)

        mock_get_setting.side_effect = mock_setting
        mock_colors.return_value = ["#26f4ff", "#e61b8e", "#d1ff02"]

        parsed_data = processor.process_subtitles(str(temp_srt), interval, output_ass)

    with open(output_ass, encoding="utf-8") as f:
        ass_content = f.read()

    # Exact strict header assertion
    expected_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
"""
    assert ass_content.startswith(expected_header)

    expected_format = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
        " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,"
        " ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
        " Alignment, MarginL, MarginR, MarginV, Encoding\n"
    )
    assert expected_format in ass_content

    # Note: &H00000000 vs &H80000000 and hex format MUST match exactly.
    base_layer_style = (
        "Style: BaseLayer,Montserrat,85,&HFFFFFF&,"
        "&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,5,10,10,250,1\n"
    )
    assert base_layer_style in ass_content
    active_layer_style = (
        "Style: ActiveLayer,Montserrat,85,&Hfff426&,"
        "&H000000FF,&H000000&,&H80000000,-1,0,0,0,100,100,0,0,1,8,3,5,10,10,250,1\n"
    )
    assert active_layer_style in ass_content
    assert "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" in ass_content

    # Check that multiline concatenated properly:
    # "Line one" and "Line two" are in parsed_data
    texts = [item["phrase_text"] for item in parsed_data]
    assert "Line one Line two" in texts

    # Check the long phrase group split properly (max 6 words per phrase):
    # "This is a very long text that contains more than six words exactly." (13 words)
    assert "This is a very long text" in texts
    assert "that contains more" in texts
    # "exactly." might be left out if it falls out of time bounds, or combined

    # Verify speaker fallback to "Speaker Unknown"
    speakers = {item["phrase_text"]: item["speaker"] for item in parsed_data}
    if "Line one Line two" in speakers:
        assert speakers["Line one Line two"] == "Speaker Unknown"


def test_process_subtitles_edge_cases(tmp_path):
    processor = SubtitleProcessor()

    srt_content = """1
00:00:01,000 --> 00:00:02,000

2
00:00:03,000 --> 00:00:04,000
Unknown block

3
Invalid time line
Speaker 1: Hi

4
00:00:05,000 --> 00:00:06,000
No speaker prefix here

5
00:01:00,000 --> 00:01:05,000
Speaker 1: This is way out of interval

6
00:00:09,000 --> 00:00:11,000
Speaker 2: Partially overlapping

7
00:00:08,500 --> 00:00:09,500
Speaker 3:
"""
    srt_file = tmp_path / "edge.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    ass_file = tmp_path / "out.ass"

    interval = TimeInterval(start_seconds=8.0, end_seconds=10.0)

    # 8.0s to 10.0s
    # Block 1 (1-2s): completely before
    # Block 2 (3-4s): less than 3 lines after split
    # Block 3: no match time
    # Block 4: outside interval
    # Block 5: completely after
    # Block 6: (9-11s) overlaps. Shifted: 1000ms to 3000ms. But interval is 2000ms long.
    # Block 7: Empty words.

    result = processor.process_subtitles(str(srt_file), interval, str(ass_file))

    assert len(result) == 1
    assert result[0]["speaker"] == "Speaker 2"
    assert result[0]["phrase_text"] == "Partially"
    # Overlapping boundary clip: it starts at 9s (1000ms relative), and ends at 10s (2000ms relative clip max)
    assert result[0]["start_ms"] == 1000
    assert result[0]["end_ms"] == 2000


def test_format_ms_to_ass_time_should_preserve_small_centiseconds():
    processor = SubtitleProcessor()

    assert processor._format_ms_to_ass_time(10) == "0:00:00.01"
    assert processor._format_ms_to_ass_time(21) == "0:00:00.02"


def test_process_subtitles_should_exclude_blocks_touching_interval_boundaries(tmp_path):
    processor = SubtitleProcessor()
    srt_content = """1
00:00:09,000 --> 00:00:10,000
Speaker 0: Ends exactly at interval start

2
00:00:10,000 --> 00:00:11,000
Speaker 1: Inside interval

3
00:00:20,000 --> 00:00:21,000
Speaker 2: Starts exactly at interval end
"""

    srt_file = tmp_path / "boundaries.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    ass_file = tmp_path / "boundaries.ass"

    result = processor.process_subtitles(str(srt_file), TimeInterval(10.0, 20.0), str(ass_file))

    assert len(result) == 1
    assert result[0]["speaker"] == "Speaker 1"
    assert result[0]["phrase_text"] == "Inside interval"


def test_process_subtitles_should_skip_non_overlapping_blocks_before_timing_calculation(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    calls = []

    def capture_chunk_times(chunks, start_ms, end_ms):
        calls.append((start_ms, end_ms, list(chunks)))
        return [{"text": chunk, "start": start_ms, "end": end_ms} for chunk in chunks]

    monkeypatch.setattr(processor, "_calculate_chunk_times", capture_chunk_times)

    srt_content = """1
00:00:01,000 --> 00:00:09,000
Speaker 0: block outside before interval

2
00:00:10,000 --> 00:00:11,000
Speaker 1: block inside interval

3
00:00:20,000 --> 00:00:22,000
Speaker 2: block outside after interval
"""

    srt_file = tmp_path / "interval-filter.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    ass_file = tmp_path / "interval-filter.ass"

    result = processor.process_subtitles(str(srt_file), TimeInterval(10.0, 20.0), str(ass_file))

    assert len(result) == 1
    assert result[0]["speaker"] == "Speaker 1"
    assert result[0]["phrase_text"] == "block inside interval"
    assert len(calls) == 1
    assert calls[0][0] == 10000
    assert calls[0][1] == 11000


def test_process_subtitles_should_skip_boundary_block_ending_at_interval_start(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    calls = []

    def capture_chunk_times(chunks, start_ms, end_ms):
        calls.append((start_ms, end_ms, list(chunks)))
        return [{"text": chunk, "start": start_ms, "end": end_ms} for chunk in chunks]

    monkeypatch.setattr(processor, "_calculate_chunk_times", capture_chunk_times)

    srt_content = """1
00:00:08,000 --> 00:00:10,000
Speaker 0: boundary end equals interval start

2
00:00:10,000 --> 00:00:11,000
Speaker 1: valid block
"""

    srt_file = tmp_path / "boundary-start.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    ass_file = tmp_path / "boundary-start.ass"

    result = processor.process_subtitles(str(srt_file), TimeInterval(10.0, 20.0), str(ass_file))

    assert len(result) == 1
    assert result[0]["speaker"] == "Speaker 1"
    assert result[0]["phrase_text"] == "valid block"
    assert len(calls) == 1
    assert calls[0][0] == 10000
    assert calls[0][1] == 11000


def test_process_subtitles_should_continue_after_empty_and_fully_clipped_blocks(
    tmp_path,
):
    processor = SubtitleProcessor()
    srt_content = """1
00:00:10,100 --> 00:00:10,700
Speaker 1: first valid

2
00:00:10,700 --> 00:00:11,000
Speaker 2:

3
00:00:09,999 --> 00:00:10,001
Speaker 3: one two three four five six seven

4
00:00:11,100 --> 00:00:11,700
Speaker 4: second valid
"""

    srt_file = tmp_path / "continue.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    ass_file = tmp_path / "continue.ass"

    result = processor.process_subtitles(str(srt_file), TimeInterval(10.0, 12.0), str(ass_file))

    assert [segment["speaker"] for segment in result] == ["Speaker 1", "Speaker 4"]
    assert [segment["phrase_text"] for segment in result] == [
        "first valid",
        "second valid",
    ]


def test_process_subtitles_should_keep_1ms_words_and_clip_to_interval_duration(
    tmp_path,
):
    processor = SubtitleProcessor()
    srt_content = """1
00:00:10,000 --> 00:00:10,001
Speaker 1: tiny

2
00:00:11,000 --> 00:00:13,000
Speaker 2: clipped
"""

    srt_file = tmp_path / "clip.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    ass_file = tmp_path / "clip.ass"

    result = processor.process_subtitles(str(srt_file), TimeInterval(10.0, 12.0), str(ass_file))

    assert len(result) == 2
    assert result[0]["phrase_text"] == "tiny"
    assert result[0]["start_ms"] == 0
    assert result[0]["end_ms"] == 1
    assert result[1]["phrase_text"] == "clipped"
    assert result[1]["start_ms"] == 1000
    assert result[1]["end_ms"] == 2000


def test_process_subtitles_should_keep_phrase_order_across_multiple_groups(tmp_path):
    processor = SubtitleProcessor()
    words = [f"w{i}" for i in range(1, 19)]
    srt_content = f"1\n00:00:10,000 --> 00:00:28,000\nSpeaker 5: {' '.join(words)}\n"

    srt_file = tmp_path / "phrases.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    ass_file = tmp_path / "phrases.ass"

    result = processor.process_subtitles(str(srt_file), TimeInterval(10.0, 30.0), str(ass_file))

    assert len(result) == 3
    assert result[0]["phrase_text"] == "w1 w2 w3 w4 w5 w6"
    assert result[1]["phrase_text"] == "w7 w8 w9 w10 w11 w12"
    assert result[2]["phrase_text"] == "w13 w14 w15 w16 w17 w18"
    assert [(segment["start_ms"], segment["end_ms"]) for segment in result] == [
        (0, 6000),
        (6000, 12000),
        (12000, 18000),
    ]


def test_write_ass_file_should_use_exact_config_keys_and_dialogue_format(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "exact.ass"

    def get_setting(_self, key, _default):
        values = {
            "font_name": "ExactFont",
            "font_size": 100,
            "base_color_hex": "#123456",
            "active_border_color_hex": "#654321",
            "y_position": 777,
        }
        return values.get(key, f"UNEXPECTED::{key}")

    monkeypatch.setattr("src.infrastructure.config.ConfigManager.get_subtitle_setting", get_setting)
    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_brand_colors",
        lambda _self: ["#112233", "#abcdef", "#445566"],
    )
    monkeypatch.setattr("random.choice", lambda seq: seq[1])

    processor._write_ass_file(_make_segment(["Alpha"], step_ms=500), str(output_file))
    content = output_file.read_text(encoding="utf-8")

    expected = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: BaseLayer,ExactFont,100,&H563412&,&H000000FF,&H00000000,"
        "&H80000000,-1,0,0,0,100,100,0,0,1,6,3,5,10,10,250,1\n"
        "Style: ActiveLayer,ExactFont,100,&H332211&,&H000000FF,&H214365&,"
        "&H80000000,-1,0,0,0,100,100,0,0,1,8,3,5,10,10,250,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:00.50,BaseLayer,,0,0,0,,{\\an5\\pos(540,777)}Alpha\n"
        "Dialogue: 1,0:00:00.00,0:00:00.50,ActiveLayer,,0,0,0,,"
        "{\\c&Hefcdab&\\an5\\pos(540,777)\\t(0,120,\\fscx120\\fscy120)}Alpha\n"
    )
    assert content == expected


def test_write_ass_file_should_use_defaults_when_settings_are_missing(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "defaults.ass"

    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_subtitle_setting",
        lambda _self, _key, default: default,
    )
    monkeypatch.setattr("src.infrastructure.config.ConfigManager.get_brand_colors", lambda _self: [])

    call_index = {"value": 0}

    def cycle_choice(seq):
        item = seq[call_index["value"] % len(seq)]
        call_index["value"] += 1
        return item

    monkeypatch.setattr("random.choice", cycle_choice)

    processor._write_ass_file(_make_segment(["one", "two", "three"], step_ms=500), str(output_file))
    content = output_file.read_text(encoding="utf-8")

    assert "Style: BaseLayer,Montserrat,85,&HFFFFFF&," in content
    assert "Style: ActiveLayer,Montserrat,85,&Hfff426&,&H000000FF,&H000000&," in content
    assert "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n" in content
    assert "\\c&Hfff426&" in content
    assert "\\c&H8e1be6&" in content
    assert "\\c&H02ffd1&" in content
    assert "{\\an5\\pos(" in content
    assert ",1050)}" in content


def test_write_ass_file_should_use_configured_brand_palette_without_fallback(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "palette.ass"

    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_subtitle_setting",
        lambda _self, _key, default: default,
    )
    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_brand_colors",
        lambda _self: ["#010203"],
    )
    monkeypatch.setattr("random.choice", lambda seq: seq[0])

    processor._write_ass_file(_make_segment(["brand"], step_ms=500), str(output_file))
    content = output_file.read_text(encoding="utf-8")

    assert "Style: ActiveLayer,Montserrat,85,&H030201&," in content
    assert "\\c&H030201&" in content


def test_write_ass_file_should_use_white_active_default_for_truthy_empty_palette(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "truthy-empty.ass"

    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_subtitle_setting",
        lambda _self, _key, default: default,
    )
    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_brand_colors",
        lambda _self: TruthyEmptyColors(),
    )

    processor._write_ass_file([], str(output_file))
    content = output_file.read_text(encoding="utf-8")

    assert "Style: ActiveLayer,Montserrat,85,&HFFFFFF&," in content


def test_write_ass_file_should_use_expected_active_border_default_literal(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "active-border-default.ass"

    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_subtitle_setting",
        lambda _self, _key, default: default,
    )
    monkeypatch.setattr("src.infrastructure.config.ConfigManager.get_brand_colors", lambda _self: [])
    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.hex_to_ass_color",
        staticmethod(lambda value: f"ASS::{value}"),
    )

    processor._write_ass_file([], str(output_file))
    content = output_file.read_text(encoding="utf-8")

    assert "ASS::#000000" in content
    assert "ASS::XX#000000XX" not in content


def test_write_ass_file_should_keep_words_on_same_line_at_exact_threshold(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "threshold-850.ass"

    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_subtitle_setting",
        lambda _self, _key, default: default,
    )
    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_brand_colors",
        lambda _self: ["#26f4ff"],
    )
    monkeypatch.setattr("random.choice", lambda seq: seq[0])

    widths = {" ": 50, "W1": 300, "W2": 500}
    monkeypatch.setattr(processor, "_get_text_width", lambda text, _size: widths[text])

    processor._write_ass_file(_make_segment(["W1", "W2"], step_ms=500), str(output_file))
    content = output_file.read_text(encoding="utf-8")

    assert "{\\an5\\pos(265,1050)}W1" in content
    assert "{\\an5\\pos(715,1050)}W2" in content


def test_write_ass_file_should_wrap_at_width_851(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "threshold-851.ass"

    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_subtitle_setting",
        lambda _self, _key, default: default,
    )
    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_brand_colors",
        lambda _self: ["#26f4ff"],
    )
    monkeypatch.setattr("random.choice", lambda seq: seq[0])

    widths = {" ": 50, "W1": 400, "W2": 401}
    monkeypatch.setattr(processor, "_get_text_width", lambda text, _size: widths[text])

    processor._write_ass_file(_make_segment(["W1", "W2"], step_ms=500), str(output_file))
    content = output_file.read_text(encoding="utf-8")

    assert "{\\an5\\pos(540,999)}W1" in content
    assert "{\\an5\\pos(540,1101)}W2" in content


def test_write_ass_file_should_keep_state_after_line_wrap(tmp_path, monkeypatch):
    processor = SubtitleProcessor()
    output_file = tmp_path / "line-state.ass"

    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_subtitle_setting",
        lambda _self, _key, default: default,
    )
    monkeypatch.setattr(
        "src.infrastructure.config.ConfigManager.get_brand_colors",
        lambda _self: ["#26f4ff"],
    )
    monkeypatch.setattr("random.choice", lambda seq: seq[0])

    widths = {" ": 50, "W1": 400, "W2": 450, "W3": 100}
    monkeypatch.setattr(processor, "_get_text_width", lambda text, _size: widths[text])

    processor._write_ass_file(_make_segment(["W1", "W2", "W3"], step_ms=500), str(output_file))
    content = output_file.read_text(encoding="utf-8")

    assert "{\\an5\\pos(540,999)}W1" in content
    assert "{\\an5\\pos(465,1101)}W2" in content
    assert "{\\an5\\pos(790,1101)}W3" in content

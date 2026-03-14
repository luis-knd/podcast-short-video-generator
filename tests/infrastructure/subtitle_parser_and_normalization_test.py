from src.infrastructure.subtitles.normalization import normalize_token
from src.infrastructure.subtitles.parser import SubtitleParser


def test_normalize_token_collapses_spaces_and_strips_supported_punctuation():
    assert normalize_token("  HELLO,\n\nWORLD!  ") == "hello, world"
    assert normalize_token('"(Test)"') == "test"
    assert normalize_token("[ spaced ]") == " spaced "
    assert normalize_token("XhelloX") == "xhellox"


def test_subtitle_parser_preserves_speaker_contract_and_skips_invalid_blocks(tmp_path):
    srt_file = tmp_path / "sample.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,000\n"
        "Speaker 2: First line\n"
        "\n"
        "2\n"
        "00:00:01,000 --> 00:00:02,000\n"
        "Line one\n"
        "Line two\n"
        "\n"
        "3\n"
        "invalid line\n"
        "Should be skipped\n"
        "\n"
        "4\n"
        "00:00:03,000 --> 00:00:04,000\n"
        "Speaker 4:\n",
        encoding="utf-8",
    )

    parser = SubtitleParser()
    cues = parser.parse(str(srt_file))

    assert SubtitleParser.TIME_RANGE_PATTERN.pattern == (r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})")
    assert SubtitleParser.SPEAKER_PATTERN.pattern == r"^(Speaker \d+):?\s*(.*)"
    assert parser.parse_time_to_ms("00:00:03,250") == 3250
    assert [cue.cue_id for cue in cues] == ["cue-1", "cue-2"]
    assert cues[0].speaker == "Speaker 2"
    assert cues[0].text == "First line"
    assert cues[1].speaker == "Speaker Unknown"
    assert cues[1].text == "Line one Line two"


def test_subtitle_parser_continue_skips_invalid_block_without_stopping_subsequent_blocks(tmp_path):
    """Kills mutmut_36: continue → break — remaining valid blocks must still be parsed."""
    srt_file = tmp_path / "multi.srt"
    srt_file.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:01,000\n"
        "First valid block\n"
        "\n"
        "2\n"
        "invalid line\n"
        "should be skipped\n"
        "\n"
        "3\n"
        "00:00:02,000 --> 00:00:03,000\n"
        "Third valid block\n"
        "\n"
        "4\n"
        "00:00:04,000 --> 00:00:05,000\n"
        "Fourth valid block\n",
        encoding="utf-8",
    )

    parser = SubtitleParser()
    cues = parser.parse(str(srt_file))

    # Blocks 1, 3, and 4 must all be parsed; block 2 is skipped but must not stop parsing
    cue_texts = [cue.text for cue in cues]
    assert "First valid block" in cue_texts
    assert "Third valid block" in cue_texts
    assert "Fourth valid block" in cue_texts
    assert len(cues) == 3

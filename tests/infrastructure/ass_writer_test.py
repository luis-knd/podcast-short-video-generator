import os
import tempfile
from unittest.mock import MagicMock, patch

from src.infrastructure.subtitles.ass_writer import AssWriter

_CONFIG_PATCH = "src.infrastructure.config.ConfigManager"


def _mock_config_class():
    instance = MagicMock()
    instance.get_subtitle_setting.side_effect = lambda key, default=None: default
    instance.get_brand_colors.return_value = ["#26f4ff"]
    mock_cls = MagicMock(return_value=instance)
    mock_cls.hex_to_ass_color = staticmethod(lambda h: "&H" + h.lstrip("#").upper() + "&")
    return mock_cls


def _minimal_segment(start_ms: int = 0, end_ms: int = 1000) -> dict:
    return {
        "speaker": "Speaker 1",
        "phrase_text": "hello world",
        "start_ms": start_ms,
        "end_ms": end_ms,
        "words": [
            {"text": "hello", "start": start_ms, "end": start_ms + 500},
            {"text": "world", "start": start_ms + 500, "end": end_ms},
        ],
    }


def _segment(words: list[tuple[str, int, int]], start_ms: int, end_ms: int) -> dict:
    return {
        "speaker": "Speaker 1",
        "phrase_text": " ".join(word for word, _, _ in words),
        "start_ms": start_ms,
        "end_ms": end_ms,
        "words": [{"text": word, "start": word_start, "end": word_end} for word, word_start, word_end in words],
    }


def test_ass_writer_format_time_fallback_uses_format_ms_to_ass_time():
    writer = AssWriter()
    called_with: list[int] = []

    def spy_format(ms: int) -> str:
        called_with.append(ms)
        return AssWriter.format_ms_to_ass_time(ms)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False) as f:
        out_path = f.name

    try:
        with patch(_CONFIG_PATCH, _mock_config_class()):
            writer.write([_minimal_segment(1000, 2000)], out_path, format_time=spy_format)

        assert len(called_with) > 0

        with patch(_CONFIG_PATCH, _mock_config_class()):
            writer.write([_minimal_segment(500, 1500)], out_path)

        with open(out_path, encoding="utf-8") as fh:
            assert "[Script Info]" in fh.read()
    finally:
        os.remove(out_path)


def test_ass_writer_write_produces_valid_utf8_file():
    writer = AssWriter()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False) as f:
        out_path = f.name

    try:
        with patch(_CONFIG_PATCH, _mock_config_class()):
            writer.write([_minimal_segment()], out_path)

        with open(out_path, encoding="utf-8") as fh:
            content = fh.read()

        assert "PlayResX: 1080" in content
        assert "PlayResY: 1920" in content
    finally:
        os.remove(out_path)


def test_ass_writer_write_output_is_decodable_as_utf8():
    writer = AssWriter()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ass", delete=False) as f:
        out_path = f.name

    try:
        with patch(_CONFIG_PATCH, _mock_config_class()):
            writer.write([_minimal_segment()], out_path)

        with open(out_path, "rb") as fh:
            raw = fh.read()
        decoded = raw.decode("utf-8")
        assert "ScriptType: v4.00+" in decoded
    finally:
        os.remove(out_path)


def test_ass_writer_does_not_keep_base_layer_for_single_active_word(tmp_path):
    writer = AssWriter()
    out_path = tmp_path / "single-word.ass"
    segment = _segment([("Alpha", 0, 500)], start_ms=0, end_ms=500)

    with patch(_CONFIG_PATCH, _mock_config_class()):
        writer.write([segment], str(out_path))

    content = out_path.read_text(encoding="utf-8")

    assert "Dialogue: 0,0:00:00.00,0:00:00.50,BaseLayer,,0,0,0,,{\\an5\\pos(540,1050)}Alpha" not in content
    assert "Dialogue: 1,0:00:00.00,0:00:00.50,ActiveLayer" in content


def test_ass_writer_splits_base_layer_before_and_after_active_window(tmp_path):
    writer = AssWriter()
    out_path = tmp_path / "middle-word.ass"
    segment = _segment(
        [("first", 0, 500), ("middle", 500, 1000), ("last", 1000, 1500)],
        start_ms=0,
        end_ms=1500,
    )

    with patch(_CONFIG_PATCH, _mock_config_class()):
        writer.write([segment], str(out_path))

    content = out_path.read_text(encoding="utf-8")

    assert "Dialogue: 0,0:00:00.00,0:00:01.50,BaseLayer" not in content
    assert "Dialogue: 0,0:00:00.00,0:00:00.50,BaseLayer,,0,0,0,,{\\an5\\pos(" in content
    assert "Dialogue: 0,0:00:01.00,0:00:01.50,BaseLayer,,0,0,0,,{\\an5\\pos(" in content
    assert content.count("}middle\n") == 3
    assert "Dialogue: 1,0:00:00.50,0:00:01.00,ActiveLayer" in content

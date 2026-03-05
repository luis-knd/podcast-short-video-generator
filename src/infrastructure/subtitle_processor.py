import re
from typing import Any

from src.domain.value_objects import TimeInterval


class SubtitleProcessor:
    def __init__(self):
        pass

    @staticmethod
    def _parse_time_to_ms(time_str: str) -> int:
        """Parses SRT time format 00:00:00,000 to milliseconds."""
        time_str = time_str.strip()
        h, m, s_ms = time_str.split(":")
        s, ms = s_ms.split(",")
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)

    @staticmethod
    def _format_ms_to_ass_time(ms: int) -> str:
        """Formats milliseconds to ASS time format H:MM:SS.cs"""
        ms = int(ms)
        h = ms // 3600000
        ms %= 3600000
        m = ms // 60000
        ms %= 60000
        s = ms // 1000
        cs = (ms % 1000) // 10  # Centiseconds
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def _calculate_chunk_times(
        chunks: list[str], start_ms: int, end_ms: int
    ) -> list[dict[str, Any]]:
        """Calculates proportionally distributed start/end times for words based on chunk length."""
        total_duration = end_ms - start_ms
        total_words = sum(len(c.split()) for c in chunks)

        if total_words == 0:
            return []

        time_per_word = total_duration / total_words

        timed_chunks = []
        current_time = start_ms

        for chunk in chunks:
            word_count = len(chunk.split())
            chunk_duration = int(word_count * time_per_word)
            timed_chunks.append(
                {
                    "text": chunk,
                    "start": int(current_time),
                    "end": int(current_time + chunk_duration),
                }
            )
            current_time += chunk_duration

        return timed_chunks

    @staticmethod
    def _get_text_width(text: str, font_size: int) -> int:
        """Approximates the pixel width of a string based on font size."""
        width = 0
        base_char_width = int(font_size * 0.48)
        for char in text:
            if char == " ":
                width += int(font_size * 0.25)
            elif char in "il1!.,;:|":
                width += int(base_char_width * 0.4)
            elif char in "wmWM":
                width += int(base_char_width * 1.5)
            elif char in "tfjI":
                width += int(base_char_width * 0.6)
            elif char.isupper():
                width += int(base_char_width * 1.1)
            else:
                width += base_char_width
        return width

    @staticmethod
    def _group_into_phrases(
        words: list[str], words_per_phrase: int = 4
    ) -> list[list[str]]:
        phrases = []
        for i in range(0, len(words), words_per_phrase):
            phrases.append(words[i : i + words_per_phrase])
        return phrases

    def process_subtitles(
        self, srt_filepath: str, interval: TimeInterval, output_ass_filepath: str
    ) -> list[dict[str, Any]]:
        """
        Parses an SRT file, filters for a time interval, shifts times,
        groups into phrases, and generates progressive karaoke ASS.
        """
        interval_start_ms = interval.start_seconds * 1000
        interval_end_ms = interval.end_seconds * 1000

        with open(srt_filepath, encoding="utf-8") as f:
            content = f.read()

        blocks = content.strip().split("\n\n")
        segments = []

        for block in blocks:
            lines = block.split("\n")
            if len(lines) < 3:
                continue

            time_line = lines[1]
            text_lines = lines[2:]
            text = " ".join(text_lines)

            # Parse time
            match = re.search(
                r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", time_line
            )
            if not match:
                continue

            start_ms = self._parse_time_to_ms(match.group(1))
            end_ms = self._parse_time_to_ms(match.group(2))

            # Filter by interval
            if end_ms <= interval_start_ms or start_ms >= interval_end_ms:
                continue

            # Parse speaker
            speaker = "Speaker Unknown"
            speaker_match = re.match(r"^(Speaker \d+):?\s*(.*)", text)
            if speaker_match:
                speaker = speaker_match.group(1)
                text = speaker_match.group(2).strip()

            # Shift time to be relative to the start of the short
            words = text.split()
            if not words:
                continue

            word_times = self._calculate_chunk_times(words, start_ms, end_ms)

            valid_word_times = []
            for wt in word_times:
                w_start = wt["start"] - interval_start_ms
                w_end = wt["end"] - interval_start_ms

                if w_end <= 0 or w_start >= (interval_end_ms - interval_start_ms):
                    continue

                wt["start"] = max(0, w_start)
                wt["end"] = min(interval_end_ms - interval_start_ms, w_end)
                valid_word_times.append(wt)

            if not valid_word_times:
                continue

            valid_words = [wt["text"] for wt in valid_word_times]
            phrases = self._group_into_phrases(valid_words, words_per_phrase=6)

            word_idx = 0
            for phrase_words in phrases:
                phrase_word_times = valid_word_times[
                    word_idx : word_idx + len(phrase_words)
                ]
                word_idx += len(phrase_words)

                phrase_start = phrase_word_times[0]["start"]
                phrase_end = phrase_word_times[-1]["end"]
                phrase_text = " ".join(phrase_words)

                segments.append(
                    {
                        "speaker": speaker,
                        "phrase_text": phrase_text,
                        "start_ms": phrase_start,
                        "end_ms": phrase_end,
                        "words": phrase_word_times,
                    }
                )

        self._write_ass_file(segments, output_ass_filepath)
        return segments

    def _write_ass_file(self, segments: list[dict[str, Any]], output_filepath: str):
        """Generates progressive word-by-word karaoke ASS."""
        import random

        from src.infrastructure.config import ConfigManager

        config = ConfigManager()
        font_name = config.get_subtitle_setting("font_name", "Montserrat")
        font_size = config.get_subtitle_setting("font_size", 85)
        base_color = ConfigManager.hex_to_ass_color(
            config.get_subtitle_setting("base_color_hex", "#FFFFFF")
        )

        # Get brand colors array
        brand_colors = config.get_brand_colors()
        if not brand_colors:
            brand_colors = ["#26f4ff", "#e61b8e", "#d1ff02"]
        ass_colors = [ConfigManager.hex_to_ass_color(c) for c in brand_colors]
        default_active_color = ass_colors[0] if ass_colors else "&HFFFFFF&"
        active_border = ConfigManager.hex_to_ass_color(
            config.get_subtitle_setting("active_border_color_hex", "#000000")
        )
        y_pos = config.get_subtitle_setting("y_position", 1050)

        ass_header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: BaseLayer,{font_name},{font_size},{base_color},"
            f"&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,5,10,10,250,1\n"
            f"Style: ActiveLayer,{font_name},{font_size},{default_active_color},"
            f"&H000000FF,{active_border},&H80000000,-1,0,0,0,100,100,0,0,1,8,3,5,10,10,250,1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        with open(output_filepath, "w", encoding="utf-8") as f:
            f.write(ass_header)

            for segment in segments:
                phrase_start = self._format_ms_to_ass_time(segment["start_ms"])
                phrase_end = self._format_ms_to_ass_time(segment["end_ms"])

                # Calculate phrase width to center it appropriately
                space_width = self._get_text_width(" ", font_size)
                max_width = 850
                lines = []
                current_line = []
                current_line_width = 0

                for w in segment["words"]:
                    w_text = w["text"]
                    word_width = self._get_text_width(w_text, font_size)

                    if (
                        current_line_width + space_width + word_width > max_width
                        and current_line
                    ):
                        lines.append(current_line)
                        current_line = [w]
                        current_line_width = word_width
                    else:
                        current_line.append(w)
                        if current_line_width == 0:
                            current_line_width = word_width
                        else:
                            current_line_width += space_width + word_width

                if current_line:
                    lines.append(current_line)

                num_lines = len(lines)
                line_height = int(font_size * 1.2)
                start_y = y_pos - (line_height * (num_lines - 1)) / 2

                for i, line_words in enumerate(lines):
                    line_y = int(start_y + i * line_height)
                    line_width = sum(
                        self._get_text_width(w["text"], font_size) for w in line_words
                    ) + space_width * (len(line_words) - 1)
                    current_x = 540 - (line_width / 2)

                    for w in line_words:
                        w_start = self._format_ms_to_ass_time(w["start"])
                        w_end = self._format_ms_to_ass_time(w["end"])
                        w_text = w["text"]

                        word_width = self._get_text_width(w_text, font_size)
                        center_x = int(current_x + (word_width / 2))

                        # Layer 0: Static grey base word (lives for the entire phrase duration)
                        f.write(
                            f"Dialogue: 0,{phrase_start},{phrase_end},"
                            f"BaseLayer,,0,0,0,,"
                            f"{{\\an5\\pos({center_x},{line_y})}}{w_text}\n"
                        )

                        random_color = random.choice(ass_colors)
                        # Layer 1: Active word pop-in and glow overlays (lives only while the word is spoken)
                        f.write(
                            f"Dialogue: 1,{w_start},{w_end},ActiveLayer,,0,0,0,,"
                            f"{{\\c{random_color}\\an5\\pos({center_x},{line_y})"
                            f"\\t(0,120,\\fscx120\\fscy120)}}{w_text}\n"
                        )

                        current_x += word_width + space_width

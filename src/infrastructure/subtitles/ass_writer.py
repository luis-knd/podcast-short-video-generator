from typing import Any


class AssWriter:
    @staticmethod
    def format_ms_to_ass_time(ms: int) -> str:
        ms = int(ms)
        h = ms // 3600000
        ms %= 3600000
        m = ms // 60000
        ms %= 60000
        s = ms // 1000
        cs = (ms % 1000) // 10
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @staticmethod
    def get_text_width(text: str, font_size: int) -> int:
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
    def _build_base_intervals(
        phrase_start_ms: int,
        phrase_end_ms: int,
        word_start_ms: int,
        word_end_ms: int,
    ) -> list[tuple[int, int]]:
        intervals: list[tuple[int, int]] = []

        before_start = phrase_start_ms
        before_end = min(word_start_ms, phrase_end_ms)
        if before_end > before_start:
            intervals.append((before_start, before_end))

        after_start = max(word_end_ms, phrase_start_ms)
        after_end = phrase_end_ms
        if after_end > after_start:
            intervals.append((after_start, after_end))

        return intervals

    @staticmethod
    def _split_words_into_lines(
        words: list[dict[str, Any]],
        font_size: int,
        get_text_width,
        max_width: int,
        space_width: int,
    ) -> list[list[dict[str, Any]]]:
        lines: list[list[dict[str, Any]]] = []
        current_line: list[dict[str, Any]] = []
        current_line_width = 0

        for word in words:
            word_text = word["text"]
            word_width = get_text_width(word_text, font_size)

            if current_line_width + space_width + word_width > max_width and current_line:
                lines.append(current_line)
                current_line = [word]
                current_line_width = word_width
                continue

            current_line.append(word)
            if current_line_width == 0:
                current_line_width = word_width
                continue

            current_line_width += space_width + word_width

        if current_line:
            lines.append(current_line)

        return lines

    @staticmethod
    def _write_base_dialogues(
        ass_file,
        format_time,
        center_x: int,
        line_y: int,
        word_text: str,
        phrase_start_ms: int,
        phrase_end_ms: int,
        word_start_ms: int,
        word_end_ms: int,
    ):
        for base_start_ms, base_end_ms in AssWriter._build_base_intervals(
            phrase_start_ms,
            phrase_end_ms,
            word_start_ms,
            word_end_ms,
        ):
            ass_file.write(
                f"Dialogue: 0,{format_time(base_start_ms)},{format_time(base_end_ms)},"
                f"BaseLayer,,0,0,0,,"
                f"{{\\an5\\pos({center_x},{line_y})}}{word_text}\n"
            )

    @staticmethod
    def _write_active_dialogue(
        ass_file,
        center_x: int,
        line_y: int,
        random_color: str,
        word_start: str,
        word_end: str,
        word_text: str,
    ):
        ass_file.write(
            f"Dialogue: 1,{word_start},{word_end},ActiveLayer,,0,0,0,,"
            f"{{\\c{random_color}\\an5\\pos({center_x},{line_y})"
            f"\\t(0,120,\\fscx120\\fscy120)}}{word_text}\n"
        )

    def write(
        self,
        segments: list[dict[str, Any]],
        output_filepath: str,
        format_time=None,
        get_text_width=None,
    ):
        import random

        from src.infrastructure.config import ConfigManager

        format_time = format_time or self.format_ms_to_ass_time
        get_text_width = get_text_width or self.get_text_width

        config = ConfigManager()
        font_name = config.get_subtitle_setting("font_name", "Montserrat")
        font_size = config.get_subtitle_setting("font_size", 85)
        base_color = ConfigManager.hex_to_ass_color(config.get_subtitle_setting("base_color_hex", "#FFFFFF"))
        brand_colors = config.get_brand_colors()
        if not brand_colors:
            brand_colors = ["#26f4ff", "#e61b8e", "#d1ff02"]
        ass_colors = [ConfigManager.hex_to_ass_color(color) for color in brand_colors]
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

        with open(output_filepath, "w", encoding="utf-8") as ass_file:
            ass_file.write(ass_header)

            for segment in segments:
                phrase_start_ms = int(segment["start_ms"])
                phrase_end_ms = int(segment["end_ms"])

                space_width = get_text_width(" ", font_size)
                max_width = 850
                lines = self._split_words_into_lines(
                    segment["words"],
                    font_size,
                    get_text_width,
                    max_width,
                    space_width,
                )

                num_lines = len(lines)
                line_height = int(font_size * 1.2)
                start_y = y_pos - (line_height * (num_lines - 1)) / 2

                for line_index, line_words in enumerate(lines):
                    line_y = int(start_y + line_index * line_height)
                    line_width = sum(get_text_width(word["text"], font_size) for word in line_words) + space_width * (
                        len(line_words) - 1
                    )
                    current_x = 540 - (line_width / 2)

                    for word in line_words:
                        word_start_ms = int(word["start"])
                        word_end_ms = int(word["end"])
                        word_start = format_time(word_start_ms)
                        word_end = format_time(word_end_ms)
                        word_text = word["text"]
                        word_width = get_text_width(word_text, font_size)
                        center_x = int(current_x + (word_width / 2))

                        self._write_base_dialogues(
                            ass_file,
                            format_time,
                            center_x,
                            line_y,
                            word_text,
                            phrase_start_ms,
                            phrase_end_ms,
                            word_start_ms,
                            word_end_ms,
                        )

                        random_color = random.choice(ass_colors)
                        self._write_active_dialogue(
                            ass_file,
                            center_x,
                            line_y,
                            random_color,
                            word_start,
                            word_end,
                            word_text,
                        )

                        current_x += word_width + space_width

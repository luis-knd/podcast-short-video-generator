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
                phrase_start = format_time(segment["start_ms"])
                phrase_end = format_time(segment["end_ms"])

                space_width = get_text_width(" ", font_size)
                max_width = 850
                lines = []
                current_line = []
                current_line_width = 0

                for word in segment["words"]:
                    word_text = word["text"]
                    word_width = get_text_width(word_text, font_size)

                    if current_line_width + space_width + word_width > max_width and current_line:
                        lines.append(current_line)
                        current_line = [word]
                        current_line_width = word_width
                    else:
                        current_line.append(word)
                        if current_line_width == 0:
                            current_line_width = word_width
                        else:
                            current_line_width += space_width + word_width

                if current_line:
                    lines.append(current_line)

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
                        word_start = format_time(word["start"])
                        word_end = format_time(word["end"])
                        word_text = word["text"]
                        word_width = get_text_width(word_text, font_size)
                        center_x = int(current_x + (word_width / 2))

                        ass_file.write(
                            f"Dialogue: 0,{phrase_start},{phrase_end},"
                            f"BaseLayer,,0,0,0,,"
                            f"{{\\an5\\pos({center_x},{line_y})}}{word_text}\n"
                        )

                        random_color = random.choice(ass_colors)
                        ass_file.write(
                            f"Dialogue: 1,{word_start},{word_end},ActiveLayer,,0,0,0,,"
                            f"{{\\c{random_color}\\an5\\pos({center_x},{line_y})"
                            f"\\t(0,120,\\fscx120\\fscy120)}}{word_text}\n"
                        )

                        current_x += word_width + space_width

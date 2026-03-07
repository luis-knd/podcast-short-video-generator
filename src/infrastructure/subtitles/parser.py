import re

from src.domain.subtitle_models import SubtitleCue


class SubtitleParser:
    TIME_RANGE_PATTERN = re.compile(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})")
    SPEAKER_PATTERN = re.compile(r"^(Speaker \d+):?\s*(.*)")

    @staticmethod
    def parse_time_to_ms(time_str: str) -> int:
        time_str = time_str.strip()
        h, m, s_ms = time_str.split(":")
        s, ms = s_ms.split(",")
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)

    def parse(self, srt_filepath: str) -> list[SubtitleCue]:
        with open(srt_filepath, encoding="utf-8") as srt_file:
            content = srt_file.read()

        if not content.strip():
            return []

        blocks = re.split(r"\r?\n\r?\n", content.strip())
        cues: list[SubtitleCue] = []

        for cue_index, block in enumerate(blocks, start=1):
            lines = block.splitlines()
            if len(lines) < 3:
                continue

            match = self.TIME_RANGE_PATTERN.search(lines[1])
            if not match:
                continue

            text = " ".join(line.strip() for line in lines[2:]).strip()
            if not text:
                continue

            speaker = "Speaker Unknown"
            speaker_match = self.SPEAKER_PATTERN.match(text)
            if speaker_match:
                speaker = speaker_match.group(1)
                text = speaker_match.group(2).strip()

            if not text:
                continue

            cues.append(
                SubtitleCue(
                    cue_id=f"cue-{cue_index}",
                    speaker=speaker,
                    text=text,
                    start_ms=self.parse_time_to_ms(match.group(1)),
                    end_ms=self.parse_time_to_ms(match.group(2)),
                )
            )

        return cues

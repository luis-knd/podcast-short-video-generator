import json
import os


class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.config = cls._load_config()
        return cls._instance

    @staticmethod
    def _load_config() -> dict:
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                return json.load(f)
        return {}

    def get_color(self, name: str, default: str) -> str:
        colors = self.config.get("brand_colors", {})
        if isinstance(colors, dict):
            return colors.get(name, default)
        return default

    def get_brand_colors(self) -> list[str]:
        colors = self.config.get("brand_colors", [])
        if isinstance(colors, dict):
            return list(colors.values())
        return colors

    def get_subtitle_setting(self, name: str, default: any) -> any:
        return self.config.get("subtitles", {}).get(name, default)

    def get_alignment_setting(self, name: str, default: any) -> any:
        return self.config.get("alignment", {}).get(name, default)

    @staticmethod
    def hex_to_ass_color(hex_color: str) -> str:
        """Converts #RRGGBB to &HBBGGRR& ASS format"""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H{b}{g}{r}&"
        return "&H000000&"

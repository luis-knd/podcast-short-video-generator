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
        ConfigManager._load_env_file()
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def _load_env_file():
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        if not os.path.exists(env_path):
            return

        with open(env_path, encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

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

    def get_broll_setting(self, name: str, default: any) -> any:
        return self.config.get("broll", {}).get(name, default)

    def get_interval_generation_setting(self, name: str, default: any) -> any:
        return self.config.get("interval_generation", {}).get(name, default)

    @staticmethod
    def hex_to_ass_color(hex_color: str) -> str:
        """Converts #RRGGBB to &HBBGGRR& ASS format"""
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
            return f"&H{b}{g}{r}&"
        return "&H000000&"

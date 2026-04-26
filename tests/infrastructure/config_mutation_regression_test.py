from unittest.mock import patch

from src.infrastructure.config import ConfigManager


def test_config_manager_returns_default_interval_generation_value_when_section_or_key_is_missing():
    with patch("os.path.exists", return_value=False):
        manager = ConfigManager()
        manager.config = {}
        assert manager.get_interval_generation_setting("provider", "auto") == "auto"

        manager.config = {"interval_generation": {"provider": "gemini", "target_count": 11}}
        assert manager.get_interval_generation_setting("provider", "auto") == "gemini"
        assert manager.get_interval_generation_setting("target_count", 3) == 11
        assert manager.get_interval_generation_setting("missing", "fallback") == "fallback"


def test_config_manager_returns_safe_defaults_when_sections_are_missing():
    with patch("os.path.exists", return_value=False):
        manager = ConfigManager()
        manager.config = {}

        assert manager.get_brand_colors() == []
        assert manager.get_alignment_setting("backend", "faster_whisper") == "faster_whisper"
        assert manager.get_broll_setting("enabled", False) is False

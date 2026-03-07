import importlib
import json
from unittest.mock import mock_open, patch

import pytest

from src.infrastructure.config import ConfigManager


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton instance before and after each test."""
    ConfigManager._instance = None
    yield
    ConfigManager._instance = None


def test_singleton_behavior():
    with patch("os.path.exists", return_value=False):
        c1 = ConfigManager()
        c2 = ConfigManager()
        assert c1 is c2


def test_load_config_file_exists():
    mock_json = '{"brand_colors": {"primary": "#FF0000"}}'
    with (
        patch("os.path.exists", return_value=True) as mock_exists,
        patch("builtins.open", mock_open(read_data=mock_json)),
        patch("json.load", return_value=json.loads(mock_json)),
    ):
        c = ConfigManager()
        assert c.config == {"brand_colors": {"primary": "#FF0000"}}
        # Ensure path is built correctly terminating in config.json
        called_path = mock_exists.call_args[0][0]
        assert called_path.endswith("config.json")
        assert ".." in called_path


def test_load_config_file_not_exists():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        assert c.config == {}


def test_get_color():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        c.config = {"brand_colors": {"primary": "#FF0000"}}
        assert c.get_color("primary", "#000000") == "#FF0000"
        assert c.get_color("secondary", "#FFFFFF") == "#FFFFFF"


def test_get_color_not_dict():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        c.config = {"brand_colors": ["#FF0000"]}
        assert c.get_color("primary", "#FFFFFF") == "#FFFFFF"


def test_get_brand_colors_dict():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        c.config = {"brand_colors": {"primary": "#FF0000", "secondary": "#00FF00"}}
        assert c.get_brand_colors() == ["#FF0000", "#00FF00"]


def test_get_brand_colors_list():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        c.config = {"brand_colors": ["#FF0000", "#00FF00"]}
        assert c.get_brand_colors() == ["#FF0000", "#00FF00"]


def test_get_subtitle_setting():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        c.config = {"subtitles": {"font": "Arial"}}
        assert c.get_subtitle_setting("font", "Roboto") == "Arial"
        assert c.get_subtitle_setting("size", 24) == 24

        c.config = {}
        assert c.get_subtitle_setting("font", "Roboto") == "Roboto"


def test_get_alignment_setting():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        c.config = {"alignment": {"enabled": False}}
        assert c.get_alignment_setting("enabled", True) is False
        assert c.get_alignment_setting("backend", "faster_whisper") == "faster_whisper"


def test_hex_to_ass_color():
    # Make sure staticmethod is used by calling on an instance
    c = ConfigManager()
    assert c.hex_to_ass_color("#FF0000") == "&H0000FF&"

    assert ConfigManager.hex_to_ass_color("#FF0000") == "&H0000FF&"
    assert ConfigManager.hex_to_ass_color("00FF00") == "&H00FF00&"
    assert ConfigManager.hex_to_ass_color("#0000FF") == "&HFF0000&"
    assert ConfigManager.hex_to_ass_color("#123456") == "&H563412&"

    # Needs to strip specifically '#'
    assert ConfigManager.hex_to_ass_color("XFF0000") == "&H000000&"

    # Invalid lengths
    assert ConfigManager.hex_to_ass_color("#FFF") == "&H000000&"
    assert ConfigManager.hex_to_ass_color("1234567") == "&H000000&"
    assert ConfigManager.hex_to_ass_color("") == "&H000000&"


def test_load_config_is_callable_from_instance():
    with patch("os.path.exists", return_value=False):
        c = ConfigManager()
        assert c._load_config() == {}


def test_hex_to_ass_color_reads_blue_component_with_stop_index_six():
    class SliceProbeHex:
        def __init__(self):
            self.seen_slices = []

        def lstrip(self, _char):
            return self

        def __len__(self):
            return 6

        def __getitem__(self, key):
            self.seen_slices.append(key)
            if isinstance(key, slice):
                if key.start == 0 and key.stop == 2:
                    return "AA"
                if key.start == 2 and key.stop == 4:
                    return "BB"
                if key.start == 4 and key.stop in (6, 7):
                    return "CC"
            raise AssertionError(f"Unexpected key access: {key!r}")

    probe = SliceProbeHex()
    result = ConfigManager.hex_to_ass_color(probe)

    assert result == "&HCCBBAA&"
    assert any(
        isinstance(slice_key, slice) and slice_key.start == 4 and slice_key.stop == 6 for slice_key in probe.seen_slices
    )


def test_config_manager_singleton_default_is_none_on_module_load():
    import src.infrastructure.config as config_module

    reloaded_module = importlib.reload(config_module)
    assert reloaded_module.ConfigManager._instance is None

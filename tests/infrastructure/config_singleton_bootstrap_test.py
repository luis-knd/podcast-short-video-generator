import importlib

import src.infrastructure.config as config_module


def test_config_manager_bootstrap_singleton_starts_as_none():
    reloaded_module = importlib.reload(config_module)
    assert reloaded_module.ConfigManager._instance is None

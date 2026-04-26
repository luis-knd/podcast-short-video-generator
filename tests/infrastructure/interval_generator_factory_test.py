import os

from src.infrastructure.subtitles.factory import IntervalGeneratorFactory
from src.infrastructure.subtitles.interval_generator import ViralSubtitleIntervalGenerator
from src.infrastructure.subtitles.llm_interval_generator import LlmSubtitleIntervalGenerator


class _StubConfig:
    def __init__(self, values: dict[str, object]):
        self.values = values

    def get_interval_generation_setting(self, name: str, default):
        return self.values.get(name, default)


def test_interval_generator_factory_uses_llm_when_api_key_is_available(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    config = _StubConfig(
        {
            "provider": "auto",
            "llm_model": "gemini-2.5-flash",
            "llm_timeout_seconds": 21,
            "llm_temperature": 0.1,
            "target_count": 9,
            "min_duration_ms": 19_000,
            "max_duration_ms": 40_000,
        }
    )

    resolution = IntervalGeneratorFactory.build(config=config, env=os.environ)

    assert isinstance(resolution.generator, LlmSubtitleIntervalGenerator)
    assert resolution.warning_message is None


def test_interval_generator_factory_falls_back_to_heuristic_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config = _StubConfig({"provider": "gemini"})

    resolution = IntervalGeneratorFactory.build(config=config, env=os.environ)

    assert isinstance(resolution.generator, ViralSubtitleIntervalGenerator)
    assert resolution.warning_message is not None
    assert "GEMINI_API_KEY" in resolution.warning_message


def test_interval_generator_factory_prefers_env_model_override_when_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "secret")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-env-override")
    config = _StubConfig(
        {
            "provider": "gemini",
            "llm_model": "gemini-config-value",
            "llm_timeout_seconds": 20,
            "llm_temperature": 0.2,
        }
    )

    resolution = IntervalGeneratorFactory.build(config=config, env=os.environ)

    assert isinstance(resolution.generator, LlmSubtitleIntervalGenerator)
    assert resolution.generator.llm_client.model == "gemini-env-override"

import os
from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike

from src.domain.ports import ISubtitleIntervalGenerator
from src.infrastructure.config import ConfigManager
from src.infrastructure.subtitles.interval_generator import ViralSubtitleIntervalGenerator
from src.infrastructure.subtitles.llm_interval_generator import (
    GeminiIntervalSelectionClient,
    LlmSubtitleIntervalGenerator,
)


@dataclass(frozen=True)
class IntervalGeneratorResolution:
    generator: ISubtitleIntervalGenerator
    warning_message: str | None = None
    info_message: str | None = None


class IntervalGeneratorFactory:
    SUPPORTED_LLM_PROVIDERS = frozenset({"auto", "gemini", "llm"})

    @staticmethod
    def build(
        config: ConfigManager | None = None,
        env: Mapping[str, str | PathLike[str]] | None = None,
    ) -> IntervalGeneratorResolution:
        effective_config = config or ConfigManager()
        effective_env = os.environ if env is None else env
        fallback_generator = ViralSubtitleIntervalGenerator()
        provider = str(effective_config.get_interval_generation_setting("provider", "auto")).strip().lower()
        if provider == "heuristic":
            return IntervalGeneratorResolution(
                generator=fallback_generator,
                info_message="Interval generation provider: heuristic.",
            )
        if provider not in IntervalGeneratorFactory.SUPPORTED_LLM_PROVIDERS:
            return IntervalGeneratorResolution(
                generator=fallback_generator,
                warning_message=(
                    "Warning: Unsupported interval_generation.provider value; "
                    "using heuristic interval selection instead."
                ),
                info_message="Interval generation provider: heuristic.",
            )

        api_key = str(effective_env.get("GEMINI_API_KEY", "")).strip()
        if not api_key:
            warning_message = None
            if provider != "auto":
                warning_message = (
                    "Warning: Gemini interval generation requested but GEMINI_API_KEY is not configured. "
                    "Falling back to heuristic interval selection."
                )
            return IntervalGeneratorResolution(
                generator=fallback_generator,
                warning_message=warning_message,
                info_message="Interval generation provider: heuristic.",
            )

        model_name = (
            str(
                effective_env.get(
                    "GEMINI_MODEL",
                    effective_config.get_interval_generation_setting("llm_model", "gemini-2.5-flash"),
                )
            ).strip()
            or "gemini-2.5-flash"
        )

        generator = LlmSubtitleIntervalGenerator(
            llm_client=GeminiIntervalSelectionClient(
                api_key=api_key,
                model=model_name,
                timeout_seconds=float(effective_config.get_interval_generation_setting("llm_timeout_seconds", 20.0)),
                temperature=float(effective_config.get_interval_generation_setting("llm_temperature", 0.2)),
                retry_attempts=int(effective_config.get_interval_generation_setting("llm_retry_attempts", 2)),
            ),
            fallback_generator=fallback_generator,
            target_count=int(effective_config.get_interval_generation_setting("target_count", 11)),
            min_duration_ms=int(effective_config.get_interval_generation_setting("min_duration_ms", 18_000)),
            max_duration_ms=int(effective_config.get_interval_generation_setting("max_duration_ms", 42_000)),
        )
        return IntervalGeneratorResolution(
            generator=generator,
            info_message=f"Interval generation provider: gemini ({model_name}).",
        )

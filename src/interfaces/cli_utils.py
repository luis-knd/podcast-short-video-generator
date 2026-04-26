import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OutroResolution:
    filepath: str | None
    warning_message: str | None = None


@dataclass(frozen=True)
class IntervalsFileResolution:
    payload: list[dict[str, str]] | None
    warning_message: str | None = None


def resolve_outro_filepath(enable_outro: bool, outro_filepath: str) -> OutroResolution:
    if not enable_outro:
        return OutroResolution(filepath=None)
    if os.path.exists(outro_filepath):
        return OutroResolution(filepath=outro_filepath)
    warning_message = f"Warning: Outro file not found: {outro_filepath}. Continuing without outro."
    return OutroResolution(filepath=None, warning_message=warning_message)


def resolve_existing_intervals_file(
    intervals_filepath: str,
    allow_invalid_json_warning: bool,
) -> IntervalsFileResolution:
    if not os.path.exists(intervals_filepath):
        return IntervalsFileResolution(payload=None)

    with open(intervals_filepath, encoding="utf-8") as intervals_file:
        try:
            payload = json.load(intervals_file)
        except json.JSONDecodeError as exc:
            if not allow_invalid_json_warning:
                raise
            warning_message = (
                "Warning: Ignoring invalid intervals JSON in "
                f"{intervals_filepath} while auto generation is enabled. {exc}"
            )
            return IntervalsFileResolution(payload=None, warning_message=warning_message)

    return IntervalsFileResolution(payload=payload)


def persist_intervals_json(intervals_filepath: str, intervals_json: list[dict[str, str]]):
    parent_dir = os.path.dirname(intervals_filepath)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(intervals_filepath, "w", encoding="utf-8") as intervals_file:
        json.dump(intervals_json, intervals_file, ensure_ascii=False, indent=2)
        intervals_file.write("\n")

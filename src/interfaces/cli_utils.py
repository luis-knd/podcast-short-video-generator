import os


def resolve_outro_filepath(
    enable_outro: bool, outro_filepath: str
) -> tuple[str | None, str | None]:
    if not enable_outro:
        return None, None
    if os.path.exists(outro_filepath):
        return outro_filepath, None
    warning_message = (
        f"Warning: Outro file not found: {outro_filepath}. Continuing without outro."
    )
    return None, warning_message

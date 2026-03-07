import re
import unicodedata


def normalize_token(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    normalized = normalized.strip(".,!?;:\"'()[]{}")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized

import hashlib
import json
from pathlib import Path

from src.infrastructure.subtitles.cache import AlignmentCache


def test_alignment_cache_stores_raw_and_reconciled_levels(tmp_path):
    media_file = tmp_path / "video.mp4"
    media_file.write_bytes(b"video")
    subtitle_file = tmp_path / "video.srt"
    subtitle_file.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nSpeaker 1: Hello world\n",
        encoding="utf-8",
    )

    cache = AlignmentCache(tmp_path / ".cache")

    raw_key = cache.build_raw_key(
        media_filepath=str(media_file),
        aligner_name="faster_whisper",
        model_name="base",
        compute_type="int8",
        language="en",
    )
    reconciled_key = cache.build_reconciled_key(
        subtitle_filepath=str(subtitle_file),
        raw_key=raw_key,
        reconciliation_version="v1",
    )

    raw_payload = {"words": [{"text": "hello"}], "metadata": {"level": "raw"}}
    reconciled_payload = {
        "cues": [{"cue_id": "cue-1"}],
        "quality": {"global_score": 0.9},
    }

    cache.save_raw(raw_key, raw_payload)
    cache.save_reconciled(reconciled_key, reconciled_payload)

    assert cache.load_raw(raw_key) == raw_payload
    assert cache.load_reconciled(reconciled_key) == reconciled_payload


def test_alignment_cache_from_output_filepath_uses_output_local_cache(tmp_path):
    output_ass = tmp_path / "outputs" / "short_0.ass"
    output_ass.parent.mkdir(parents=True, exist_ok=True)

    cache = AlignmentCache.from_output_filepath(str(output_ass))

    assert cache.raw_cache_root == tmp_path / "outputs" / ".cache" / "subtitle_alignment" / "raw_asr"
    assert cache.reconciled_cache_root == tmp_path / "outputs" / ".cache" / "subtitle_alignment" / "reconciled"


def test_alignment_cache_builds_stable_keys_and_persists_utf8_json(tmp_path):
    media_file = tmp_path / "video.mp4"
    media_file.write_bytes(b"video-bytes")
    subtitle_file = tmp_path / "video.srt"
    subtitle_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nHola mundo\n", encoding="utf-8")

    cache = AlignmentCache(tmp_path / "nested" / "subtitle-cache")

    assert cache.raw_cache_root.is_dir()
    assert cache.reconciled_cache_root.is_dir()

    fingerprint = cache._file_fingerprint(str(media_file))
    assert fingerprint == {
        "path": str(media_file.resolve()),
        "size_bytes": len(b"video-bytes"),
        "mtime_ns": media_file.stat().st_mtime_ns,
    }

    payload = {"b": 2, "a": {"z": 1}}
    expected_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert cache._hash_payload(payload) == expected_hash
    assert cache._hash_file(str(subtitle_file)) == hashlib.sha256(subtitle_file.read_bytes()).hexdigest()

    raw_key = cache.build_raw_key(
        media_filepath=str(media_file),
        aligner_name="faster_whisper",
        model_name="small",
        compute_type="float16",
        language="es",
    )
    expected_raw_key = cache._hash_payload(
        {
            "media": cache._file_fingerprint(str(media_file)),
            "aligner": "faster_whisper",
            "model": "small",
            "compute_type": "float16",
            "language": "es",
        }
    )
    assert raw_key == expected_raw_key

    reconciled_key = cache.build_reconciled_key(
        subtitle_filepath=str(subtitle_file),
        raw_key=raw_key,
        reconciliation_version="v1",
    )
    expected_reconciled_key = cache._hash_payload(
        {
            "subtitle": {
                **cache._file_fingerprint(str(subtitle_file)),
                "sha256": cache._hash_file(str(subtitle_file)),
            },
            "raw_key": raw_key,
            "reconciliation_version": "v1",
        }
    )
    assert reconciled_key == expected_reconciled_key

    cache_path = cache.raw_cache_root / f"{raw_key}.json"
    cache._save(cache_path, {"speaker": "Se\u00f1or"})
    assert cache._load(Path(tmp_path / "does-not-exist.json")) is None
    assert cache._load(cache_path) == {"speaker": "Se\u00f1or"}
    assert cache_path.read_text(encoding="utf-8") == '{\n  "speaker": "Se\\u00f1or"\n}'

import json
import subprocess

from src.infrastructure.broll.providers.local_still_provider import LocalMediaProvider
from tests.infrastructure.broll.providers.local_media_provider_support_test import create_asset, search_candidates
from tests.infrastructure.broll.providers.support_test import build_provider_test_beat


def test_local_media_provider_reads_ffprobe_output_and_reuses_probe_cache(tmp_path, monkeypatch):
    media_root = tmp_path / "broll"
    video = media_root / "money" / "budget-crash.mp4"
    create_asset(video, b"video")

    provider = LocalMediaProvider(search_dirs=(str(media_root),))
    ffprobe_calls = {"count": 0}

    class FakeCompletedProcess:
        stdout = json.dumps(
            {
                "streams": [{"width": 720, "height": 1280}],
                "format": {"duration": "2.4"},
            }
        )

    expected_command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height:format=duration",
        "-of",
        "json",
        str(video),
    ]

    def fake_run(command, **kwargs):
        ffprobe_calls["count"] += 1
        assert command == expected_command
        assert kwargs == {"check": True, "capture_output": True, "text": True}
        return FakeCompletedProcess()

    monkeypatch.setattr(subprocess, "run", fake_run)

    first = provider.search(
        beat=build_provider_test_beat("The budget crash hit hard"),
        queries=("budget crash",),
        cache_dir=str(tmp_path / "cache"),
    )
    second = provider.search(
        beat=build_provider_test_beat("The budget crash hit hard"),
        queries=("budget crash",),
        cache_dir=str(tmp_path / "cache"),
    )

    assert ffprobe_calls["count"] == 1
    assert first[0].duration_ms == 2400
    assert first[0].width == 720
    assert first[0].height == 1280
    assert first[0].orientation == "vertical"
    assert second[0].duration_ms == 2400


def test_local_media_provider_build_candidate_normalizes_backslashes_and_keeps_provider_metadata(tmp_path, monkeypatch):
    media_root = tmp_path / "broll"
    asset_path = media_root / "special" / "budget\\city.png"
    create_asset(asset_path, b"image")

    provider = LocalMediaProvider(search_dirs=(str(media_root),))
    monkeypatch.setattr(
        provider,
        "_probe_asset",
        lambda **_kwargs: (0, 1080, 1080, "vertical"),
    )

    candidate = provider._build_candidate(
        root=media_root,
        asset_path=asset_path,
        asset_type="image",
        orientation="vertical",
        discovery_source="local_heuristic_fallback",
        title="Budget city",
        tags=("budget", "city"),
    )

    assert candidate.candidate_id == "local-special-budget-city.png"
    assert candidate.provider == "local_media"
    assert candidate.asset_url == str(asset_path)
    assert candidate.local_path == str(asset_path)


def test_local_media_provider_probe_asset_turns_unknown_image_orientation_into_square(tmp_path):
    image = tmp_path / "poster.png"
    create_asset(image, b"image")

    provider = LocalMediaProvider()

    assert provider._probe_asset(image, asset_type="image", fallback_orientation="unknown") == (
        0,
        1080,
        1080,
        "square",
    )


def test_local_media_provider_probe_cache_is_scoped_per_asset_path(tmp_path, monkeypatch):
    first_video = tmp_path / "first.mp4"
    second_video = tmp_path / "second.mp4"
    create_asset(first_video, b"video")
    create_asset(second_video, b"video")
    results = {
        str(first_video.resolve()): (1200, 720, 1280, "vertical"),
        str(second_video.resolve()): (2400, 1280, 720, "landscape"),
    }

    provider = LocalMediaProvider()
    monkeypatch.setattr(
        provider,
        "_run_ffprobe",
        lambda asset_path, fallback_orientation: results[str(asset_path.resolve())],
    )

    assert provider._probe_asset(first_video, asset_type="video", fallback_orientation="unknown") == (
        1200,
        720,
        1280,
        "vertical",
    )
    assert provider._probe_asset(second_video, asset_type="video", fallback_orientation="unknown") == (
        2400,
        1280,
        720,
        "landscape",
    )
    assert provider._probe_asset(first_video, asset_type="video", fallback_orientation="unknown") == (
        1200,
        720,
        1280,
        "vertical",
    )


def test_local_media_provider_run_ffprobe_uses_stream_duration_when_format_duration_is_missing(tmp_path, monkeypatch):
    video = tmp_path / "clip.mp4"
    create_asset(video, b"video")
    payload = {"streams": [{"width": 720, "height": 1280, "duration": "1.2"}]}

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=json.dumps(payload)),
    )

    provider = LocalMediaProvider()

    assert provider._run_ffprobe(video, fallback_orientation="unknown") == (1200, 720, 1280, "vertical")


def test_local_media_provider_run_ffprobe_preserves_fallback_when_duration_and_dimensions_are_missing(
    tmp_path, monkeypatch
):
    video = tmp_path / "clip.mp4"
    create_asset(video, b"video")
    payload = {"streams": [{}], "format": {}}

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args[0], returncode=0, stdout=json.dumps(payload)),
    )

    provider = LocalMediaProvider()

    assert provider._run_ffprobe(video, fallback_orientation="landscape") == (0, 0, 0, "landscape")


def test_local_media_provider_returns_unknown_video_metadata_when_ffprobe_fails(tmp_path, monkeypatch):
    media_root = tmp_path / "broll"
    video = media_root / "money" / "budget-crash.mp4"
    create_asset(video, b"video")

    def raise_ffprobe_error(*_args, **_kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd="ffprobe")

    monkeypatch.setattr(subprocess, "run", raise_ffprobe_error)

    _, candidates = search_candidates(
        tmp_path,
        search_dirs=(media_root,),
        beat_text="The budget crash hit hard",
        queries=("budget crash",),
    )

    assert len(candidates) == 1
    assert candidates[0].duration_ms == 0
    assert candidates[0].width == 0
    assert candidates[0].height == 0
    assert candidates[0].orientation == "unknown"

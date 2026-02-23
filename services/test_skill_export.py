"""Tests for Skill 11: Multi-Format Export."""

import os

import pytest
from pathlib import Path

from ffmpeg_service import FFmpegService
from skill_export import MultiFormatExporter


@pytest.fixture
def exporter():
    return MultiFormatExporter()


@pytest.fixture
def ffmpeg():
    return FFmpegService()


@pytest.fixture
def test_video(tmp_path):
    """Create a 640x480 5-second test video with audio (SMPTE bars)."""
    path = tmp_path / "source.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:duration=5:rate=30" '
        f'-f lavfi -i "sine=frequency=1000:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac -shortest '
        f'"{path}" -y 2>/dev/null'
    )
    assert path.exists(), "Failed to create test video"
    return path


def test_list_profiles(exporter):
    """Should list all 8 export profiles."""
    profiles = exporter.list_profiles()
    assert len(profiles) == 8
    expected = {
        "youtube_4k", "youtube_1080p", "youtube_720p",
        "instagram_reels", "tiktok", "twitter",
        "web_optimized", "gif_preview",
    }
    assert set(profiles.keys()) == expected


def test_export_single_1080p(exporter, ffmpeg, test_video, tmp_path):
    """Should transcode to 1080p with correct resolution."""
    output = tmp_path / "out_1080p.mp4"
    result = exporter.export_single(test_video, output, "youtube_1080p")

    assert output.exists()
    assert result["profile"] == "youtube_1080p"
    assert result["size_bytes"] > 0
    assert result["duration"] > 0

    meta = ffmpeg.get_metadata(output)
    assert meta.width == 1920
    assert meta.height == 1080
    assert meta.has_audio is True


def test_export_single_720p(exporter, ffmpeg, test_video, tmp_path):
    """Should transcode to 720p with correct resolution."""
    output = tmp_path / "out_720p.mp4"
    result = exporter.export_single(test_video, output, "youtube_720p")

    assert output.exists()
    assert result["profile"] == "youtube_720p"

    meta = ffmpeg.get_metadata(output)
    assert meta.width == 1280
    assert meta.height == 720
    assert meta.has_audio is True


def test_export_gif(exporter, test_video, tmp_path):
    """Should export GIF with no audio and correct dimensions."""
    output = tmp_path / "preview.gif"
    result = exporter.export_single(test_video, output, "gif_preview")

    assert output.exists()
    assert result["profile"] == "gif_preview"
    assert result["size_bytes"] > 0
    assert output.suffix == ".gif"


def test_export_web_optimized(exporter, ffmpeg, test_video, tmp_path):
    """Should export web-optimized profile with correct resolution."""
    output = tmp_path / "out_web.mp4"
    result = exporter.export_single(test_video, output, "web_optimized")

    assert output.exists()
    assert result["profile"] == "web_optimized"

    meta = ffmpeg.get_metadata(output)
    assert meta.width == 1920
    assert meta.height == 1080


def test_execute_multiple(exporter, test_video, tmp_path):
    """Should export to 2 profiles and verify both created."""
    output_dir = tmp_path / "exports"
    result = exporter.execute(
        test_video, output_dir, profiles=["youtube_720p", "web_optimized"]
    )

    assert len(result["exports"]) == 2
    assert result["total_size_bytes"] > 0

    for exp in result["exports"]:
        assert Path(exp["path"]).exists()
        assert exp["size_bytes"] > 0
        assert exp["duration"] > 0

    profile_names = [e["profile"] for e in result["exports"]]
    assert "youtube_720p" in profile_names
    assert "web_optimized" in profile_names


def test_invalid_profile_raises(exporter, test_video, tmp_path):
    """Should raise ValueError for unknown profile."""
    output = tmp_path / "out.mp4"
    with pytest.raises(ValueError, match="Unknown profile"):
        exporter.export_single(test_video, output, "nonexistent_profile")

    # Also test via execute()
    with pytest.raises(ValueError, match="Unknown profile"):
        exporter.execute(test_video, tmp_path, profiles=["bad_profile"])

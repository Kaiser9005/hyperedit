import pytest
import os
from pathlib import Path

from ffmpeg_service import FFmpegService, VideoMetadata


@pytest.fixture
def svc():
    return FFmpegService()


@pytest.fixture
def test_video(tmp_path):
    """Create a 5-second test video with audio."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_get_metadata(svc, test_video):
    """Should extract video metadata."""
    meta = svc.get_metadata(test_video)
    assert meta.width == 1920
    assert meta.height == 1080
    assert meta.fps == 30.0
    assert 4.5 <= meta.duration <= 5.5
    assert meta.has_audio is True


def test_cut_segment(svc, test_video, tmp_path):
    """Should cut a segment from video."""
    output = tmp_path / "cut.mp4"
    # Use reencode=True for precise cuts (stream copy can miss keyframes)
    svc.cut(test_video, output, start=1.0, end=3.0, reencode=True)
    meta = svc.get_metadata(output)
    assert 1.5 <= meta.duration <= 2.5


def test_concat_videos(svc, test_video, tmp_path):
    """Should concatenate video files."""
    # Create two clips first
    clip1 = tmp_path / "clip1.mp4"
    clip2 = tmp_path / "clip2.mp4"
    svc.cut(test_video, clip1, start=0, end=2)
    svc.cut(test_video, clip2, start=2, end=4)

    output = tmp_path / "concat.mp4"
    svc.concat([clip1, clip2], output)
    meta = svc.get_metadata(output)
    assert meta.duration >= 3.5


def test_normalize_audio(svc, test_video, tmp_path):
    """Should normalize audio to target LUFS."""
    output = tmp_path / "normalized.mp4"
    svc.normalize_audio(test_video, output, target_lufs=-14)
    assert output.exists()
    assert output.stat().st_size > 0


def test_crop_aspect_ratio(svc, test_video, tmp_path):
    """Should crop to 9:16 vertical format."""
    output = tmp_path / "vertical.mp4"
    svc.crop_aspect(test_video, output, aspect="9:16")
    meta = svc.get_metadata(output)
    # 9:16 ratio means height > width
    assert meta.height > meta.width


def test_get_loudness(svc, test_video):
    """Should measure audio loudness."""
    loudness = svc.get_loudness(test_video)
    assert "input_i" in loudness
    assert float(loudness["input_i"]) < 0  # LUFS is negative

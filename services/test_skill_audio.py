import pytest
import os
from pathlib import Path

from skill_audio import AudioEnhancement


@pytest.fixture
def skill():
    return AudioEnhancement()


@pytest.fixture
def test_video(tmp_path):
    """Create a test video with audio."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "color=c=green:s=1280x720:d=3" '
        f'-f lavfi -i "sine=frequency=440:duration=3" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_audio_enhancement_normalizes(skill, test_video, tmp_path):
    """Should normalize audio to target LUFS."""
    output = tmp_path / "enhanced.mp4"
    result = skill.execute(
        input_path=test_video,
        output_path=output,
        target_lufs=-14,
        noise_reduce=True,
    )
    assert output.exists()
    assert result["after_lufs"] != -99  # Successfully measured
    assert result["lufs_diff"] <= 3  # Within reasonable range


def test_audio_enhancement_no_noise(skill, test_video, tmp_path):
    """Should work without noise reduction."""
    output = tmp_path / "enhanced.mp4"
    result = skill.execute(
        input_path=test_video,
        output_path=output,
        target_lufs=-14,
        noise_reduce=False,
    )
    assert output.exists()
    assert result["noise_reduced"] is False


def test_audio_enhancement_raises_no_audio(skill, tmp_path):
    """Should raise error for video without audio."""
    silent = tmp_path / "silent.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "color=c=black:s=320x240:d=2" '
        f'-c:v libx264 -preset ultrafast -an '
        f'"{silent}" -y 2>/dev/null'
    )
    output = tmp_path / "enhanced.mp4"
    with pytest.raises(ValueError, match="no audio"):
        skill.execute(input_path=silent, output_path=output)

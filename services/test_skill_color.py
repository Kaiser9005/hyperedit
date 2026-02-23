import pytest
import os
from pathlib import Path

from skill_color import ColorGrading


@pytest.fixture
def grader():
    return ColorGrading()


@pytest.fixture
def test_video(tmp_path):
    """Create a test video with SMPTE color bars and audio (3 seconds)."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=3" '
        f'-f lavfi -i "sine=frequency=440:duration=3" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_list_presets(grader):
    presets = grader.list_presets()
    assert "cinematic" in presets
    assert "warm" in presets
    assert "cool" in presets
    assert "vintage" in presets
    assert "high_contrast" in presets
    assert "desaturated" in presets
    assert len(presets) >= 6


def test_execute_with_preset(grader, test_video, tmp_path):
    output = tmp_path / "graded.mp4"
    result = grader.execute(test_video, output, preset="cinematic")
    assert output.exists()
    assert result["preset_used"] == "cinematic"
    assert abs(result["input_duration"] - result["output_duration"]) < 1.0


def test_execute_manual_adjustments(grader, test_video, tmp_path):
    output = tmp_path / "adjusted.mp4"
    result = grader.execute(
        test_video, output,
        contrast=1.2, brightness=0.05, saturation=0.8,
    )
    assert output.exists()
    assert result["adjustments"]["contrast"] == 1.2
    assert result["adjustments"]["brightness"] == 0.05
    assert result["adjustments"]["saturation"] == 0.8


def test_execute_with_gamma(grader, test_video, tmp_path):
    output = tmp_path / "gamma.mp4"
    result = grader.execute(
        test_video, output,
        gamma=1.5,
    )
    assert output.exists()
    assert result["adjustments"]["gamma"] == 1.5


def test_preset_overrides_defaults(grader):
    presets = grader.list_presets()
    cinematic = presets["cinematic"]
    assert cinematic["contrast"] != 1.0
    assert cinematic["saturation"] != 1.0


def test_execute_warm_preset(grader, test_video, tmp_path):
    output = tmp_path / "warm.mp4"
    result = grader.execute(test_video, output, preset="warm")
    assert output.exists()
    assert result["preset_used"] == "warm"
    assert result["adjustments"]["saturation"] == 1.15


def test_invalid_preset_raises(grader, test_video, tmp_path):
    output = tmp_path / "bad.mp4"
    with pytest.raises(ValueError, match="Unknown preset"):
        grader.execute(test_video, output, preset="nonexistent")


def test_missing_input_raises(grader, tmp_path):
    output = tmp_path / "out.mp4"
    with pytest.raises(FileNotFoundError, match="Input video not found"):
        grader.execute(tmp_path / "does_not_exist.mp4", output, preset="warm")


def test_missing_lut_raises(grader, test_video, tmp_path):
    output = tmp_path / "out.mp4"
    with pytest.raises(FileNotFoundError, match="LUT file not found"):
        grader.execute(test_video, output, lut_path=tmp_path / "missing.cube")


def test_resolution_preserved(grader, test_video, tmp_path):
    """Output should have the same resolution as input."""
    from ffmpeg_service import FFmpegService
    ffmpeg = FFmpegService()
    input_meta = ffmpeg.get_metadata(test_video)

    output = tmp_path / "res_check.mp4"
    grader.execute(test_video, output, preset="high_contrast")

    output_meta = ffmpeg.get_metadata(output)
    assert output_meta.width == input_meta.width
    assert output_meta.height == input_meta.height

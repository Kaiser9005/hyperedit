import os

import pytest
from pathlib import Path

from skill_style import StyleTransfer


@pytest.fixture
def styler():
    return StyleTransfer()


@pytest.fixture
def test_video(tmp_path):
    """Create a 640x480 3-second test video with color bars and audio."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=3" '
        f'-f lavfi -i "sine=frequency=440:duration=3" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_list_styles(styler):
    styles = styler.list_styles()
    assert len(styles) == 7
    assert "film_noir" in styles
    assert "vhs_retro" in styles
    assert "instagram_warm" in styles
    assert "cool_blue" in styles
    assert "high_contrast_bw" in styles
    assert "dreamy" in styles
    assert "cinematic_teal_orange" in styles


def test_execute_film_noir(styler, test_video, tmp_path):
    output = tmp_path / "noir.mp4"
    result = styler.execute(test_video, output, style="film_noir")
    assert output.exists()
    assert result["style_applied"] == "Film Noir"
    assert abs(result["input_duration"] - result["output_duration"]) < 1.0


def test_execute_vhs_retro(styler, test_video, tmp_path):
    output = tmp_path / "vhs.mp4"
    result = styler.execute(test_video, output, style="vhs_retro")
    assert output.exists()
    assert result["style_applied"] == "VHS Retro"
    assert abs(result["input_duration"] - result["output_duration"]) < 1.0


def test_execute_dreamy(styler, test_video, tmp_path):
    output = tmp_path / "dreamy.mp4"
    result = styler.execute(test_video, output, style="dreamy")
    assert output.exists()
    assert result["style_applied"] == "Dreamy"
    assert abs(result["input_duration"] - result["output_duration"]) < 1.0


def test_execute_cinematic(styler, test_video, tmp_path):
    output = tmp_path / "cinematic.mp4"
    result = styler.execute(test_video, output, style="cinematic_teal_orange")
    assert output.exists()
    assert result["style_applied"] == "Cinematic Teal & Orange"
    assert abs(result["input_duration"] - result["output_duration"]) < 1.0


def test_invalid_style_raises(styler, test_video, tmp_path):
    output = tmp_path / "bad.mp4"
    with pytest.raises(ValueError, match="Unknown style"):
        styler.execute(test_video, output, style="nonexistent")


def test_no_style_or_reference_raises(styler, test_video, tmp_path):
    output = tmp_path / "bad.mp4"
    with pytest.raises(ValueError, match="Either 'style' preset or 'reference_path' must be provided"):
        styler.execute(test_video, output)

import os

import pytest

from skill_animation import AnimationOverlay


@pytest.fixture
def overlay():
    return AnimationOverlay()


@pytest.fixture
def test_video(tmp_path):
    """Create a 640x480 5-second test video with audio."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_list_presets(overlay):
    presets = overlay.list_presets()
    assert "lower_third" in presets
    assert "title_card" in presets
    assert "scroll_text" in presets
    assert "corner_badge" in presets
    assert "countdown" in presets
    assert len(presets) == 5


def test_build_filter_chain_single(overlay):
    overlays = [
        {
            "preset": "lower_third",
            "text": "Hello",
            "start": 1.0,
            "end": 4.0,
            "fontsize": 36,
            "color": "white",
            "bg_color": "black@0.7",
        }
    ]
    chain = overlay._build_filter_chain(overlays, 640, 480)
    assert "drawtext=" in chain
    assert "Hello" in chain
    # Single overlay produces exactly one drawtext filter
    assert chain.count("drawtext=") == 1


def test_build_filter_chain_multiple(overlay):
    overlays = [
        {
            "preset": "lower_third",
            "text": "Name",
            "start": 0,
            "end": 3,
        },
        {
            "preset": "corner_badge",
            "text": "LIVE",
            "start": 0,
            "end": 5,
        },
    ]
    chain = overlay._build_filter_chain(overlays, 640, 480)
    # Two overlays produce two drawtext filters chained with comma
    assert chain.count("drawtext=") == 2
    assert "Name" in chain
    assert "LIVE" in chain


def test_execute_lower_third(overlay, test_video, tmp_path):
    output = tmp_path / "lower_third.mp4"
    result = overlay.execute(
        test_video,
        output,
        overlays=[
            {
                "preset": "lower_third",
                "text": "Company Name",
                "start": 1.0,
                "end": 4.0,
                "fontsize": 36,
                "color": "white",
                "bg_color": "black@0.7",
            }
        ],
    )
    assert output.exists()
    assert result["overlays_applied"] == 1
    assert abs(result["input_duration"] - result["output_duration"]) < 0.5


def test_execute_title_card(overlay, test_video, tmp_path):
    output = tmp_path / "title_card.mp4"
    result = overlay.execute(
        test_video,
        output,
        overlays=[
            {
                "preset": "title_card",
                "text": "Welcome",
                "start": 0.0,
                "end": 3.0,
                "fontsize": 64,
                "color": "yellow",
            }
        ],
    )
    assert output.exists()
    assert result["overlays_applied"] == 1
    assert abs(result["input_duration"] - result["output_duration"]) < 0.5


def test_execute_corner_badge(overlay, test_video, tmp_path):
    output = tmp_path / "corner_badge.mp4"
    result = overlay.execute(
        test_video,
        output,
        overlays=[
            {
                "preset": "corner_badge",
                "text": "LIVE",
                "start": 0.0,
                "end": 5.0,
                "fontsize": 24,
                "color": "red",
                "bg_color": "white@0.8",
            }
        ],
    )
    assert output.exists()
    assert result["overlays_applied"] == 1
    assert abs(result["input_duration"] - result["output_duration"]) < 0.5


def test_execute_empty_overlays(overlay, test_video, tmp_path):
    output = tmp_path / "copy.mp4"
    result = overlay.execute(
        test_video,
        output,
        overlays=[],
    )
    assert output.exists()
    assert result["overlays_applied"] == 0
    assert abs(result["input_duration"] - result["output_duration"]) < 0.5

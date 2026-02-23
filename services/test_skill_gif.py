import os

import pytest
from pathlib import Path

from skill_gif import GifManager


@pytest.fixture
def manager():
    return GifManager()


@pytest.fixture
def test_video(tmp_path):
    """Create a 640x480, 5-second test video with color bars and audio."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_list_presets(manager):
    presets = manager.list_presets()
    assert len(presets) == 4
    assert "high" in presets
    assert "medium" in presets
    assert "low" in presets
    assert "thumbnail" in presets
    # Verify preset structure
    for name, preset in presets.items():
        assert "width" in preset
        assert "fps" in preset
        assert "max_colors" in preset


def test_extract_gif(manager, test_video, tmp_path):
    output = tmp_path / "clip.gif"
    result = manager.extract_gif(
        input_path=test_video,
        output_path=output,
        start=1.0,
        end=3.0,
    )
    assert output.exists()
    assert output.suffix == ".gif"
    assert result["duration"] == 2.0
    assert result["fps"] == 15
    assert result["file_size_bytes"] > 0


def test_video_to_gif(manager, test_video, tmp_path):
    output = tmp_path / "full.gif"
    result = manager.video_to_gif(
        input_path=test_video,
        output_path=output,
    )
    assert output.exists()
    assert output.suffix == ".gif"
    assert result["duration"] <= 10
    assert result["file_size_bytes"] > 0


def test_extract_gif_custom_size(manager, test_video, tmp_path):
    large = tmp_path / "large.gif"
    small = tmp_path / "small.gif"

    manager.extract_gif(
        input_path=test_video,
        output_path=large,
        start=0,
        end=3.0,
        width=480,
    )
    manager.extract_gif(
        input_path=test_video,
        output_path=small,
        start=0,
        end=3.0,
        width=320,
    )

    assert large.exists()
    assert small.exists()
    assert small.stat().st_size < large.stat().st_size


def test_optimize_gif(manager, test_video, tmp_path):
    source_gif = tmp_path / "source.gif"
    optimized_gif = tmp_path / "optimized.gif"

    # Create a high-quality GIF first
    manager.extract_gif(
        input_path=test_video,
        output_path=source_gif,
        start=0,
        end=3.0,
        width=640,
        fps=24,
        max_colors=256,
    )

    result = manager.optimize_gif(
        input_path=test_video,
        output_path=optimized_gif,
        max_size_kb=5000,
    )

    assert optimized_gif.exists()
    assert result["optimized_size"] <= result["original_size"]
    assert len(result["reductions_applied"]) >= 1


def test_invalid_time_range(manager, test_video, tmp_path):
    output = tmp_path / "bad.gif"
    with pytest.raises(ValueError, match="start.*must be less than.*end"):
        manager.extract_gif(
            input_path=test_video,
            output_path=output,
            start=5.0,
            end=2.0,
        )
    # Also test equal start/end
    with pytest.raises(ValueError, match="start.*must be less than.*end"):
        manager.extract_gif(
            input_path=test_video,
            output_path=output,
            start=3.0,
            end=3.0,
        )

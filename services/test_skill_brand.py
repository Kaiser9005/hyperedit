"""Tests for Skill 16: Brand Kit Manager."""

import json
import os
from pathlib import Path

import pytest

from skill_brand import BrandKitManager


@pytest.fixture
def brand_mgr():
    return BrandKitManager()


@pytest.fixture
def test_video(tmp_path):
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=3" '
        f'-f lavfi -i "sine=frequency=440:duration=3" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


@pytest.fixture
def brand_config(tmp_path):
    config = {
        "name": "Test Brand",
        "colors": {
            "primary": "#FF0000",
            "secondary": "#00FF00",
            "accent": "#0000FF",
            "text": "#FFFFFF",
        },
        "fonts": {"heading": "Arial", "body": "Arial"},
        "watermark": {
            "text": "TEST BRAND",
            "position": "bottom_right",
            "opacity": 0.3,
            "font_size": 24,
        },
        "text_overlay": {
            "font_size": 36,
            "font_color": "#FFFFFF",
            "bg_color": "#00000080",
            "padding": 10,
        },
    }
    path = tmp_path / "brand.json"
    with open(path, "w") as f:
        json.dump(config, f)
    return path


def test_load_config(brand_mgr, brand_config):
    config = brand_mgr.load_config(brand_config)
    assert config["name"] == "Test Brand"
    assert config["colors"]["primary"] == "#FF0000"


def test_load_default_config(brand_mgr):
    config = brand_mgr.load_config(Path("/nonexistent/path.json"))
    assert "colors" in config
    assert "watermark" in config


def test_execute_with_watermark(brand_mgr, test_video, brand_config, tmp_path):
    output = tmp_path / "branded.mp4"
    result = brand_mgr.execute(
        test_video,
        output,
        brand_config=brand_config,
        add_watermark=True,
    )
    assert output.exists()
    assert result["watermark_applied"] is True
    assert result["brand_name"] == "Test Brand"
    assert abs(result["input_duration"] - result["output_duration"]) < 1.0


def test_execute_with_text_overlay(brand_mgr, test_video, brand_config, tmp_path):
    output = tmp_path / "text_branded.mp4"
    result = brand_mgr.execute(
        test_video,
        output,
        brand_config=brand_config,
        add_watermark=False,
        add_text_overlay=True,
        text_content="FOFAL Organic Palm Oil",
        text_position="bottom_left",
    )
    assert output.exists()
    assert result["text_overlay_applied"] is True


def test_execute_no_filters(brand_mgr, test_video, tmp_path):
    """When watermark text is empty and no text overlay, video should still process."""
    output = tmp_path / "nofilter.mp4"
    result = brand_mgr.execute(
        test_video,
        output,
        brand_config=None,  # default config has empty watermark text
        add_watermark=True,
        add_text_overlay=False,
    )
    assert output.exists()
    assert result["watermark_applied"] is False
    assert result["text_overlay_applied"] is False


def test_create_brand_config(brand_mgr, tmp_path):
    output = tmp_path / "new_brand.json"
    brand_mgr.create_brand_config(
        name="FOFAL",
        primary_color="#166534",
        secondary_color="#D97706",
        output_path=output,
    )
    assert output.exists()
    with open(output) as f:
        config = json.load(f)
    assert config["name"] == "FOFAL"
    assert config["colors"]["primary"] == "#166534"


def test_execute_missing_input(brand_mgr, tmp_path):
    """Should raise FileNotFoundError for missing input."""
    with pytest.raises(FileNotFoundError):
        brand_mgr.execute(
            tmp_path / "nonexistent.mp4",
            tmp_path / "output.mp4",
        )

"""Tests for Skill 14: Thumbnail Generation."""

import os

import pytest
from pathlib import Path

from skill_thumbnail import ThumbnailGenerator


@pytest.fixture
def gen():
    return ThumbnailGenerator()


@pytest.fixture
def test_video(tmp_path):
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=10" '
        f'-f lavfi -i "sine=frequency=440:duration=10" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_calculate_timestamps(gen):
    ts = gen._calculate_timestamps(100, 3)
    assert len(ts) == 3
    assert ts[0] >= 5  # skip first 5%
    assert ts[-1] <= 95  # skip last 5%


def test_calculate_timestamps_short_video(gen):
    ts = gen._calculate_timestamps(5, 3)
    assert len(ts) == 3
    assert all(0 <= t <= 5 for t in ts)


def test_calculate_timestamps_single(gen):
    ts = gen._calculate_timestamps(100, 1)
    assert len(ts) == 1
    assert ts[0] == 50.0


def test_calculate_timestamps_zero_count(gen):
    ts = gen._calculate_timestamps(100, 0)
    assert len(ts) == 0


def test_execute(gen, test_video, tmp_path):
    output_dir = tmp_path / "thumbnails"
    output_dir.mkdir()
    result = gen.execute(test_video, output_dir, count=3, format="jpg")
    assert result["count"] == 3
    assert len(result["thumbnails"]) == 3
    for thumb in result["thumbnails"]:
        assert Path(thumb["path"]).exists()
        assert thumb["size_bytes"] > 0
    assert "best_thumbnail" in result


def test_execute_png_format(gen, test_video, tmp_path):
    output_dir = tmp_path / "thumbs_png"
    output_dir.mkdir()
    result = gen.execute(test_video, output_dir, count=2, format="png")
    assert len(result["thumbnails"]) == 2
    for thumb in result["thumbnails"]:
        assert thumb["path"].endswith(".png")


def test_extract_at_timestamps(gen, test_video, tmp_path):
    output_dir = tmp_path / "custom_thumbs"
    output_dir.mkdir()
    thumbs = gen.extract_at_timestamps(
        test_video, output_dir, timestamps=[1.0, 5.0, 8.0]
    )
    assert len(thumbs) == 3


def test_get_best_thumbnail(gen):
    thumbnails = [
        {"path": "a.jpg", "timestamp": 1.0, "size_bytes": 1000},
        {"path": "b.jpg", "timestamp": 5.0, "size_bytes": 5000},
        {"path": "c.jpg", "timestamp": 8.0, "size_bytes": 3000},
    ]
    best = gen._get_best_thumbnail(thumbnails)
    assert best["path"] == "b.jpg"


def test_get_best_thumbnail_empty(gen):
    best = gen._get_best_thumbnail([])
    assert best == {}


def test_execute_creates_output_dir(gen, test_video, tmp_path):
    output_dir = tmp_path / "auto_created"
    # Do not mkdir -- execute should create it
    result = gen.execute(test_video, output_dir, count=2, format="jpg")
    assert output_dir.exists()
    assert result["count"] == 2


def test_execute_file_not_found(gen, tmp_path):
    with pytest.raises(FileNotFoundError):
        gen.execute(
            tmp_path / "nonexistent.mp4",
            tmp_path / "out",
            count=1,
        )

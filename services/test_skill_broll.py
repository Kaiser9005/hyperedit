"""Tests for Skill 9: B-Roll Insertion."""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from skill_broll import BRollInserter


@pytest.fixture
def skill():
    return BRollInserter()


@pytest.fixture
def test_video(tmp_path):
    """Create a 10s test video with SMPTE bars and audio."""
    path = tmp_path / "main.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=10" '
        f'-f lavfi -i "sine=frequency=440:duration=10" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


@pytest.fixture
def broll_clip(tmp_path):
    """Create a 5s blue B-roll clip with audio."""
    path = tmp_path / "broll.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "color=c=blue:size=640x480:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=880:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_find_insertion_points_returns_list(skill):
    """Mock detect_silence and verify find_insertion_points returns correct format."""
    mock_silences = [
        {"start": 2.0, "end": 4.5},
        {"start": 7.0, "end": 9.0},
    ]

    with patch.object(skill.whisper, "extract_audio") as mock_extract, \
         patch.object(skill.whisper, "detect_silence", return_value=mock_silences):
        # Provide a fake path that we won't actually read
        mock_extract.return_value = Path("/tmp/fake_audio.wav")

        # Create a temporary file so the path "exists" for unlink
        fake_input = Path("/tmp/test_find_points_input.mp4")
        fake_audio = fake_input.parent / f"{fake_input.stem}_broll_audio.wav"
        fake_audio.touch()

        try:
            points = skill.find_insertion_points(fake_input, mode="silence", min_gap=1.5)
        finally:
            if fake_audio.exists():
                fake_audio.unlink()

    assert isinstance(points, list)
    assert len(points) == 2

    for p in points:
        assert "start" in p
        assert "end" in p
        assert "duration" in p
        assert "type" in p
        assert p["type"] == "silence"

    assert points[0]["start"] == 2.0
    assert points[0]["end"] == 4.5
    assert points[0]["duration"] == pytest.approx(2.5)
    assert points[1]["start"] == 7.0
    assert points[1]["end"] == 9.0
    assert points[1]["duration"] == pytest.approx(2.0)


def test_build_edit_list():
    """Mock insertion points + broll clips, verify alternating main/broll."""
    skill = BRollInserter()
    insertion_points = [
        {"start": 3.0, "end": 5.0, "duration": 2.0, "type": "silence"},
        {"start": 8.0, "end": 9.0, "duration": 1.0, "type": "silence"},
    ]
    broll_clips = [Path("/tmp/broll1.mp4"), Path("/tmp/broll2.mp4")]
    main_duration = 12.0

    edit_list = skill._build_edit_list(insertion_points, broll_clips, main_duration)

    # Expected: main(0-3) + broll(3-5) + main(5-8) + broll(8-9) + main(9-12)
    assert len(edit_list) == 5

    assert edit_list[0]["type"] == "main"
    assert edit_list[0]["start"] == 0.0
    assert edit_list[0]["end"] == 3.0

    assert edit_list[1]["type"] == "broll"
    assert edit_list[1]["start"] == 3.0
    assert edit_list[1]["end"] == 5.0
    assert edit_list[1]["source"] == str(broll_clips[0])

    assert edit_list[2]["type"] == "main"
    assert edit_list[2]["start"] == 5.0
    assert edit_list[2]["end"] == 8.0

    assert edit_list[3]["type"] == "broll"
    assert edit_list[3]["start"] == 8.0
    assert edit_list[3]["end"] == 9.0
    assert edit_list[3]["source"] == str(broll_clips[1])

    assert edit_list[4]["type"] == "main"
    assert edit_list[4]["start"] == 9.0
    assert edit_list[4]["end"] == 12.0


def test_build_edit_list_no_insertions():
    """No insertion points should produce one main segment."""
    skill = BRollInserter()
    edit_list = skill._build_edit_list([], [Path("/tmp/broll.mp4")], 10.0)

    assert len(edit_list) == 1
    assert edit_list[0]["type"] == "main"
    assert edit_list[0]["start"] == 0.0
    assert edit_list[0]["end"] == 10.0


def test_build_edit_list_respects_max():
    """max_insertions limit should be applied before building edit list."""
    skill = BRollInserter()
    # Create 10 insertion points
    insertion_points = [
        {"start": float(i), "end": float(i) + 0.5, "duration": 0.5, "type": "silence"}
        for i in range(0, 20, 2)
    ]
    broll_clips = [Path("/tmp/broll.mp4")]

    # Limit to 3
    limited_points = insertion_points[:3]
    edit_list = skill._build_edit_list(limited_points, broll_clips, 20.0)

    # Count broll entries
    broll_count = sum(1 for e in edit_list if e["type"] == "broll")
    assert broll_count == 3


def test_build_edit_list_cycles_broll_clips():
    """B-roll clips should cycle when there are more insertions than clips."""
    skill = BRollInserter()
    insertion_points = [
        {"start": 2.0, "end": 3.0, "duration": 1.0, "type": "silence"},
        {"start": 5.0, "end": 6.0, "duration": 1.0, "type": "silence"},
        {"start": 8.0, "end": 9.0, "duration": 1.0, "type": "silence"},
    ]
    broll_clips = [Path("/tmp/a.mp4"), Path("/tmp/b.mp4")]

    edit_list = skill._build_edit_list(insertion_points, broll_clips, 10.0)

    broll_entries = [e for e in edit_list if e["type"] == "broll"]
    assert len(broll_entries) == 3
    assert broll_entries[0]["source"] == str(broll_clips[0])  # index 0 % 2 = 0
    assert broll_entries[1]["source"] == str(broll_clips[1])  # index 1 % 2 = 1
    assert broll_entries[2]["source"] == str(broll_clips[0])  # index 2 % 2 = 0


def test_prepare_broll_trim(skill, broll_clip, tmp_path):
    """Trim a 5s B-roll clip to 2s and verify duration."""
    prepared = skill._prepare_broll(
        broll_clip,
        target_duration=2.0,
        target_width=640,
        target_height=480,
    )

    assert prepared.exists()
    meta = skill.ffmpeg.get_metadata(prepared)
    assert meta.duration == pytest.approx(2.0, abs=0.5)

    # Cleanup
    prepared.unlink()


def test_prepare_broll_scale(skill, broll_clip, tmp_path):
    """Scale a 640x480 B-roll clip to 320x240 and verify dimensions."""
    prepared = skill._prepare_broll(
        broll_clip,
        target_duration=2.0,
        target_width=320,
        target_height=240,
    )

    assert prepared.exists()
    meta = skill.ffmpeg.get_metadata(prepared)
    assert meta.width == 320
    assert meta.height == 240

    # Cleanup
    prepared.unlink()

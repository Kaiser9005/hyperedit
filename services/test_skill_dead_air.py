import pytest
import os
from pathlib import Path

from skill_dead_air import DeadAirRemoval


@pytest.fixture
def skill():
    return DeadAirRemoval()


@pytest.fixture
def video_with_silence(tmp_path):
    """Create a video with a silence gap in the middle."""
    # 2s tone + 3s silence + 2s tone = 7s total
    path = tmp_path / "silence_video.mp4"
    os.system(
        f'ffmpeg '
        f'-f lavfi -i "color=c=blue:s=1280x720:d=7" '
        f'-f lavfi -i "sine=frequency=440:duration=2" '
        f'-f lavfi -i "anullsrc=r=44100:cl=stereo" '
        f'-f lavfi -i "sine=frequency=440:duration=2" '
        f'-filter_complex "[1][2][3]concat=n=3:v=0:a=1[a];[a]atrim=duration=7[aout]" '
        f'-map 0:v -map "[aout]" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'-t 7 "{path}" -y 2>/dev/null'
    )
    return path


def test_dead_air_removes_silence(skill, video_with_silence, tmp_path):
    """Should produce shorter video after removing silence."""
    output = tmp_path / "clean.mp4"
    result = skill.execute(
        input_path=video_with_silence,
        output_path=output,
        min_silence_duration=1.0,
        remove_fillers=False,
    )
    assert result["output_duration"] < result["input_duration"]
    assert result["segments_removed"] >= 1
    assert output.exists()


def test_dead_air_no_silence_copies(skill, tmp_path):
    """Video with no silence should be copied unchanged."""
    input_path = tmp_path / "no_silence.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "color=c=red:s=1280x720:d=3" '
        f'-f lavfi -i "sine=frequency=440:duration=3" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{input_path}" -y 2>/dev/null'
    )

    output = tmp_path / "clean.mp4"
    result = skill.execute(
        input_path=input_path,
        output_path=output,
        min_silence_duration=1.0,
        remove_fillers=False,
    )
    assert result["segments_removed"] == 0
    assert output.exists()


def test_merge_overlapping():
    """Should merge overlapping segments correctly."""
    skill = DeadAirRemoval()
    segments = [
        {"start": 0.0, "end": 2.0, "type": "silence"},
        {"start": 1.5, "end": 3.0, "type": "filler"},
        {"start": 5.0, "end": 6.0, "type": "silence"},
    ]
    merged = skill._merge_overlapping(segments)
    assert len(merged) == 2
    assert merged[0]["start"] == 0.0
    assert merged[0]["end"] == 3.0
    assert merged[1]["start"] == 5.0
    assert merged[1]["end"] == 6.0


def test_invert_segments():
    """Should convert removal list to keep list."""
    skill = DeadAirRemoval()
    removals = [
        {"start": 2.0, "end": 4.0},
        {"start": 6.0, "end": 7.0},
    ]
    keeps = skill._invert_segments(removals, total_duration=10.0)
    assert len(keeps) == 3
    assert keeps[0] == {"start": 0.0, "end": 2.0}
    assert keeps[1] == {"start": 4.0, "end": 6.0}
    assert keeps[2] == {"start": 7.0, "end": 10.0}

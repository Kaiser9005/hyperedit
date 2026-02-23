"""Tests for Skill 3: Transitions."""

import os
import pytest
from pathlib import Path

from skill_transitions import TransitionManager


@pytest.fixture
def test_video(tmp_path):
    """Generate a 5-second SMPTE test video with audio."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


@pytest.fixture
def two_clips(tmp_path):
    """Generate two 3-second test clips for multi-clip transitions."""
    clips = []
    for i, freq in enumerate([440, 880]):
        path = tmp_path / f"clip{i}.mp4"
        os.system(
            f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=3" '
            f'-f lavfi -i "sine=frequency={freq}:duration=3" '
            f'-c:v libx264 -preset ultrafast -c:a aac '
            f'"{path}" -y 2>/dev/null'
        )
        clips.append(path)
    return clips


@pytest.fixture
def manager():
    return TransitionManager()


class TestListTransitions:
    def test_list_transitions(self, manager):
        """Verify all 8 transitions are available."""
        transitions = manager.list_transitions()
        assert len(transitions) == 8
        expected = [
            "fade", "crossfade", "dissolve",
            "wipeleft", "wiperight",
            "slideup", "slidedown",
            "circleopen",
        ]
        for name in expected:
            assert name in transitions


class TestExecuteFade:
    def test_execute_fade(self, manager, test_video, tmp_path):
        """Apply default fade (end) to test video, verify output exists and duration preserved."""
        output = tmp_path / "faded.mp4"
        result = manager.execute(
            input_path=test_video,
            output_path=output,
            transition_type="fade",
            duration=1.0,
            position="end",
        )
        assert output.exists()
        assert output.stat().st_size > 0
        assert abs(result["input_duration"] - result["output_duration"]) < 0.5
        assert result["transition_type"] == "fade"
        assert result["position"] == "end"

    def test_execute_fade_in_only(self, manager, test_video, tmp_path):
        """Fade in only (position='start')."""
        output = tmp_path / "fade_in.mp4"
        result = manager.execute(
            input_path=test_video,
            output_path=output,
            transition_type="fade",
            duration=1.0,
            position="start",
        )
        assert output.exists()
        assert result["position"] == "start"
        assert abs(result["input_duration"] - result["output_duration"]) < 0.5

    def test_execute_fade_out_only(self, manager, test_video, tmp_path):
        """Fade out only (position='end')."""
        output = tmp_path / "fade_out.mp4"
        result = manager.execute(
            input_path=test_video,
            output_path=output,
            transition_type="fade",
            duration=1.0,
            position="end",
        )
        assert output.exists()
        assert result["position"] == "end"
        assert abs(result["input_duration"] - result["output_duration"]) < 0.5

    def test_execute_both_fades(self, manager, test_video, tmp_path):
        """Fade in + out (position='both')."""
        output = tmp_path / "fade_both.mp4"
        result = manager.execute(
            input_path=test_video,
            output_path=output,
            transition_type="fade",
            duration=1.0,
            position="both",
        )
        assert output.exists()
        assert result["position"] == "both"
        assert abs(result["input_duration"] - result["output_duration"]) < 0.5


class TestInvalidTransition:
    def test_invalid_transition_raises(self, manager, test_video, tmp_path):
        """Unknown transition type raises ValueError."""
        output = tmp_path / "invalid.mp4"
        with pytest.raises(ValueError, match="Unknown transition"):
            manager.execute(
                input_path=test_video,
                output_path=output,
                transition_type="nonexistent",
                duration=1.0,
            )


class TestApplyBetweenClips:
    def test_crossfade_two_clips(self, manager, two_clips, tmp_path):
        """Crossfade between two clips, verify combined duration."""
        output = tmp_path / "crossfaded.mp4"
        result = manager.apply_between_clips(
            clip_paths=two_clips,
            output_path=output,
            transition_type="crossfade",
            duration=0.5,
        )
        assert output.exists()
        assert result["clip_count"] == 2
        assert result["num_transitions"] == 1
        # 3s + 3s - 0.5s overlap = 5.5s expected
        assert abs(result["output_duration"] - result["expected_duration"]) < 1.0

    def test_too_few_clips_raises(self, manager, test_video, tmp_path):
        """Single clip for between-clip transition raises ValueError."""
        output = tmp_path / "fail.mp4"
        with pytest.raises(ValueError, match="at least 2 clips"):
            manager.apply_between_clips(
                clip_paths=[test_video],
                output_path=output,
                transition_type="crossfade",
                duration=0.5,
            )

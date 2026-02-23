"""Tests for the batch processor pipeline."""

import os

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from batch_processor import BatchProcessor, PipelineStep, PipelineResult


@pytest.fixture
def processor():
    return BatchProcessor()


@pytest.fixture
def test_video(tmp_path):
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_list_skills(processor):
    skills = processor.list_skills()
    assert "dead_air" in skills
    assert "audio" in skills
    assert "color" in skills
    assert len(skills) >= 8


def test_default_pipeline(processor):
    pipeline = processor.get_default_pipeline()
    assert pipeline == ["dead_air", "audio", "color", "captions"]


def test_execute_single_step(processor, test_video, tmp_path):
    output_dir = tmp_path / "output"
    steps = [PipelineStep(skill_name="color", config={"preset": "warm"})]
    result = processor.execute(test_video, output_dir, steps=steps)

    assert result.success is True
    assert result.steps_completed == 1
    assert result.steps_total == 1
    assert Path(result.output_path).exists()


def test_execute_two_steps(processor, test_video, tmp_path):
    output_dir = tmp_path / "output"
    steps = [
        PipelineStep(skill_name="color", config={"preset": "cinematic"}),
        PipelineStep(skill_name="audio"),
    ]
    result = processor.execute(test_video, output_dir, steps=steps)

    assert result.success is True
    assert result.steps_completed == 2
    assert len(result.step_results) == 2


def test_execute_missing_input(processor, tmp_path):
    with pytest.raises(FileNotFoundError):
        processor.execute(Path("/nonexistent.mp4"), tmp_path / "out")


def test_execute_unknown_skill(processor, test_video, tmp_path):
    steps = [PipelineStep(skill_name="unknown_skill")]
    result = processor.execute(test_video, tmp_path / "out", steps=steps)
    assert result.success is False
    assert len(result.errors) == 1


def test_optional_step_failure(processor, test_video, tmp_path):
    """Optional step failure doesn't stop the pipeline."""
    output_dir = tmp_path / "output"
    steps = [
        PipelineStep(skill_name="color", config={"preset": "warm"}),
        PipelineStep(skill_name="unknown_fail", required=False),  # will fail
        PipelineStep(skill_name="audio"),
    ]
    result = processor.execute(test_video, output_dir, steps=steps)
    # Color succeeds, unknown fails (optional), audio succeeds
    assert result.steps_completed == 2  # color + audio
    assert len(result.errors) == 1  # unknown_fail


def test_notification_integration(test_video, tmp_path):
    notifier = MagicMock()
    processor = BatchProcessor(notifier=notifier)
    steps = [PipelineStep(skill_name="color", config={"preset": "warm"})]
    processor.execute(test_video, tmp_path / "out", steps=steps)

    notifier.pipeline_started.assert_called_once()
    notifier.skill_started.assert_called_once()
    notifier.skill_completed.assert_called_once()
    notifier.pipeline_completed.assert_called_once()


def test_pipeline_result_has_duration(processor, test_video, tmp_path):
    """Pipeline result should include a non-negative duration."""
    output_dir = tmp_path / "output"
    steps = [PipelineStep(skill_name="color", config={"preset": "warm"})]
    result = processor.execute(test_video, output_dir, steps=steps)

    assert result.duration_seconds >= 0


def test_step_results_contain_skill_name(processor, test_video, tmp_path):
    """Each step result should include the skill name."""
    output_dir = tmp_path / "output"
    steps = [PipelineStep(skill_name="color", config={"preset": "warm"})]
    result = processor.execute(test_video, output_dir, steps=steps)

    assert len(result.step_results) == 1
    assert result.step_results[0]["skill"] == "color"
    assert result.step_results[0]["success"] is True

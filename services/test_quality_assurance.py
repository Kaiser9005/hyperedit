import pytest
import os
from pathlib import Path

from quality_assurance import QualityAssurance, QAResult
from ffmpeg_service import FFmpegService


@pytest.fixture
def qa():
    return QualityAssurance()


@pytest.fixture
def test_video(tmp_path):
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=1920x1080:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_qa_check_duration(qa, test_video):
    result = qa.check_duration(test_video, expected=5.0, tolerance=0.5)
    assert result.passed is True


def test_qa_check_resolution(qa, test_video):
    result = qa.check_resolution(test_video, min_width=1920, min_height=1080)
    assert result.passed is True


def test_qa_check_no_black_frames(qa, test_video):
    result = qa.check_no_black_frames(test_video)
    assert result.passed is True


def test_qa_full_check(qa, test_video):
    results = qa.full_check(
        test_video,
        expected_duration=5.0,
        min_width=1920,
        min_height=1080,
    )
    assert all(r.passed for r in results)


def test_qa_format_report(qa, test_video):
    results = qa.full_check(test_video, expected_duration=5.0)
    report = qa.format_report(results)
    assert "PASSED" in report
    assert "duration" in report
    assert "resolution" in report

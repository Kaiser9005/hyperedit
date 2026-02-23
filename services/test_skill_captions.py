import pytest
import os
from pathlib import Path

from skill_captions import CaptionGeneration


@pytest.fixture
def skill():
    return CaptionGeneration()


def test_srt_time_format():
    """Should format SRT timestamps correctly."""
    skill = CaptionGeneration()
    assert skill._seconds_to_srt_time(0.0) == "00:00:00,000"
    assert skill._seconds_to_srt_time(61.5) == "00:01:01,500"
    assert skill._seconds_to_srt_time(3661.123) == "01:01:01,123"


def test_vtt_time_format():
    """Should format VTT timestamps correctly."""
    skill = CaptionGeneration()
    assert skill._seconds_to_vtt_time(0.0) == "00:00:00.000"
    assert skill._seconds_to_vtt_time(61.5) == "00:01:01.500"


def test_write_srt(tmp_path):
    """Should write valid SRT file."""
    from whisper_service import TranscriptionResult
    skill = CaptionGeneration()

    transcription = TranscriptionResult(
        text="Hello world",
        segments=[
            {"start": 0.0, "end": 1.5, "text": "Hello"},
            {"start": 1.5, "end": 3.0, "text": "world"},
        ],
        language="en",
        duration=3.0,
    )

    srt_path = tmp_path / "test.srt"
    skill._write_srt(transcription, srt_path)

    content = srt_path.read_text()
    assert "1" in content
    assert "00:00:00,000 --> 00:00:01,500" in content
    assert "Hello" in content
    assert "world" in content


def test_write_vtt(tmp_path):
    """Should write valid VTT file with header."""
    from whisper_service import TranscriptionResult
    skill = CaptionGeneration()

    transcription = TranscriptionResult(
        text="Hello world",
        segments=[{"start": 0.0, "end": 1.5, "text": "Hello world"}],
        language="en",
        duration=1.5,
    )

    vtt_path = tmp_path / "test.vtt"
    skill._write_vtt(transcription, vtt_path)

    content = vtt_path.read_text()
    assert content.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.500" in content
    assert "Hello world" in content

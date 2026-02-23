"""Tests for Skill 18: Voiceover Generation."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from skill_voiceover import VoiceoverGenerator


@pytest.fixture
def generator():
    return VoiceoverGenerator()


@pytest.fixture
def test_video(tmp_path):
    """Create a short test video with audio for merge tests."""
    path = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "smptebars=size=640x480:rate=30:duration=5" '
        f'-f lavfi -i "sine=frequency=440:duration=5" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{path}" -y 2>/dev/null'
    )
    return path


def test_list_voices(generator):
    """Should return 5 voice presets."""
    voices = generator.list_voices()
    assert len(voices) == 5
    assert "narrator_male" in voices
    assert "narrator_female" in voices
    assert "professional" in voices
    assert "friendly" in voices
    assert "energetic" in voices


def test_estimate_duration(generator):
    """150 words should be approximately 60 seconds."""
    text = " ".join(["word"] * 150)
    duration = generator._estimate_duration(text)
    assert duration == pytest.approx(60.0, abs=0.1)


def test_estimate_duration_empty(generator):
    """Empty text should yield 0 seconds."""
    assert generator._estimate_duration("") == 0.0
    assert generator._estimate_duration("   ") == 0.0


def test_generate_silence_placeholder(generator, tmp_path):
    """Should create a WAV file of the correct approximate duration."""
    output = tmp_path / "silence.wav"
    generator._generate_silence_placeholder(3.0, output)
    assert output.exists()
    assert output.stat().st_size > 0

    # Verify duration via ffprobe (get_metadata requires a video stream,
    # so we query ffprobe directly for the audio-only WAV file)
    cmd = [
        generator.ffmpeg.ffprobe,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    duration = float(data["format"]["duration"])
    assert duration == pytest.approx(3.0, abs=0.5)


def test_execute_no_api_key(generator, tmp_path):
    """Without API key, should fall back to silence placeholder and return valid result."""
    generator.enabled = False
    output = tmp_path / "voiceover.wav"

    # Mock _generate_audio so it calls _generate_silence_placeholder instead
    def fake_generate(text, voice_id, out_path):
        duration = generator._estimate_duration(text)
        return generator._generate_silence_placeholder(duration, out_path)

    with patch.object(generator, "_generate_audio", side_effect=fake_generate):
        result = generator.execute(
            text="Hello world, this is a test voiceover.",
            output_path=output,
            voice="narrator_male",
        )

    assert output.exists()
    assert result["voice_used"] == "Adam"
    assert result["text_length"] > 0
    assert result["duration"] > 0
    assert "audio_path" in result


def test_execute_invalid_voice(generator, tmp_path):
    """Unknown voice preset should raise ValueError."""
    output = tmp_path / "voiceover.wav"
    with pytest.raises(ValueError, match="Unknown voice"):
        generator.execute(
            text="Test text.",
            output_path=output,
            voice="nonexistent_voice",
        )


def test_execute_empty_text(generator, tmp_path):
    """Empty text should raise ValueError."""
    output = tmp_path / "voiceover.wav"
    with pytest.raises(ValueError, match="Text must not be empty"):
        generator.execute(text="", output_path=output)

    with pytest.raises(ValueError, match="Text must not be empty"):
        generator.execute(text="   ", output_path=output)


def test_execute_with_merge(generator, test_video, tmp_path):
    """Should generate placeholder audio and merge it with a test video."""
    generator.enabled = False
    output = tmp_path / "merged.mp4"

    def fake_generate(text, voice_id, out_path):
        duration = generator._estimate_duration(text)
        return generator._generate_silence_placeholder(duration, out_path)

    with patch.object(generator, "_generate_audio", side_effect=fake_generate):
        result = generator.execute(
            text="This is narration that goes over the video content.",
            output_path=output,
            voice="professional",
            video_path=test_video,
            merge_with_video=True,
        )

    assert output.exists()
    assert "video_path" in result
    assert result["voice_used"] == "Daniel"
    assert result["text_length"] > 0

    # Verify the merged video has both video and audio streams
    meta = generator.ffmpeg.get_metadata(output)
    assert meta.has_audio
    assert meta.width == 640
    assert meta.height == 480

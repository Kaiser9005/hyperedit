import pytest
import json
import os
from pathlib import Path

from whisper_service import WhisperService, TranscriptionResult


def test_whisper_service_init():
    """whisper.cpp CLI should be found at known path"""
    svc = WhisperService()
    assert svc.cli_path.exists(), f"whisper-cli not found at {svc.cli_path}"


def test_transcription_result_model():
    """TranscriptionResult should have required fields"""
    result = TranscriptionResult(
        text="Hello world",
        segments=[{"start": 0.0, "end": 1.5, "text": "Hello world"}],
        language="en",
        duration=1.5,
    )
    assert result.text == "Hello world"
    assert len(result.segments) == 1
    assert result.duration == 1.5


def test_extract_audio_from_video(tmp_path):
    """Should extract 16kHz mono WAV from video"""
    svc = WhisperService()

    # Create a tiny test video with ffmpeg
    test_video = tmp_path / "test.mp4"
    os.system(
        f'ffmpeg -f lavfi -i "sine=frequency=440:duration=2" '
        f'-f lavfi -i "color=c=black:s=320x240:d=2" '
        f'-c:v libx264 -preset ultrafast -c:a aac '
        f'"{test_video}" -y 2>/dev/null'
    )
    assert test_video.exists()

    audio_path = svc.extract_audio(test_video, tmp_path / "audio.wav")
    assert audio_path.exists()
    assert audio_path.suffix == ".wav"


def test_detect_silence(tmp_path):
    """Should detect silent segments in audio"""
    svc = WhisperService()

    # Create audio with silence gap: 1s tone + 2s silence + 1s tone
    test_audio = tmp_path / "silence_test.wav"
    os.system(
        f'ffmpeg -f lavfi -i "sine=frequency=440:duration=1" '
        f'-f lavfi -i "anullsrc=r=16000:cl=mono" '
        f'-f lavfi -i "sine=frequency=440:duration=1" '
        f'-filter_complex "[0][1][2]concat=n=3:v=0:a=1,atrim=duration=4" '
        f'-ar 16000 -ac 1 "{test_audio}" -y 2>/dev/null'
    )

    silences = svc.detect_silence(test_audio, noise_db=-30, min_duration=1.0)
    assert len(silences) >= 1, "Should detect at least one silence gap"
    assert silences[0]["start"] >= 0.5
    # Silence may extend to end of file (4.0s) since anullsrc + atrim=4
    assert silences[0]["end"] <= 4.5


def test_detect_filler_words():
    """Should detect filler words from transcription segments"""
    svc = WhisperService()

    transcription = TranscriptionResult(
        text="um hello uh world euh bonjour",
        segments=[
            {"start": 0.0, "end": 0.5, "text": "um"},
            {"start": 0.5, "end": 1.0, "text": "hello"},
            {"start": 1.0, "end": 1.5, "text": "uh"},
            {"start": 1.5, "end": 2.0, "text": "world"},
            {"start": 2.0, "end": 2.5, "text": "euh"},
            {"start": 2.5, "end": 3.0, "text": "bonjour"},
        ],
        language="en",
        duration=3.0,
    )

    fillers = svc.detect_filler_words(transcription)
    assert len(fillers) == 3
    assert fillers[0]["text"] == "um"
    assert fillers[1]["text"] == "uh"
    assert fillers[2]["text"] == "euh"


def test_timestamp_conversion():
    """Should convert whisper timestamps to seconds"""
    svc = WhisperService()
    assert svc._ts_to_seconds("00:00:01.500") == 1.5
    assert svc._ts_to_seconds("00:01:30.000") == 90.0
    assert svc._ts_to_seconds("01:00:00.000") == 3600.0

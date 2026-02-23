"""whisper.cpp wrapper service for local transcription with timestamps."""

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TranscriptionResult:
    text: str
    segments: list[dict]
    language: str
    duration: float


class WhisperService:
    """Wraps whisper.cpp CLI for local speech-to-text transcription."""

    def __init__(
        self,
        cli_path: Optional[str] = None,
        model_path: Optional[str] = None,
    ):
        self.cli_path = Path(
            cli_path or os.getenv("WHISPER_CLI", "/usr/local/bin/whisper-cli")
        )
        self.model_path = Path(
            model_path
            or os.getenv(
                "WHISPER_MODEL",
                os.path.expanduser("~/hyperedit-ai/models/whisper/ggml-base.bin"),
            )
        )
        self.ffmpeg_path = Path(
            os.getenv("FFMPEG_PATH", "/usr/local/bin/ffmpeg")
        )
        self.ffprobe_path = Path(
            os.getenv("FFPROBE_PATH", "/usr/local/bin/ffprobe")
        )

    def extract_audio(self, video_path: Path, output_path: Path) -> Path:
        """Extract 16kHz mono WAV from video for whisper.cpp input."""
        cmd = [
            str(self.ffmpeg_path),
            "-i", str(video_path),
            "-vn",              # no video
            "-ar", "16000",     # 16kHz sample rate (whisper.cpp requirement)
            "-ac", "1",         # mono
            "-f", "wav",
            str(output_path),
            "-y",               # overwrite
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def transcribe(
        self,
        audio_path: Path,
        language: str = "auto",
        word_timestamps: bool = True,
    ) -> TranscriptionResult:
        """Transcribe audio using whisper.cpp CLI."""
        output_json = audio_path.with_suffix(".json")

        cmd = [
            str(self.cli_path),
            "-m", str(self.model_path),
            "-f", str(audio_path),
            "--output-json-full",
            "-of", str(audio_path.with_suffix("")),  # output filename prefix
        ]

        if language != "auto":
            cmd.extend(["-l", language])

        if word_timestamps:
            cmd.extend(["--max-len", "1"])  # word-level timestamps

        result = subprocess.run(cmd, capture_output=True, text=True)

        if not output_json.exists():
            # Try alternate output path
            alt_json = Path(str(audio_path) + ".json")
            if alt_json.exists():
                output_json = alt_json
            else:
                raise RuntimeError(
                    f"whisper.cpp did not produce JSON output.\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}"
                )

        with open(output_json) as f:
            data = json.load(f)

        # Parse whisper.cpp JSON format
        segments = []
        full_text_parts = []

        transcription = data.get("transcription", [])
        for seg in transcription:
            text = seg.get("text", "").strip()
            if text:
                segments.append({
                    "start": self._ts_to_seconds(seg.get("timestamps", {}).get("from", "00:00:00.000")),
                    "end": self._ts_to_seconds(seg.get("timestamps", {}).get("to", "00:00:00.000")),
                    "text": text,
                })
                full_text_parts.append(text)

        duration = self._get_audio_duration(audio_path)

        return TranscriptionResult(
            text=" ".join(full_text_parts),
            segments=segments,
            language=language,
            duration=duration,
        )

    def transcribe_video(
        self,
        video_path: Path,
        language: str = "auto",
        work_dir: Optional[Path] = None,
    ) -> TranscriptionResult:
        """Full pipeline: extract audio from video then transcribe."""
        if work_dir is None:
            work_dir = video_path.parent

        audio_path = work_dir / f"{video_path.stem}_audio.wav"
        self.extract_audio(video_path, audio_path)
        return self.transcribe(audio_path, language=language)

    def detect_silence(
        self,
        audio_path: Path,
        noise_db: float = -40,
        min_duration: float = 1.5,
    ) -> list[dict]:
        """Detect silent segments in audio using FFmpeg silencedetect."""
        cmd = [
            str(self.ffmpeg_path),
            "-i", str(audio_path),
            "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr = result.stderr

        silences = []
        current_start = None

        for line in stderr.split("\n"):
            if "silence_start:" in line:
                parts = line.split("silence_start:")
                current_start = float(parts[1].strip())
            elif "silence_end:" in line and current_start is not None:
                parts = line.split("silence_end:")
                end_parts = parts[1].strip().split("|")
                end_time = float(end_parts[0].strip())
                silences.append({"start": current_start, "end": end_time})
                current_start = None

        return silences

    def detect_filler_words(
        self,
        transcription: TranscriptionResult,
        fillers: Optional[list[str]] = None,
    ) -> list[dict]:
        """Find filler words in transcription with their timestamps."""
        if fillers is None:
            fillers = [
                "um", "uh", "erm", "ah", "like", "you know", "so",
                "basically", "actually", "literally",
                # French fillers
                "euh", "heu", "alors", "bon", "ben", "genre", "voilà",
            ]

        filler_segments = []
        for seg in transcription.segments:
            text_lower = seg["text"].lower().strip()
            if text_lower in fillers:
                filler_segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"],
                    "type": "filler",
                })

        return filler_segments

    def _ts_to_seconds(self, timestamp: str) -> float:
        """Convert HH:MM:SS.mmm to seconds."""
        parts = timestamp.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        return 0.0

    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio duration in seconds using ffprobe."""
        cmd = [
            str(self.ffprobe_path),
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(audio_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

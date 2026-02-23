"""Skill 2: Caption Generation.

Generates SRT/VTT caption files from video transcription.
Uses whisper.cpp for transcription and FFmpeg for burn-in.
"""

import argparse
from pathlib import Path
from typing import Optional

from whisper_service import WhisperService, TranscriptionResult
from ffmpeg_service import FFmpegService
from quality_assurance import QualityAssurance


class CaptionGeneration:
    """Generate captions/subtitles from video."""

    def __init__(self):
        self.whisper = WhisperService()
        self.ffmpeg = FFmpegService()
        self.qa = QualityAssurance()

    def execute(
        self,
        input_path: Path,
        output_dir: Path,
        language: str = "auto",
        formats: list[str] = None,
        burn_in: bool = False,
        font_size: int = 24,
        position: str = "bottom",
    ) -> dict:
        """Full V-I-V cycle for caption generation."""
        if formats is None:
            formats = ["srt", "vtt"]

        # === VERIFY (Before) ===
        meta = self.ffmpeg.get_metadata(input_path)
        if not meta.has_audio:
            raise ValueError(f"Input video has no audio track: {input_path}")

        # === IMPLEMENT ===
        output_dir.mkdir(parents=True, exist_ok=True)

        # 1. Transcribe
        transcription = self.whisper.transcribe_video(
            input_path, language=language, work_dir=output_dir
        )

        # 2. Generate caption files
        generated_files = []
        stem = input_path.stem

        if "srt" in formats:
            srt_path = output_dir / f"{stem}.srt"
            self._write_srt(transcription, srt_path)
            generated_files.append(str(srt_path))

        if "vtt" in formats:
            vtt_path = output_dir / f"{stem}.vtt"
            self._write_vtt(transcription, vtt_path)
            generated_files.append(str(vtt_path))

        # 3. Optionally burn in
        burned_video = None
        if burn_in and "srt" in formats:
            srt_path = output_dir / f"{stem}.srt"
            burned_video = output_dir / f"{stem}_captioned.mp4"
            self._burn_captions(input_path, srt_path, burned_video, font_size, position)

        # === VERIFY (After) ===
        # Verify each generated caption file exists and is non-empty
        for file_path_str in generated_files:
            caption_path = Path(file_path_str)
            if not caption_path.exists():
                raise RuntimeError(f"Caption file was not created: {caption_path}")
            if caption_path.stat().st_size == 0:
                raise RuntimeError(f"Caption file is empty: {caption_path}")

        qa_results = []
        if burned_video and burned_video.exists():
            qa_results = self.qa.full_check(
                burned_video, min_width=meta.width, min_height=meta.height
            )

        return {
            "segments_count": len(transcription.segments),
            "total_text_length": len(transcription.text),
            "language": transcription.language,
            "duration": transcription.duration,
            "generated_files": generated_files,
            "burned_video": str(burned_video) if burned_video else None,
            "qa_results": [r.__dict__ for r in qa_results],
        }

    def _write_srt(self, transcription: TranscriptionResult, output_path: Path):
        """Write SRT subtitle file."""
        lines = []
        for i, seg in enumerate(transcription.segments, 1):
            start = self._seconds_to_srt_time(seg["start"])
            end = self._seconds_to_srt_time(seg["end"])
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(seg["text"].strip())
            lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    def _write_vtt(self, transcription: TranscriptionResult, output_path: Path):
        """Write WebVTT subtitle file."""
        lines = ["WEBVTT", ""]
        for i, seg in enumerate(transcription.segments, 1):
            start = self._seconds_to_vtt_time(seg["start"])
            end = self._seconds_to_vtt_time(seg["end"])
            lines.append(f"{i}")
            lines.append(f"{start} --> {end}")
            lines.append(seg["text"].strip())
            lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    def _burn_captions(
        self,
        video_path: Path,
        srt_path: Path,
        output_path: Path,
        font_size: int = 24,
        position: str = "bottom",
    ):
        """Burn SRT captions into video using FFmpeg."""
        import subprocess, os

        margin_v = 30 if position == "bottom" else 10
        alignment = 2 if position == "bottom" else 6  # ASS alignment

        cmd = [
            os.getenv("FFMPEG_PATH", "/usr/local/bin/ffmpeg"),
            "-i", str(video_path),
            "-vf", f"subtitles={srt_path}:force_style='FontSize={font_size},MarginV={margin_v},Alignment={alignment}'",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp (HH:MM:SS,mmm)."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _seconds_to_vtt_time(self, seconds: float) -> str:
        """Convert seconds to VTT timestamp (HH:MM:SS.mmm)."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate captions from video")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", required=True, help="Output directory")
    parser.add_argument("--language", default="auto")
    parser.add_argument("--burn-in", action="store_true")
    parser.add_argument("--font-size", type=int, default=24)

    args = parser.parse_args()

    skill = CaptionGeneration()
    result = skill.execute(
        input_path=Path(args.input),
        output_dir=Path(args.output),
        language=args.language,
        burn_in=args.burn_in,
        font_size=args.font_size,
    )

    print(f"\n=== Caption Generation Complete ===")
    print(f"Segments: {result['segments_count']}")
    print(f"Files: {result['generated_files']}")

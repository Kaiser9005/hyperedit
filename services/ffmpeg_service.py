"""FFmpeg wrapper service for video processing operations."""

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path




@dataclass
class VideoMetadata:
    width: int
    height: int
    fps: float
    duration: float
    codec: str
    has_audio: bool
    bitrate: int
    file_size: int


class FFmpegService:
    """Wraps FFmpeg CLI for video processing operations."""

    def __init__(self):
        self.ffmpeg = os.getenv("FFMPEG_PATH", "/usr/local/bin/ffmpeg")
        self.ffprobe = os.getenv("FFPROBE_PATH", "/usr/local/bin/ffprobe")

    def get_metadata(self, video_path: Path) -> VideoMetadata:
        """Extract comprehensive metadata from a video file."""
        cmd = [
            self.ffprobe,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        video_stream = None
        has_audio = False
        for stream in data.get("streams", []):
            if stream["codec_type"] == "video" and video_stream is None:
                video_stream = stream
            if stream["codec_type"] == "audio":
                has_audio = True

        if not video_stream:
            raise ValueError(f"No video stream found in {video_path}")

        # Parse frame rate (e.g., "30/1" or "30000/1001")
        fps_parts = video_stream.get("r_frame_rate", "30/1").split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

        fmt = data.get("format", {})

        return VideoMetadata(
            width=int(video_stream.get("width", 0)),
            height=int(video_stream.get("height", 0)),
            fps=round(fps, 2),
            duration=float(str(fmt.get("duration", 0)).replace(",", ".")),
            codec=video_stream.get("codec_name", "unknown"),
            has_audio=has_audio,
            bitrate=int(fmt.get("bit_rate", 0)),
            file_size=int(fmt.get("size", 0)),
        )

    def cut(
        self,
        input_path: Path,
        output_path: Path,
        start: float,
        end: float,
        reencode: bool = False,
    ) -> Path:
        """Cut a segment from a video."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-ss", str(start),
            "-to", str(end),
        ]
        if reencode:
            cmd.extend(["-c:v", "libx264", "-preset", "fast", "-c:a", "aac"])
        else:
            cmd.extend(["-c", "copy"])

        cmd.extend([str(output_path), "-y"])
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def concat(self, input_paths: list[Path], output_path: Path) -> Path:
        """Concatenate multiple video files."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            for path in input_paths:
                f.write(f"file '{path}'\n")
            list_file = f.name

        try:
            cmd = [
                self.ffmpeg,
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                str(output_path), "-y",
            ]
            subprocess.run(cmd, capture_output=True, check=True)
        finally:
            os.unlink(list_file)

        return output_path

    def normalize_audio(
        self,
        input_path: Path,
        output_path: Path,
        target_lufs: float = -14,
        target_tp: float = -1.5,
        target_lra: float = 11,
    ) -> Path:
        """Normalize audio to target LUFS (EBU R128)."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-af", f"loudnorm=I={target_lufs}:TP={target_tp}:LRA={target_lra}",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def crop_aspect(
        self,
        input_path: Path,
        output_path: Path,
        aspect: str = "9:16",
    ) -> Path:
        """Crop video to target aspect ratio, keeping center."""
        w_ratio, h_ratio = map(int, aspect.split(":"))

        meta = self.get_metadata(input_path)
        src_w, src_h = meta.width, meta.height

        # Calculate crop dimensions
        target_ratio = w_ratio / h_ratio
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            # Source is wider: crop width
            crop_h = src_h
            crop_w = int(src_h * target_ratio)
        else:
            # Source is taller: crop height
            crop_w = src_w
            crop_h = int(src_w / target_ratio)

        x_offset = (src_w - crop_w) // 2
        y_offset = (src_h - crop_h) // 2

        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-vf", f"crop={crop_w}:{crop_h}:{x_offset}:{y_offset}",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def apply_lut(
        self,
        input_path: Path,
        output_path: Path,
        lut_path: Path,
    ) -> Path:
        """Apply a 3D LUT file for color grading."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-vf", f"lut3d='{lut_path}'",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def color_adjust(
        self,
        input_path: Path,
        output_path: Path,
        contrast: float = 1.0,
        brightness: float = 0.0,
        saturation: float = 1.0,
    ) -> Path:
        """Adjust color properties without a LUT file."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-vf", f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation}",
            "-c:v", "libx264", "-preset", "fast",
            "-c:a", "copy",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def extract_frame(
        self,
        input_path: Path,
        output_path: Path,
        timestamp: float,
    ) -> Path:
        """Extract a single frame as an image."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-ss", str(timestamp),
            "-frames:v", "1",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def noise_reduce(
        self,
        input_path: Path,
        output_path: Path,
    ) -> Path:
        """Apply noise reduction to audio."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-af", "afftdn=nf=-20",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def merge_audio(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        audio_volume: float = 0.15,
    ) -> Path:
        """Merge background audio track with video (with volume adjustment)."""
        cmd = [
            self.ffmpeg,
            "-i", str(video_path),
            "-i", str(audio_path),
            "-filter_complex",
            f"[1:a]volume={audio_volume}[bg];[0:a][bg]amerge=inputs=2[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(output_path), "-y",
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def get_loudness(self, input_path: Path) -> dict:
        """Measure audio loudness (LUFS) of a video/audio file."""
        cmd = [
            self.ffmpeg,
            "-i", str(input_path),
            "-af", "loudnorm=print_format=json",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        # Parse loudnorm JSON from stderr
        stderr = result.stderr
        json_start = stderr.rfind("{")
        json_end = stderr.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(stderr[json_start:json_end])
        return {}
